"""REL-03: the six first-run scenarios get actionable, non-privileged guidance."""
import unittest

from respected_orchestrator.interfaces import health_wizard


def check(name, ok):
    return {"name": name, "ok": ok, "detail": ""}


class HealthWizardTests(unittest.TestCase):
    def guide(self, **failed):
        names = ("data_root_writable", "git_available", "worker_cli", "engine_key")
        return health_wizard.guide([check(name, not failed.get(name, False)) for name in names], "/data")

    def test_git_missing(self):
        self.assertEqual(self.guide(git_available=True)["steps"][0]["action"], "install_git")

    def test_worker_cli_missing(self):
        self.assertEqual(self.guide(worker_cli=True)["steps"][0]["action"], "install_or_sign_in_worker")

    def test_wrong_permission(self):
        self.assertEqual(self.guide(data_root_writable=True)["steps"][0]["action"], "data_root_permissions")

    def test_hub_absent_core_still_works(self):
        got = health_wizard.guide([check("git_available", True)], "/data", hub_installed=False)
        self.assertEqual((got["hub_required"], got["hub_installed"]), (False, False))

    def test_uninstall_keeps_data_unless_purged(self):
        got = self.guide()
        self.assertEqual(got["uninstall"], {"keeps_data": True, "purge_flag": "--purge"})

    def test_sample_task_is_read_only(self):
        sample = self.guide()["sample_task"]
        self.assertEqual((sample["mode"], sample["writes"]), ("read", False))


if __name__ == "__main__":
    unittest.main()