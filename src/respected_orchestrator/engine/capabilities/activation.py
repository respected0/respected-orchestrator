"""Approved ActivationPlan and its gate (B4-03.04). This module decides; it never writes, installs, starts or enables anything.

A plan is a described change: which discovered capability would be added to (or removed from) which project's config file, bound
by digests to exactly what was seen. A person approves it in their own native dialog (`authority`: only HUMAN may approve);
`consume` then re-checks everything against a fresh inventory and answers whether the caller may perform the listed writes.
Fail closed on: wrong or other project, a target outside the project folder, an incompatible capability, a changed or vanished
record (stale), a plan edited after it was shown (tampered), an approval for another plan, an expired or reused approval.
The execution gate of capability_manifest stays final and independent: activation puts an entry in a config; it does not
make a tool callable (`execution` on each change reports what that gate says today). Rollback is the exact inverse list."""
import hashlib
import json
import secrets
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..authority import Action, Origin, authorize
from . import compatibility, paths, permissions

SCHEMA = 1
TTL_SECONDS = 300
OPS = ("enable", "disable")


class ActivationError(PermissionError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _inside(project: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(project.resolve())
        return True
    except ValueError:
        return False


def _target(client: str, kind: str, project: Path) -> Path:
    for row in paths.matrix(Path("/probe-home"), project):
        if row["client"] == client and row["kind"] == kind and row["scope"] == "project":
            return Path(row["path"])
    raise ActivationError("NO_PROJECT_TARGET", f"{client} has no project-level place for {kind} capabilities")


def propose(project_root: str | Path, changes: Sequence[Mapping[str, Any]], inventory: Mapping[str, Any], *, target_client: str, now: float) -> dict[str, Any]:
    """Describe the change. Nothing is written. Raises ActivationError for anything that cannot be activated for this project."""
    project = Path(project_root).resolve()
    if not project.is_dir():
        raise ActivationError("PROJECT_MISSING", "the project folder does not exist")
    records = {r["id"]: r for r in inventory.get("capabilities", [])}
    out = []
    for change in changes:
        op, cid = change.get("op"), change.get("capability_id")
        if op not in OPS or cid not in records:
            raise ActivationError("BAD_CHANGE", "each change needs op enable|disable and a capability id from the inventory")
        record = records[cid]
        if record.get("scope") == "project" and record.get("project_path") and Path(record["project_path"]).resolve() != project:
            raise ActivationError("CROSS_PROJECT", f"{cid} belongs to a different project")
        compat = compatibility.resolve(record, target_client, project=str(project))
        if op == "enable" and compat["verdict"] == "incompatible":
            raise ActivationError("INCOMPATIBLE", f"{cid}: " + "; ".join(r["detail"] for r in compat["reasons"] if r["verdict"] == "incompatible"))
        target = _target(target_client, record["kind"], project)
        if not _inside(project, target):
            raise ActivationError("OUTSIDE_WORKSPACE", "the target config file is outside the project folder")
        card = permissions.inspect(record)
        before = _digest(target.read_text("utf-8")) if target.is_file() else None
        out.append({"op": op, "capability_id": cid, "name": record["name"], "kind": record["kind"], "record_digest": record["digest"],
                    "write": {"path": str(target), "action": "add_entry" if op == "enable" else "remove_entry", "file_digest_before": before},
                    "compatibility": compat["verdict"], "risk_level": card["level"], "execution": card["execution"]["code"] or "approved",
                    "rollback": {"op": "disable" if op == "enable" else "enable", "restore_file_digest": before}})
    if not out:
        raise ActivationError("EMPTY_PLAN", "a plan needs at least one change")
    body = {"schema": SCHEMA, "project": str(project), "target_client": target_client, "changes": out}
    plan_id = "act-" + _digest(body)[:16]
    return {**body, "plan_id": plan_id, "binding": binding(plan_id, body), "expires_at": now + TTL_SECONDS, "status": "proposed"}


def binding(plan_id: str, body: Mapping[str, Any]) -> str:
    """What the person is shown, as one digest; a decision about any other plan cannot match it."""
    return _digest([plan_id, body["project"], body["target_client"], [(c["op"], c["capability_id"], c["record_digest"], c["write"]) for c in body["changes"]]])


def approve(plan: Mapping[str, Any], decision: str, shown_binding: str, *, origin: Origin, now: float) -> dict[str, Any]:
    """Only the native human-presence authority gets here. Returns the single-use approval (or a denial record)."""
    authorize(origin, Action.PRIVILEGED)
    if decision not in ("approve", "deny"):
        raise ActivationError("BAD_DECISION", "decision must be approve or deny")
    if shown_binding != plan["binding"]:
        raise ActivationError("BINDING_MISMATCH", "the decision is not about this plan")
    if now > plan["expires_at"]:
        raise ActivationError("EXPIRED", "the plan expired; ask again")
    if decision == "deny":
        return {"plan_id": plan["plan_id"], "state": "denied"}
    return {"plan_id": plan["plan_id"], "state": "approved", "binding": plan["binding"], "project": plan["project"], "nonce": secrets.token_hex(16),
            "expires_at": now + TTL_SECONDS}


def consume(plan: Mapping[str, Any], approval: Mapping[str, Any], inventory: Mapping[str, Any], *, project_root: str | Path, used_nonces: set[str], now: float) -> dict[str, Any]:
    """May the caller perform the plan's writes? Burns the nonce only on success. Raises ActivationError otherwise; performs nothing itself."""
    body = {k: plan[k] for k in ("schema", "project", "target_client", "changes")}
    if plan.get("binding") != binding(plan.get("plan_id", ""), body) or plan.get("plan_id") != "act-" + _digest(body)[:16]:
        raise ActivationError("TAMPERED", "the plan no longer matches its own digest")
    if not isinstance(approval, Mapping) or approval.get("state") != "approved":
        raise ActivationError("NOT_APPROVED", "there is no approval for this plan")
    if approval.get("plan_id") != plan["plan_id"] or approval.get("binding") != plan["binding"]:
        raise ActivationError("BINDING_MISMATCH", "the approval is for a different plan")
    if Path(project_root).resolve() != Path(plan["project"]) or approval.get("project") != plan["project"]:
        raise ActivationError("CROSS_PROJECT", "this plan was approved for another project")
    if now > approval["expires_at"]:
        raise ActivationError("EXPIRED", "the approval expired")
    if approval["nonce"] in used_nonces:
        raise ActivationError("ALREADY_USED", "this approval was already used")
    records = {r["id"]: r for r in inventory.get("capabilities", [])}
    for change in plan["changes"]:
        record = records.get(change["capability_id"])
        if record is None or record["digest"] != change["record_digest"]:
            raise ActivationError("STALE", f"{change['capability_id']} changed or vanished since the plan was shown")
        target = Path(change["write"]["path"])
        if not _inside(Path(plan["project"]), target):
            raise ActivationError("OUTSIDE_WORKSPACE", "the target config file is outside the project folder")
        now_digest = _digest(target.read_text("utf-8")) if target.is_file() else None
        if now_digest != change["write"]["file_digest_before"]:
            raise ActivationError("STALE", f"{target.name} changed since the plan was shown")
    used_nonces.add(approval["nonce"])
    return {"ok": True, "plan_id": plan["plan_id"], "writes": [c["write"] for c in plan["changes"]],
            "rollback": [c["rollback"] | {"capability_id": c["capability_id"], "path": c["write"]["path"]} for c in reversed(plan["changes"])]}
