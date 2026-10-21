"""The private JSON entry point (__main__.main): argument errors, dispatch and the error envelope."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator import __main__ as cli
from respected_orchestrator.workflows import planner, roles


def call(*argv, stdin=""):
    out = io.StringIO()
    with mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin.encode()))), contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class MainTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = ["--data-root", str(Path(temp.name))]

    def test_status_list_and_roles_dry_run(self):
        code, text = call(*self.root, "status")
        self.assertEqual((code, json.loads(text)["product"]), (0, "respected-orchestrator"))
        self.assertEqual(call(*self.root, "list")[0], 0)
        code, text = call(*self.root, "roles", stdin='{"roles": {}, "needed": ["implementer"]}')
        self.assertIn("assignments", json.loads(text))

    def test_run_commands_need_exactly_one_identity(self):
        code, text = call(*self.root, "inspect")
        self.assertEqual(code, 1)
        self.assertIn("run identity", json.loads(text)["error"])

    def test_errors_become_a_json_envelope(self):
        code, text = call(*self.root, "create", stdin="not json")
        self.assertEqual(code, 1)
        self.assertIn("error", json.loads(text))
        error = roles.RoleError("ROLE_UNAVAILABLE", "nope", "fix it")
        with mock.patch.object(planner, "plan", side_effect=error):
            code, text = call(*self.root, "plan", stdin="{}")
        self.assertEqual((code, json.loads(text)["code"], json.loads(text)["hint"]), (1, "ROLE_UNAVAILABLE", "fix it"))

    def test_dispatch_to_subsystems(self):
        with mock.patch("respected_orchestrator.interfaces.rpp.run", return_value=5) as rpp:
            self.assertEqual(call(*self.root, "rpp")[0], 5)
        rpp.assert_called_once()
        with mock.patch("respected_orchestrator.interfaces.mcp_server.serve", return_value=0) as serve:
            call(*self.root, "mcp", "--allow-auto-apply")
        self.assertEqual(serve.call_args.kwargs, {"allow_auto_apply": True, "allow_privileged": False})
        with mock.patch("respected_orchestrator.engine.sandbox_exec", create=True) as launcher:
            launcher.main.return_value = 3
            self.assertEqual(call("_sandbox-exec", "--sid", "S")[0], 3)
        with mock.patch("respected_orchestrator.workflows.campaign.list_campaigns", return_value={"campaigns": []}):
            self.assertEqual(json.loads(call(*self.root, "campaign-list")[1]), {"campaigns": []})


if __name__ == "__main__":
    unittest.main()
