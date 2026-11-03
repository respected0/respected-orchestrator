"""Direct vs orchestrated evaluation comparison (EVAL-02).

The control arm applies no change; the orchestrated arm applies the verified
golden fixture patch. This measures harness consistency, not model quality.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from tests.evals import runner

MODES = ("direct", "orchestrated")


def metadata():
    values = runner._metadata()
    values["model"] = "golden-fixture"
    values["comparison_schema"] = "respected.eval.compare.v1"
    return values


def evaluate_task(fixture, mode, repeat=3, timeout=20.0):
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    runs = []
    for index in range(repeat):
        root = Path(tempfile.mkdtemp(prefix=f"orch-cmp-{fixture.id.lower()}-"))
        try:
            start = runner.build_repository(fixture, root)
            if mode == "orchestrated":
                (root / "solution.py").write_text(fixture.fixed_source, encoding="utf-8", newline="\n")
            done = runner._execute(runner.COMMAND, root, timeout)
            runs.append({
                "run": index + 1,
                "start_sha": start,
                "start_sha_matches": start == fixture.start_sha,
                "status": "passed" if done["returncode"] == 0 else "failed",
                "duration_seconds": done["duration_seconds"],
                "security_violation": False,
                "cost": "bilinmiyor",
            })
        finally:
            shutil.rmtree(root, ignore_errors=True)
    passed = all(run["start_sha_matches"] and run["status"] == "passed" for run in runs)
    return {"task_id": fixture.id, "mode": mode, "status": "passed" if passed else "failed", "runs": runs}


def _summary(tasks):
    runs = [run for task in tasks for run in task["runs"]]
    return {
        "tasks": len(tasks),
        "runs": len(runs),
        "success_rate": round(sum(run["status"] == "passed" for run in runs) / len(runs), 4) if runs else 0.0,
        "security_violations": sum(run["security_violation"] is True for run in runs),
        "interventions": 0,
        "duration_seconds": round(sum(run["duration_seconds"] for run in runs), 4),
        "cost": "bilinmiyor",
    }


def compare(fixtures=None, repeat=3, timeout=20.0):
    selected = list(fixtures) if fixtures is not None else list(runner.all_fixtures())
    if not selected:
        raise ValueError("comparison needs at least one fixture")
    modes = [
        {"mode": mode, "tasks": [evaluate_task(fixture, mode, repeat, timeout) for fixture in selected]}
        for mode in MODES
    ]
    return {
        "schema": "respected.eval.compare.v1",
        "metadata": metadata(),
        "repeat": repeat,
        "timeout": timeout,
        "fixture_ids": [fixture.id for fixture in selected],
        "modes": modes,
        "summary": {entry["mode"]: _summary(entry["tasks"]) for entry in modes},
    }