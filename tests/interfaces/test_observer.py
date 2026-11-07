import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.journal import Journal
from respected_orchestrator.interfaces import observer as ob

HUMAN = Origin.HUMAN


def code_of(fn, *a, **k):
    try:
        fn(*a, **k)
    except ob.ObserverError as error:
        return error.code


class ObserverTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ctx = EngineContext(Path(temp.name).resolve() / "data")
        self.t = [1000.0]
        self.obs = ob.Observer(self.ctx, clock=lambda: self.t[0])
        d = self.ctx.run_dir("run-20261108000000-abcdef123456")
        d.mkdir(parents=True)
        save_signed(self.ctx, d / "request.json", {"task": "t", "worker": "codex", "kind": "write"})
        save_signed(self.ctx, d / "status.json", {"status": "queued"})
        Journal(self.ctx.state_dir / "events.log").append("op1", "x.y", "run-20261108000000-abcdef123456", {"api_token": "SECRET", "note": "ok"})

    def pair(self, name="phone"):
        code = self.obs.open_pairing(origin=HUMAN)["code"]
        return self.obs.pair(code, name)

    def login(self):
        creds = self.pair()
        return creds, self.obs.token(creds["device_id"], creds["secret"])["token"]

    def test_nothing_exists_by_default(self):
        self.assertFalse((self.ctx.data_root / "observer").exists())
        self.assertEqual(self.obs.handle("GET", "/status", None)[0], 401)

    def test_pairing_needs_a_human_at_the_machine(self):
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                self.obs.open_pairing(origin=origin)

    def test_codes_are_single_use_short_lived_and_wrong_ones_burn_the_attempt(self):
        code = self.obs.open_pairing(origin=HUMAN)["code"]
        self.assertEqual(len(code), 8)
        self.obs.pair(code, "a")
        self.assertEqual(code_of(self.obs.pair, code, "b"), "BAD_CODE")  # replay
        code = self.obs.open_pairing(origin=HUMAN)["code"]
        self.t[0] += ob.PAIR_SECONDS + 1
        self.assertEqual(code_of(self.obs.pair, code, "late"), "BAD_CODE")
        code = self.obs.open_pairing(origin=HUMAN)["code"]
        self.assertEqual(code_of(self.obs.pair, "WRONGCODE", "x"), "BAD_CODE")
        self.assertEqual(code_of(self.obs.pair, code, "x"), "BAD_CODE")  # the right code no longer works once a guess was made

    def test_guessing_is_locked_out(self):
        for _ in range(ob.MAX_FAILS):
            self.obs.open_pairing(origin=HUMAN)
            code_of(self.obs.pair, "AAAAAAAA", "x")
        self.obs.open_pairing(origin=HUMAN)
        self.assertEqual(code_of(self.obs.pair, "AAAAAAAA", "x"), "LOCKED")
        self.assertEqual(code_of(self.obs.token, "dev-x", "y"), "LOCKED")
        self.t[0] += ob.LOCKOUT_SECONDS + 1
        self.assertEqual(code_of(self.obs.pair, "AAAAAAAA", "x"), "BAD_CODE")

    def test_secrets_and_tokens_are_never_stored_in_clear(self):
        creds, token = self.login()
        stored = (self.ctx.data_root / "observer" / "devices.json").read_text("utf-8")
        self.assertNotIn(creds["secret"], stored)
        self.assertNotIn(token, stored)
        self.assertIn("secret_hash", stored)

    def test_read_endpoints_work_and_are_masked(self):
        creds, token = self.login()
        status, body = self.obs.handle("GET", "/status", token)
        self.assertEqual((status, body["sampled"], sum(body["runs_by_state"].values())), (200, 1, 1))  # the minimal fixture run is honestly "invalid" to the read model
        status, body = self.obs.handle("GET", "/runs?limit=5", token)
        self.assertEqual((status, body["runs"][0]["run_id"]), (200, "run-20261108000000-abcdef123456"))
        status, body = self.obs.handle("GET", "/events?after=0", token)
        self.assertEqual(status, 200)
        self.assertEqual(body["events"][0]["p"], {"api_token": "[redacted]", "note": "ok"})
        self.assertEqual(self.obs.handle("GET", "/events?after=abc", token)[0], 400)

    def test_every_attempt_to_change_something_is_refused(self):
        creds, token = self.login()
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            for path in ("/status", "/runs", "/start", "/approve", "/apply", "/settings", "/runs/run-x/cancel"):
                self.assertEqual(self.obs.handle(method, path, token)[0], 405, (method, path))
        for path in ("/start", "/apply", "/settings", "/../../etc/passwd", "/runs/../x", "/evidence/run-1", ""):
            self.assertEqual(self.obs.handle("GET", path, token)[0], 404, path)
        self.assertEqual(len(list((self.ctx.state_dir).glob("run-*"))), 1)  # nothing was created

    def test_bad_tokens(self):
        creds, token = self.login()
        for bad in (None, "", "x", token + "x", token[:-1], 5):
            self.assertEqual(self.obs.handle("GET", "/status", bad)[0], 401, bad)
        self.t[0] += ob.TOKEN_SECONDS + 1
        self.assertEqual(self.obs.handle("GET", "/status", token)[0], 401)  # short-lived
        self.assertEqual(code_of(self.obs.token, creds["device_id"], "wrong"), "BAD_CREDENTIALS")
        self.assertEqual(code_of(self.obs.token, "dev-unknown", creds["secret"]), "BAD_CREDENTIALS")
        self.assertTrue(self.obs.token(creds["device_id"], creds["secret"])["token"])

    def test_revoked_device_loses_everything_at_once(self):
        creds, token = self.login()
        other_creds, other_token = self.login()
        for origin in (Origin.WORKER, Origin.MCP, Origin.RENDERER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                self.obs.revoke(creds["device_id"], origin=origin)
        self.assertTrue(self.obs.revoke(creds["device_id"], origin=HUMAN))
        self.assertEqual(self.obs.handle("GET", "/status", token)[0], 401)  # the live token died with the device
        self.assertEqual(code_of(self.obs.token, creds["device_id"], creds["secret"]), "BAD_CREDENTIALS")
        self.assertEqual(self.obs.handle("GET", "/status", other_token)[0], 200)  # others are unaffected
        self.assertFalse(self.obs.revoke(creds["device_id"], origin=HUMAN))

    def test_stolen_device_secret_is_useless_after_revocation_even_with_a_fresh_observer(self):
        creds, token = self.login()
        self.obs.revoke(creds["device_id"], origin=HUMAN)
        restarted = ob.Observer(self.ctx, clock=lambda: self.t[0])
        self.assertEqual(code_of(restarted.token, creds["device_id"], creds["secret"]), "BAD_CREDENTIALS")
        self.assertEqual(restarted.handle("GET", "/status", token)[0], 401)  # tokens are memory-only: a restart drops them all

    def test_device_limit(self):
        for i in range(ob.MAX_DEVICES):
            self.pair(f"d{i}")
        self.assertEqual(code_of(self.obs.open_pairing, origin=HUMAN), "TOO_MANY_DEVICES")

    def test_no_remote_listener_can_be_created(self):
        for host in ("0.0.0.0", "192.168.1.5", "example.com", "::", ""):
            self.assertEqual(code_of(ob.serve, self.obs, host, 0, origin=HUMAN), "NO_REMOTE_LISTENER", host)
        with self.assertRaises(PermissionError):
            ob.serve(self.obs, "127.0.0.1", 0, origin=Origin.WORKER)

    def test_loopback_server_end_to_end_is_read_only(self):
        creds, token = self.login()
        server = ob.serve(self.obs, "127.0.0.1", 0, origin=HUMAN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close()))
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def call(method, path, bearer=None, data=None):
            request = urllib.request.Request(base + path, method=method, data=data, headers={"Authorization": f"Bearer {bearer}"} if bearer else {})
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    return response.status, json.loads(response.read())
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read())
        self.assertEqual(call("GET", "/status")[0], 401)
        self.assertEqual(call("GET", "/status", token)[0], 200)
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertEqual(call(method, "/runs", token, b"{}")[0], 405, method)
        self.obs.revoke(creds["device_id"], origin=HUMAN)
        self.assertEqual(call("GET", "/status", token)[0], 401)

    def test_the_module_can_only_read(self):
        source = (Path(ob.__file__)).read_text("utf-8")
        imports = [line for line in source.splitlines() if line.startswith(("from ", "import "))]
        self.assertFalse([line for line in imports if any(w in line for w in ("runner", "approval", "project", "campaign", "maintenance", "subprocess", "winproc"))], imports)


if __name__ == "__main__":
    unittest.main()
