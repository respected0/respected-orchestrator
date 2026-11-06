import unittest

from respected_orchestrator.engine.authority import Action, Grant, Origin, authorize, check_grant, effective_origin

OK = {
    Origin.HUMAN: set(Action),
    Origin.RENDERER: {Action.READ, Action.TASK, Action.SETTINGS},
    Origin.MCP: {Action.READ, Action.TASK},
    Origin.WORKER: set(),
    Origin.CHILD: set(),
}


class AuthorityTests(unittest.TestCase):
    def test_full_role_matrix(self):
        for origin in Origin:
            for action in Action:
                if action in OK[origin]:
                    authorize(origin, action)
                else:
                    with self.assertRaises(PermissionError, msg=(origin, action)):
                        authorize(origin, action)

    def test_only_a_human_can_approve_or_apply(self):
        privileged = [o for o in Origin if Action.PRIVILEGED in OK[o]]
        self.assertEqual(privileged, [Origin.HUMAN])

    def test_child_environment_demotes_any_claimed_origin(self):
        self.assertIs(effective_origin(Origin.HUMAN, {"RESPECTED_ORCH_CHILD": "1"}), Origin.CHILD)
        self.assertIs(effective_origin(Origin.HUMAN, {}), Origin.HUMAN)
        with self.assertRaises(PermissionError):
            authorize(effective_origin(Origin.HUMAN, {"RESPECTED_ORCH_CHILD": "1"}), Action.PRIVILEGED)

    def test_grant_binds_scope_run_and_patch_and_is_single_use(self):
        g = Grant("apply", "run-1", "abc", "n1")
        used = set()
        kw = dict(scope="apply", run_id="run-1", patch_sha256="abc")
        for bad in (dict(kw, scope="settings"), dict(kw, run_id="run-2"), dict(kw, patch_sha256="def")):
            with self.assertRaises(ValueError):
                check_grant(g, used_nonces=used, **bad)
        self.assertEqual(used, set())  # failed checks must not burn the nonce
        check_grant(g, used_nonces=used, **kw)
        with self.assertRaises(ValueError):  # replay
            check_grant(g, used_nonces=used, **kw)


if __name__ == "__main__":
    unittest.main()
