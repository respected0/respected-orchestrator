"""Rule-based capability recommender (B4-03.02). Advice only: it reads inventory records and returns a ranked, explained list.

It writes nothing, installs nothing, enables nothing and calls no model or catalog. A recommendation is never an approval:
every entry says `needs_approval: true` and carries the record's own trust state untouched. Ranking uses only structured facts
(the capability's name, its kind, compatibility, installed/trusted state). Descriptions and any other free text a capability
ships are untrusted data: they are never matched, only echoed (trimmed) when they look harmless, so a description cannot make
itself relevant or rank itself up. Task text is used only to pick task categories; it never selects permissions."""
import re
from collections.abc import Mapping, Sequence
from typing import Any

from . import compatibility

# task category -> (words in the task text, words in a capability NAME). Small on purpose; extending it is a code change, not data.
TAXONOMY = {
    "testing": (r"test|pytest|unittest|coverage|regression", r"test|pytest|jest|coverage"),
    "browser": (r"browser|ui|frontend|web ?page|screenshot|css|html|click", r"playwright|puppeteer|browser|chrome|selenium"),
    "docs": (r"doc|readme|markdown|guide|changelog", r"doc|markdown|readme|mdbook"),
    "repo_search": (r"refactor|rename|find|search|codebase|large repo|architecture", r"serena|context|search|grep|index|repo|code"),
    "github": (r"github|issue|pull request|\bpr\b|ci\b|workflow", r"github|\bgh\b|git"),
    "format": (r"format|lint|style|black|ruff|prettier", r"format|lint|black|ruff|prettier|eslint"),
}
MAX_SHOWN = 10


def categories(task_text: Any) -> list[str]:
    """Task categories the text mentions. Pure keyword match; unknown text gives [] and therefore no recommendation."""
    text = task_text.casefold() if isinstance(task_text, str) else ""
    return [name for name, (task_re, _) in TAXONOMY.items() if re.search(task_re, text)]


def _shown(description: Any, record: Mapping[str, Any]) -> str | None:
    bad = any(w.get("kind") == "instruction_like_text" for w in record.get("warnings", []))
    return None if bad or not isinstance(description, str) else description[:200]


def recommend(task_text: Any, risk: Mapping[str, Any] | None, inventory: Mapping[str, Any], target_client: str, *, project: str | None = None) -> dict[str, Any]:
    """{task_categories, recommendations[...], excluded[...], notes[...]}; deterministic, offline, read-only."""
    cats = categories(task_text)
    level = (risk or {}).get("level", "unknown")
    notes: list[str] = []
    if not cats:
        notes.append("no_task_category_matched: nothing is suggested for a task this engine cannot classify")
    recommendations, excluded = [], []
    for record in inventory.get("capabilities", []):
        compat = compatibility.resolve(record, target_client, project=project)
        matched = [c for c in cats if re.search(TAXONOMY[c][1], str(record.get("name", "")).casefold())]
        if compat["verdict"] == "incompatible":
            if matched:
                excluded.append({"id": record["id"], "name": record["name"], "why": [r["detail"] for r in compat["reasons"] if r["verdict"] == "incompatible"]})
            continue
        if not matched:
            continue
        status = record.get("status", {})
        trusted = bool(status.get("trusted", {}).get("state"))
        installed = status.get("installed", {}).get("state")
        declared = record.get("declared_permissions", {})
        risks = [w["kind"] for w in record.get("warnings", []) if w["kind"] in ("launches_local_process", "secrets_in_config", "instruction_like_text", "unknown_transport")]
        if isinstance(declared.get("network"), str) and declared["network"].startswith("http"):
            risks.append("reaches_network")
        recommendations.append({
            "id": record["id"], "name": record["name"], "kind": record["kind"], "scope": record["scope"],
            "matched": matched, "compatibility": compat["verdict"], "compatibility_reasons": [r["detail"] for r in compat["reasons"]],
            "installed": installed, "trusted": trusted, "risks": sorted(set(risks)), "description": _shown(record.get("entry", {}).get("description"), record),
            "blocked_by_risk": level in ("high", "unknown") and not trusted,
            "needs_approval": True, "score": 2 * len(matched) + int(trusted) + int(installed is True) - int(compat["verdict"] == "unknown")})
    recommendations.sort(key=lambda r: (-r["score"], r["name"].casefold(), r["id"]))
    if cats and recommendations and all(r["compatibility"] == "unknown" for r in recommendations):
        notes.append("all_unknown: every candidate has unconfirmed compatibility")
    if cats and not recommendations:
        notes.append("nothing_matched: no discovered capability fits this task; nothing is fetched or installed")
    return {"task_categories": cats, "risk_level": level, "recommendations": recommendations[:MAX_SHOWN],
            "excluded": excluded[:MAX_SHOWN], "notes": notes, "side_effects": "none"}
