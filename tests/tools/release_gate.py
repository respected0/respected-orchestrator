"""B3-09.04: the Beta.3 release gate. It collects every P0 verification into one manifest tied to a commit and decides.

    python tests/tools/release_gate.py collect OUT.json   run everything (clean tree, non-elevated), write the manifest, exit 1 unless release-ready
    python tests/tools/release_gate.py verify OUT.json    re-derive the decision from the recorded gates and this checkout

Three separate answers, never merged:
  release_ready  every required gate passed on a clean tree, with zero skips in the P0 test groups
  signed         the installer carries a valid Authenticode signature from the expected signer (release_signature.verify)
  publishable    release_ready AND signed. Without a certificate there is a named blocker (SIGNING-01), never a "signed release" claim.
Nothing here publishes, tags or pushes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 1

# gate id -> test module prefixes that must all run and pass (no skip, no failure, at least one test each)
TEST_GROUPS = {
    "appcontainer_worker_matrix": ("tests.engine.test_worker_security", "tests.engine.test_sandbox", "tests.engine.test_security_gate"),
    "gui_apply_negatives": ("tests.engine.test_approval_attacks", "tests.engine.test_approval", "tests.engine.test_apply_hardening",
                             "tests.engine.test_review_apply_invariants"),
    "intervention_negatives": ("tests.engine.test_session_control", "tests.engine.test_authority"),
    "chat_adapter": ("tests.engine.test_chat_session",),
    "installer_and_hash": ("tests.packaging.test_desktop_package", "tests.packaging.test_frozen_build"),
    "update_and_migration": ("tests.engine.test_maintenance", "tests.interfaces.test_migration_faults"),
    "offline_no_telemetry": ("tests.engine.test_no_telemetry",),
}
COMMAND_GATES = ("security_matrix", "full_suite", "desktop_check", "distribution_audit", "installer_hash", "roadmap_p0")
REQUIRED = tuple(TEST_GROUPS) + COMMAND_GATES
SIGNING_BLOCKER = {"id": "SIGNING-01", "text": "No valid Authenticode signature: the release cannot be called signed (needs a production certificate; D21)"}


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def group_result(outcomes, prefixes):
    """A P0 test group passes only if it ran at least one test per prefix and every one of them is 'ok'. A skip is a failure."""
    problems = []
    for prefix in prefixes:
        mine = {k: v for k, v in outcomes.items() if k == prefix or k.startswith(prefix + ".")}
        if not mine:
            problems.append(f"{prefix}: no tests ran")
        problems += [f"{k}: {v}" for k, v in sorted(mine.items()) if v != "ok"]
    return {"status": "fail" if problems else "pass", "detail": f"{len(problems)} problem(s)" if problems else "all ok",
            "problems": problems[:20], "tests": sum(1 for k in outcomes if any(k == p or k.startswith(p + ".") for p in prefixes))}


def roadmap_open_p0(text):
    """Beta.3 cards that are P0 and not ticked, from the roadmap's own summary table and card checkboxes. B3-09.04 is the gate itself."""
    priority = dict(re.findall(r"^\| `(B3-\d\d\.\d\d)` \|[^|]*\| (P\d)", text, re.M))
    open_ids = []
    for card, pri in priority.items():
        m = re.search(rf"^#### {re.escape(card)} .*?\n\n- \[( |x)\] \*\*Tamamland", text, re.M | re.S)
        if pri == "P0" and card != "B3-09.04" and (m is None or m.group(1) != "x"):
            open_ids.append(card)
    return sorted(open_ids), len(priority)


