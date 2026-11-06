"""B3-05.04: attacks on the approval center through the engine's real stdio protocol, one process per connection.

Same code path as the desktop shell: `_ipc` (renderer origin) and `_ipc --human` (native presence origin), each with its own
session token. Set RESPECTED_ATTACK_EXE to run the identical suite against the packaged executable.
Every attack must be rejected AND leave the project byte-identical; one legitimate path must apply exactly once.
"""
import hashlib
import json
import os
import secrets
import subprocess
import sys
import unittest
from pathlib import Path

from respected_orchestrator.engine.runner import create_task, execute_task
from respected_orchestrator.engine.evidence import load_signed, save_signed
from tests.workflows.test_reviewer_reliability import CodingFixture

SRC = Path(__file__).resolve().parents[2] / "src"
EXE = os.environ.get("RESPECTED_ATTACK_EXE")
OLD, NEW = "value = 0\n", "value = 1\n"


class Engine:
    """One engine process with its own token, spoken to the way the Rust shell does it."""

    def __init__(self, data_root, *args, token=None, extra_env=None):
        self.token = token or secrets.token_hex(24)
        env = {**os.environ, "RESPECTED_DATA_DIR": str(data_root), "RESPECTED_IPC_TOKEN": self.token, "PYTHONIOENCODING": "utf-8", **(extra_env or {})}
        env.pop("RESPECTED_ORCH_CHILD", None) if not (extra_env or {}).get("RESPECTED_ORCH_CHILD") else None
        cmd = [EXE, "_ipc", *args] if EXE else [sys.executable, "-m", "respected_orchestrator", "_ipc", *args]
        if not EXE:
            env["PYTHONPATH"] = str(SRC)
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env)
        self.n = 0
        self.transcript = []

    def call(self, cmd, payload=None, *, id=None, session=None):
        self.n += 1
        request = {"ipc": "1", "id": id or f"atk-{self.n:06d}", "session": self.token if session is None else session, "cmd": cmd, "payload": payload or {}}
        line = json.dumps(request)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        reply = self.proc.stdout.readline()
        self.transcript.append((line, reply))
        return json.loads(reply)

    def close(self):
        if getattr(self, "stderr", None) is not None:
            return
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except Exception:
            self.proc.kill()
        self.stderr = self.proc.stderr.read()
        self.proc.stderr.close()
        self.proc.stdout.close()


