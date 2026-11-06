"""Editable plan drafts with server-side revalidation (B3-04.03).

The UI only ever *proposes* a list of edits against a revision number; the engine applies them to a copy, validates the
whole plan again with the same validator the coordinator uses, and stores the result as a new signed revision. A revision
that does not validate is kept for the user to fix but can never start. Starting needs the latest revision, its exact
content hash typed back by the operator, and the TASK authority; it is a separate call from editing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
from uuid import uuid4

from ..context import safe_path
from ..engine.authority import Action, authorize
from ..engine.evidence import load_signed, save_signed
from ..engine.runner import SUPPORTED_AGENTS, tool_available
from . import coordinator, project, roles

MAX_EDITS = 50
_ID = re.compile(r"plan-[0-9a-f]{12}\Z")
_LANE_FIELDS = {"after": ("lane", "after"), "task": ("request", "task"), "worker": ("request", "worker"),
                "ownership": ("request", "ownership"), "forbidden": ("request", "forbidden")}


class StaleRevision(ValueError):
    pass


class NotStartable(ValueError):
    pass


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _path(ctx, draft_id):
    if not _ID.fullmatch(str(draft_id)):
        raise ValueError("Invalid draft identity")
    return safe_path(ctx.data_root / "plan-drafts" / f"{draft_id}.json")


def _validate(spec, project_root, settings):
    """Engine verdict for the whole plan: structure, scopes, budgets, roles. Never raises for a bad plan."""
    try:
        dag = coordinator._validate(spec, project_root, settings)
        for phase in spec.get("phases", []):
            for lane in phase.get("workstreams", []):
                worker = (lane.get("request") or {}).get("worker")
                if worker is not None and (worker not in SUPPORTED_AGENTS or not tool_available(worker)):
                    raise ValueError(f"Role unavailable: worker '{worker}' in {phase['name']}/{lane['name']} is not installed or supported")
        return {"valid": True, "problem": None, "dag": dag}
    except (TypeError, ValueError, KeyError, AttributeError, roles.RoleError) as error:
        return {"valid": False, "problem": str(error)[:500], "dag": None}


def _apply(spec, edits):
    """Apply edits to a copy. A malformed edit is a caller error (nothing is saved); an invalid plan is not."""
    if not isinstance(edits, list) or not 1 <= len(edits) <= MAX_EDITS:
        raise ValueError(f"Send 1..{MAX_EDITS} edits")
    spec = copy.deepcopy(spec)
    phases = {p["name"]: p for p in spec.get("phases", []) if isinstance(p, dict) and "name" in p}
    for edit in edits:
        if not isinstance(edit, dict) or edit.get("op") not in ("set_lane", "set_phase_after", "rename_lane"):
            raise ValueError("Unknown edit operation")
        phase = phases.get(edit.get("phase"))
        if phase is None:
            raise ValueError("Edit names an unknown phase")
        if edit["op"] == "set_phase_after":
            if not isinstance(edit.get("value"), list):
                raise ValueError("value must be a list")
            phase["after"] = edit["value"]
            continue
        lane = next((w for w in phase.get("workstreams", []) if isinstance(w, dict) and w.get("name") == edit.get("lane")), None)
        if lane is None:
            raise ValueError("Edit names an unknown workstream")
        if edit["op"] == "rename_lane":
            if not isinstance(edit.get("to"), str):
                raise ValueError("to must be a string")
            lane["name"] = edit["to"]
            continue
        field = _LANE_FIELDS.get(edit.get("field"))
        if field is None or "value" not in edit:
            raise ValueError("Unknown lane field")
        target = lane if field[0] == "lane" else lane.setdefault("request", {})
        target[field[1]] = edit["value"]
    return spec


def _store(ctx, draft, spec, edits, settings):
    verdict = _validate(spec, draft["project_root"], settings)
    revision = draft["revision"] + 1
    draft = {**draft, "revision": revision, "spec": spec, "spec_hash": spec_hash(spec), "valid": verdict["valid"],
             "problem": verdict["problem"], "history": [*draft["history"], {"revision": revision, "edits": edits, "valid": verdict["valid"]}][-100:]}
    save_signed(ctx, _path(ctx, draft["draft_id"]), draft)
    return draft


def _summary(draft):
    return {k: draft[k] for k in ("draft_id", "revision", "spec_hash", "valid", "problem", "project_root")} | {"started": draft.get("started")}


def create_draft(ctx, spec, project_root, settings=None):
    if not isinstance(spec, dict) or not isinstance(project_root, str):
        raise ValueError("create_draft needs a spec object and project_root")
    settings = roles.read_settings(ctx.data_root) if settings is None else settings
    draft_id = f"plan-{uuid4().hex[:12]}"
    (ctx.data_root / "plan-drafts").mkdir(parents=True, exist_ok=True)
    base = {"draft_id": draft_id, "project_root": project_root, "revision": 0, "history": [], "started": None}
    return _summary(_store(ctx, base, spec, [], settings))


def get_draft(ctx, draft_id):
    return load_signed(ctx, _path(ctx, draft_id))


class _Lock:
    def __init__(self, path):
        self.path = path.with_suffix(".lock")

    def __enter__(self):
        for _ in range(100):
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                time.sleep(0.05)
        raise ValueError("Draft is busy; retry")

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)


def edit_draft(ctx, draft_id, expected_revision, edits, settings=None):
    settings = roles.read_settings(ctx.data_root) if settings is None else settings
    path = _path(ctx, draft_id)
    with _Lock(path):
        draft = load_signed(ctx, path)
        if draft.get("started"):
            raise NotStartable("This draft was already started; create a new draft to change the plan")
        if expected_revision != draft["revision"]:
            raise StaleRevision(f"Draft is at revision {draft['revision']}, edit was made against {expected_revision}")
        return _summary(_store(ctx, draft, _apply(draft["spec"], edits), edits, settings))


def start_draft(ctx, draft_id, revision, confirm_hash, *, origin, start=None):
    """The separate operator action. Everything is re-checked here from the stored, signed draft, not from the caller."""
    authorize(origin, Action.TASK)
    path = _path(ctx, draft_id)
    with _Lock(path):
        draft = load_signed(ctx, path)
        if draft.get("started"):
            raise NotStartable("Already started")  # exactly once
        if revision != draft["revision"]:
            raise StaleRevision(f"Draft is at revision {draft['revision']}")
        if confirm_hash != draft["spec_hash"] or spec_hash(draft["spec"]) != draft["spec_hash"]:
            raise NotStartable("Confirmation does not match this plan's content hash")
        verdict = _validate(draft["spec"], draft["project_root"], roles.read_settings(ctx.data_root))
        if not verdict["valid"]:
            raise NotStartable(f"Plan is not valid: {verdict['problem']}")
        draft["started"] = {"revision": revision, "spec_hash": confirm_hash}
        save_signed(ctx, path, draft)  # recorded before the launch: a crash can never start it twice
    result = (start or project.start_project)(ctx, draft["spec"])
    return {"draft_id": draft_id, "started": True, "result": result}