def evaluate(meta, gates, signature):
    """Pure decision. `gates` maps gate id -> {"status": "pass"|"fail", ...}; anything absent or not 'pass' keeps the release red."""
    reasons = []
    if not meta.get("commit_sha"):
        reasons.append("no commit SHA")
    if meta.get("tree_clean") is not True:
        reasons.append("working tree is not clean (the manifest would not describe a commit)")
    if meta.get("elevated") is not False:
        reasons.append("run was elevated or did not record elevation")
    for gate in REQUIRED:
        got = gates.get(gate)
        if not isinstance(got, dict):
            reasons.append(f"{gate}: missing")
        elif got.get("status") != "pass":
            reasons.append(f"{gate}: {got.get('status')} - {got.get('detail')}")
    ready = not reasons
    signed = isinstance(signature, dict) and signature.get("signed") is True
    blockers = [{"id": "GATE", "text": r} for r in reasons] + ([] if signed else [{**SIGNING_BLOCKER, "status": (signature or {}).get("status", "unknown")}])
    return {"release_ready": ready, "signed": signed, "publishable": ready and signed, "blockers": blockers}


def build_manifest(meta, gates, signature):
    body = {"schema": SCHEMA, **meta, "gates": gates, "signature": signature, **evaluate(meta, gates, signature)}
    body["body_sha256"] = sha256_text(json.dumps(body, sort_keys=True, ensure_ascii=True))
    return body


def verify_manifest(manifest, head_sha, tree_clean=True):
    """Every reason this manifest may not be trusted for `head_sha`. The decision is recomputed; the stored flags are only compared."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        return ["not a release manifest of this schema"]
    problems = []
    body = {k: v for k, v in manifest.items() if k != "body_sha256"}
    if sha256_text(json.dumps(body, sort_keys=True, ensure_ascii=True)) != manifest.get("body_sha256"):
        problems.append("body hash does not match: the manifest was edited")
    if manifest.get("commit_sha") != head_sha:
        problems.append(f"manifest is for {manifest.get('commit_sha')!r}, checkout is {head_sha!r}")
    meta = {k: manifest.get(k) for k in ("commit_sha", "tree_clean", "elevated", "generated_at", "python", "platform")}
    again = evaluate(meta, manifest.get("gates") or {}, manifest.get("signature"))
    for key in ("release_ready", "signed", "publishable"):
        if manifest.get(key) != again[key]:
            problems.append(f"{key} is {manifest.get(key)!r} but the recorded gates give {again[key]!r}")
    return problems


# ---- collection (real work) -------------------------------------------------------------------------------------------------------

def _run(argv, cwd=ROOT, timeout=3600, env=None):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          env={**os.environ, **(env or {})}, shell=False)


def _git(*args):
    return _run(["git", *args]).stdout.strip()


def _tail(done, n=400):
    return (done.stdout + done.stderr).strip()[-n:]


def _command_gate(done):
    return {"status": "pass" if done.returncode == 0 else "fail", "detail": f"exit {done.returncode}", "tail": _tail(done)}


class _Recorder(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.outcomes = {}

    def _put(self, test, value):
        self.outcomes[test.id()] = value if self.outcomes.get(test.id()) in (None, "ok") else self.outcomes[test.id()]

    def addSuccess(self, test): super().addSuccess(test); self._put(test, "ok")
    def addFailure(self, test, err): super().addFailure(test, err); self.outcomes[test.id()] = "fail"
    def addError(self, test, err): super().addError(test, err); self.outcomes[test.id()] = "error"
    def addSkip(self, test, reason): super().addSkip(test, reason); self.outcomes[test.id()] = "skip"
    def addUnexpectedSuccess(self, test): super().addUnexpectedSuccess(test); self.outcomes[test.id()] = "fail"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes[test.id()] = "fail"


def suite_child(out_path):
    """Child process: run the whole suite and write per-test outcomes. A fresh process keeps the suite's HOME isolation out of the gate."""
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    with open(os.devnull, "w") as sink:
        result = unittest.TextTestRunner(stream=sink, verbosity=0, resultclass=_Recorder).run(suite)
    Path(out_path).write_text(json.dumps({"outcomes": result.outcomes, "ran": result.testsRun}), encoding="utf-8")
    return 0


