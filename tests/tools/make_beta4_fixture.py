"""Writes desktop/tests/fixtures/beta4.json: the REAL engine's replies for the three Beta.4 read-only screens, produced from a synthetic
data root and a synthetic home (no real configuration is read). The desktop tests parse this file with the screens' own view functions,
so the TypeScript shapes and the Python engine cannot drift apart unnoticed.

    python -m tests.tools.make_beta4_fixture
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import local_api
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.journal import Journal
from respected_orchestrator.workflows import handoff, team_profiles as tp

OUT = Path(__file__).resolve().parents[2] / "desktop" / "tests" / "fixtures" / "beta4.json"
USAGE = {"raw_input_tokens": 12000, "cached_input_tokens": 4000, "output_tokens": 800, "estimated_weighted_tokens": 9000}


def build() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        home = root / "home"
        (home / ".claude" / "skills" / "docs-writer").mkdir(parents=True)
        (home / ".claude" / "skills" / "docs-writer" / "SKILL.md").write_text("---\nname: docs-writer\ndescription: Writes documentation.\n---\n", encoding="utf-8")
        (home / ".claude.json").write_text(json.dumps({"mcpServers": {"pytest-runner": {"command": "python", "args": ["-m", "pytest_mcp"]},
                                                                      "github": {"type": "http", "url": "https://api.example.com/mcp"}}}), encoding="utf-8")
        ctx = EngineContext(root / "data")
        tools = ["codex", "claude", "opencode", "custom", "agy", "openrouter", "cursor"]
        members = [{"id": "lead", "name": "Lider", "role": "lead", "assignment": {"tool": "claude", "profile": "opus"}},
                   {"id": "implementer", "name": "Geliştirici", "role": "implementer", "assignment": {"tool": "codex", "profile": "gpt"}},
                   {"id": "reviewer", "name": "Gözden geçiren", "role": "reviewer", "assignment": {"tool": "claude", "profile": "sonnet"}}]
        team = tp.save(ctx.data_root, {"schema": 1, "id": "core", "name": "Çekirdek takım", "members": members}, tools)
        env = handoff.parse(ctx, team, {"to": "reviewer", "scope": {"paths": ["src/a.py"]}, "reason": "needs_review", "next_action": "review", "note": "testler geçti"},
                            sender={"profile_id": "implementer", "session_id": "ss-1"}, granted_scope=["src"])
        handoff.post(ctx, env)
        Journal(ctx.state_dir / "events.log").append("esc-1", "handoff.escalated", "run-20261108000001-aaaaaaaaaaa1",
                                                     {"reasons": ["hop budget spent: hop is already beyond max_hops"], "stop_sessions": []})
        specs = [("completed", None, USAGE), ("completed", None, USAGE), ("failed", "test_failed", USAGE), ("failed", "limit_exhausted", None),
                 ("completed", None, None), ("completed", None, USAGE), ("failed", "limit_exhausted", None)]
        for n, (status, reason, usage) in enumerate(specs, 1):
            d = ctx.state_dir / f"run-2026110800000{n}-aaaaaaaaaaa{n}"
            d.mkdir(parents=True)
            save_signed(ctx, d / "request.json", {"kind": "write", "worker": "codex" if n % 2 else "claude", "project_root": "C:/projeler/uygulama" if n < 5 else "C:/projeler/site"})
            save_signed(ctx, d / "status.json", {"status": status, "updated_at": "2026-11-08T00:00:00+00:00", **({"reason": reason} if reason else {}), **({"usage": usage} if usage else {})})
        (ctx.data_root / "settings.json").write_text(json.dumps({"budget_weighted_tokens": 60000}), encoding="utf-8")
        token = "fixture-token-0123456789abcdef"
        api = local_api.LocalApi(ctx, token, origin=Origin.HUMAN)
        out = {}
        with mock.patch.dict(os.environ, {"USERPROFILE": str(home), "HOME": str(home)}), mock.patch("respected_orchestrator.engine.local_api.tool_available", lambda t: t != "codex"):
            for n, (name, cmd, payload) in enumerate([("team", "team.view", {}), ("suggestions", "capabilities.recommend", {"task": "pytest ile testleri çalıştır ve dokümantasyonu güncelle run the tests and update the docs"}),
                                                      ("usage", "analytics.summary", {})], 1):
                out[name] = api.handle({"ipc": local_api.IPC, "id": f"fixture-{n:04}", "session": token, "cmd": cmd, "payload": payload})
        return out


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({sum(1 for v in data.values() if v['ok'])}/3 ok)")
    sys.exit(0 if all(v["ok"] for v in data.values()) else 1)