class ApprovalAttackTests(CodingFixture):
    def setUp(self):
        super().setUp()
        self.engines = []
        self.run_id = create_task(self.ctx, self.request())["run_id"]
        self.assertEqual(execute_task(self.ctx, self.run_id)["status"], "completed")
        self.addCleanup(lambda: [e.close() for e in self.engines])

    def engine(self, *args, **kwargs):
        e = Engine(self.ctx.data_root, *args, **kwargs)
        self.engines.append(e)
        return e

    def asker(self, **kw):
        return self.engine(**kw)

    def human(self, **kw):
        return self.engine("--human", **kw)

    def state(self):
        g = lambda *a: subprocess.run(["git", *a], cwd=self.repo, capture_output=True, text=True, check=True).stdout
        data = (self.repo / "calculator.py").read_bytes()
        return hashlib.sha256((g("rev-parse", "HEAD") + g("status", "--porcelain") + g("diff", "--cached")).encode() + data).hexdigest()

    def assert_rejected(self, reply, *codes):
        self.assertFalse(reply["ok"], reply)
        if codes:
            self.assertIn(reply["error"]["code"], codes, reply)

    def assert_untouched(self, before):
        self.assertEqual(self.state(), before)
        self.assertFalse((self.ctx.run_dir(self.run_id) / "applied.json").exists())

    def challenge(self, asker):
        reply = asker.call("approval.open", {"run_id": self.run_id})
        self.assertTrue(reply["ok"], reply)
        return reply["result"]

    # --- the attacker set (each is a separate, named case) -------------------------------------------------------

    def test_01_renderer_connection_cannot_decide(self):
        before, a = self.state(), self.asker()
        c = self.challenge(a)
        self.assert_rejected(a.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]}), "FORBIDDEN")
        self.assert_untouched(before)

    def test_02_renderer_connection_cannot_apply_even_with_a_stolen_token(self):
        before, a, h = self.state(), self.asker(), self.human()
        c = self.challenge(a)
        token = h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]})["result"]["token"]
        self.assert_rejected(a.call("approval.apply", {"token": token, "run_id": self.run_id}), "FORBIDDEN")
        self.assert_untouched(before)

    def test_03_orchestrated_process_cannot_pose_as_the_human(self):
        before, a = self.state(), self.asker()
        c = self.challenge(a)
        h = self.human(extra_env={"RESPECTED_ORCH_CHILD": "1"})
        self.assert_rejected(h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]}), "FORBIDDEN")
        self.assert_untouched(before)

    def test_04_wrong_or_missing_session_token_is_unauthenticated(self):
        before, h = self.state(), self.human()
        for session in ("x" * 48, "", " ", "t" * 5):
            self.assert_rejected(h.call("approval.decide", {"challenge_id": "chal-" + "0" * 16, "decision": "approve", "binding": "b"}, session=session), "UNAUTHENTICATED")
        self.assert_untouched(before)

    def test_05_human_connection_exposes_nothing_beyond_approval(self):
        h = self.human()
        for cmd in ("plan.start", "project.cancel", "settings.apply", "runs.list", "approval.open", "events.snapshot"):
            self.assert_rejected(h.call(cmd, {}), "FORBIDDEN")

    def test_06_wrong_run_id_gets_no_challenge(self):
        a = self.asker()
        for bad in ("run-20260101000000-aaaaaaaaaaaa", "run-../../x", "../run", "", None, 7, "run-" + "a" * 500):
            self.assert_rejected(a.call("approval.open", {"run_id": bad}), "ENGINE_ERROR")
        self.assertEqual(list(self.ctx.data_root.glob("approvals/*")), [])

    def test_07_patch_swapped_after_the_challenge_is_refused_at_decision_time(self):
        before, a, h = self.state(), self.asker(), self.human()
        c = self.challenge(a)
        (self.ctx.run_dir(self.run_id) / "worker.patch").write_text("diff --git a/calculator.py b/calculator.py\n+evil\n", encoding="utf8")
        self.assert_rejected(h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]}), "ENGINE_ERROR")
        self.assert_untouched(before)

    def test_08_forged_signed_patch_outside_the_grant_never_gets_a_challenge(self):
        before, a = self.state(), self.asker()
        directory = self.ctx.run_dir(self.run_id)
        for name, text in {"outside ownership": "diff --git a/evil.txt b/evil.txt\nnew file mode 100644\n--- /dev/null\n+++ b/evil.txt\n@@ -0,0 +1 @@\n+x\n",
                           "symlink": "diff --git a/calculator.py b/calculator.py\nnew file mode 120000\n--- /dev/null\n+++ b/calculator.py\n@@ -0,0 +1 @@\n+/etc/passwd\n",
                           "traversal": "diff --git a/../outside.txt b/../outside.txt\nnew file mode 100644\n--- /dev/null\n+++ b/../outside.txt\n@@ -0,0 +1 @@\n+x\n"}.items():
            (directory / "worker.patch").write_text(text, encoding="utf8", newline="\n")
            result = load_signed(self.ctx, directory / "result.json")
            save_signed(self.ctx, directory / "result.json", {**result, "patch_sha256": hashlib.sha256(text.encode()).hexdigest()})
            self.assert_rejected(a.call("approval.open", {"run_id": self.run_id}), "ENGINE_ERROR")
        self.assertEqual(list(self.ctx.data_root.glob("approvals/*")), [])
        self.assertFalse((self.repo / "evil.txt").exists() or (self.repo.parent / "outside.txt").exists())
        self.assert_untouched(before)

    def test_09_request_id_reuse_with_a_different_payload_is_a_conflict(self):
        a = self.asker()
        self.assertTrue(a.call("approval.open", {"run_id": self.run_id}, id="same-id-0001")["ok"])
        self.assert_rejected(a.call("approval.open", {"run_id": "run-20260101000000-bbbbbbbbbbbb"}, id="same-id-0001"), "REPLAY_CONFLICT")

    def test_10_replayed_decision_changes_nothing_a_second_time(self):
        a, h = self.asker(), self.human()
        c = self.challenge(a)
        decide = {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]}
        self.assertTrue(h.call("approval.decide", decide)["ok"])
        self.assert_rejected(h.call("approval.decide", decide), "ENGINE_ERROR")
        self.assertEqual(len(list(self.ctx.data_root.glob("approvals/grant-*.json"))), 1)

    def test_11_replayed_token_cannot_apply_twice(self):
        a, h = self.asker(), self.human()
        c = self.challenge(a)
        token = h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]})["result"]["token"]
        self.assertTrue(h.call("approval.apply", {"token": token, "run_id": self.run_id})["ok"])
        after = self.state()
        self.assert_rejected(h.call("approval.apply", {"token": token, "run_id": self.run_id}), "ENGINE_ERROR")
        self.assertEqual(self.state(), after)

    def test_12_forged_and_malformed_tokens_and_ids_are_rejected(self):
        before, h = self.state(), self.human()
        for token in (secrets.token_hex(32), "0" * 64, "../../etc/passwd", "A" * 64, "", None, 5, "f" * 63):
            self.assert_rejected(h.call("approval.apply", {"token": token, "run_id": self.run_id}), "ENGINE_ERROR")
        for cid in ("../x", "chal-" + "z" * 16, "chal-" + "0" * 16 + "\n", None, 3):
            self.assert_rejected(h.call("approval.decide", {"challenge_id": cid, "decision": "approve", "binding": "b"}), "ENGINE_ERROR")
        self.assert_untouched(before)

    def test_13_binding_of_another_challenge_is_a_wrong_window(self):
        before, a, h = self.state(), self.asker(), self.human()
        first, second = self.challenge(a), self.challenge(a)
        self.assert_rejected(h.call("approval.decide", {"challenge_id": first["challenge_id"], "decision": "approve", "binding": second["binding"]}), "ENGINE_ERROR")
        self.assert_untouched(before)

    def test_14_token_for_one_run_cannot_apply_another(self):
        before, a, h = self.state(), self.asker(), self.human()
        c = self.challenge(a)
        token = h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]})["result"]["token"]
        self.assert_rejected(h.call("approval.apply", {"token": token, "run_id": "run-20260101000000-cccccccccccc"}), "ENGINE_ERROR")
        self.assert_untouched(before)

    def test_15_oversized_and_garbage_requests_are_refused_cleanly(self):
        before, a = self.state(), self.asker()
        self.assert_rejected(a.call("approval.open", {"run_id": "x" * 70000}), "PAYLOAD_TOO_LARGE")
        for raw in ("not json", "[]", '{"ipc":"1"}'):
            a.proc.stdin.write(raw + "\n")
            a.proc.stdin.flush()
            self.assertFalse(json.loads(a.proc.stdout.readline())["ok"])
        self.assertTrue(a.call("hello")["ok"])  # still serving
        self.assert_untouched(before)

    def test_16_denial_applies_nothing_and_cannot_be_flipped(self):
        before, a, h = self.state(), self.asker(), self.human()
        c = self.challenge(a)
        self.assertEqual(h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "deny", "binding": c["binding"]})["result"]["state"], "denied")
        self.assert_rejected(h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]}), "ENGINE_ERROR")
        self.assert_untouched(before)

    def test_17_crash_between_decision_and_apply_never_auto_applies(self):
        before, a, h = self.state(), self.asker(), self.human()
        c = self.challenge(a)
        self.assertTrue(h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]})["ok"])
        h.proc.kill()  # the presence process dies holding the token
        h.proc.wait()
        self.assert_untouched(before)  # nothing applies on its own
        again = self.human()  # a fresh presence process has no token and cannot guess one
        self.assert_rejected(again.call("approval.apply", {"token": secrets.token_hex(32), "run_id": self.run_id}), "ENGINE_ERROR")
        self.assert_untouched(before)

    def test_19_token_burned_by_a_failed_apply_cannot_be_replayed_after_the_attacker_restores_the_state(self):
        a, h = self.asker(), self.human()
        c = self.challenge(a)
        token = h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]})["result"]["token"]
        (self.repo / "calculator.py").write_text("value = 7\n", encoding="utf8")  # the project moves, the apply is refused ...
        self.assert_rejected(h.call("approval.apply", {"token": token, "run_id": self.run_id}), "ENGINE_ERROR")
        (self.repo / "calculator.py").write_text(OLD, encoding="utf8")  # ... then it is put back exactly as approved
        before = self.state()
        again = h.call("approval.apply", {"token": token, "run_id": self.run_id})
        self.assert_rejected(again, "ENGINE_ERROR")
        self.assertIn("already used", again["error"]["message"])
        self.assert_untouched(before)

    def test_18_the_legitimate_path_applies_once_and_nothing_secret_is_left_behind(self):
        a, h = self.asker(), self.human()
        c = self.challenge(a)
        granted = h.call("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]})["result"]
        out = h.call("approval.apply", {"token": granted["token"], "run_id": self.run_id})
        self.assertTrue(out["ok"], out)
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), NEW)
        self.assertEqual(out["result"]["committed"], False)
        self.assert_rejected(h.call("approval.apply", {"token": granted["token"], "run_id": self.run_id}), "ENGINE_ERROR")
        for e in (a, h):
            e.close()
        secrets_seen = [granted["token"], a.token, h.token]
        leaks = []
        for path in self.ctx.data_root.rglob("*"):
            if path.is_file():
                blob = path.read_bytes().decode("utf8", errors="replace")
                leaks += [(path.name, s[:6]) for s in secrets_seen if s in blob]
        self.assertEqual(leaks, [])  # no log, journal, evidence or approval record holds a token
        self.assertNotIn(granted["token"], "".join(r for _, r in a.transcript) + a.stderr + h.stderr)  # the asker side never sees it
        self.assertEqual(a.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