def collect(out_path):
    sys.path.insert(0, str(ROOT))
    from respected_orchestrator.engine import appcontainer
    from respected_orchestrator import release_signature
    meta = {"commit_sha": _git("rev-parse", "HEAD"), "tree_clean": _git("status", "--porcelain") == "", "elevated": appcontainer._is_elevated(),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "python": sys.version.split()[0], "platform": sys.platform}
    gates, work = {}, Path(out_path).resolve().parent
    # 1. mandatory security matrix (ADR-017): its own validator, zero skips
    sec_path = work / "release-gate-security.json"
    done = _run([sys.executable, "tests/tools/run_security_ci.py", "run", str(sec_path)])
    gates["security_matrix"] = _command_gate(done)
    # 2. the whole suite, per-test outcomes; the P0 groups are judged from it
    suite_path = work / "release-gate-suite.json"
    done = _run([sys.executable, str(Path(__file__).resolve()), "_suite", str(suite_path)])
    try:
        recorded = json.loads(suite_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recorded = {"outcomes": {}, "ran": 0}
    bad = {k: v for k, v in recorded["outcomes"].items() if v in ("fail", "error")}
    skipped = sorted(k for k, v in recorded["outcomes"].items() if v == "skip")
    gates["full_suite"] = {"status": "pass" if done.returncode == 0 and recorded["ran"] > 0 and not bad else "fail",
                           "detail": f"{recorded['ran']} tests, {len(bad)} failing, {len(skipped)} skipped (outside P0 groups skips are listed, not fatal)",
                           "skipped": skipped, "failing": sorted(bad)[:20]}
    for name, prefixes in TEST_GROUPS.items():
        gates[name] = group_result(recorded["outcomes"], prefixes)
    # 3. the desktop shell
    npm = "npm.cmd" if os.name == "nt" else "npm"
    gates["desktop_check"] = _command_gate(_run([npm, "run", "check"], cwd=ROOT / "desktop"))
    # 4. packaged build: manifest hashes match the files; installer hash recorded
    gates["distribution_audit"] = _command_gate(_run([sys.executable, "packaging/build_dist.py", "--audit"]))
    installers = sorted((ROOT / "dist").glob("*Setup.exe"))
    if installers:
        digest = release_signature.sha256(installers[0])
        gates["installer_hash"] = {"status": "pass", "detail": installers[0].name, "sha256": digest}
        signature = release_signature.verify(installers[0], expected_sha256=digest, expected_signer=os.environ.get("RESPECTED_SIGN_SUBJECT") or "Respected")
    else:
        gates["installer_hash"] = {"status": "fail", "detail": "no dist/*Setup.exe: the installer was not built"}
        signature = {"signed": False, "status": "missing", "sha256": None}
    # 5. the roadmap itself: no other Beta.3 P0 card may be open
    open_p0, total = roadmap_open_p0((ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8"))
    gates["roadmap_p0"] = {"status": "fail" if open_p0 or total == 0 else "pass", "detail": f"open P0 cards: {open_p0}" if open_p0 else f"all P0 cards of {total} ticked (B3-09.04 excepted)",
                           "open": open_p0}
    manifest = build_manifest(meta, gates, signature)
    Path(out_path).write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: manifest[k] for k in ("commit_sha", "release_ready", "signed", "publishable")}, indent=1))
    for b in manifest["blockers"]:
        print("BLOCKER", b["id"], b["text"])
    return 0 if manifest["release_ready"] else 1


def verify(path):
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print("manifest unreadable:", error)
        return 1
    problems = verify_manifest(manifest, _git("rev-parse", "HEAD"))
    print("release gate verify:", "consistent" if not problems else "; ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    action, target = (sys.argv[1:3] + [None, None])[:2]
    handlers = {"collect": collect, "verify": verify, "_suite": suite_child}
    sys.exit(handlers[action](target) if action in handlers and target else print(__doc__) or 2)
