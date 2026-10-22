import unittest
from unittest import mock

from respected_orchestrator import hints


class HintsTest(unittest.TestCase):
    def test_without_the_hub_only_the_product_command_is_named(self):
        with mock.patch.object(hints, "hub_installed", return_value=False):
            self.assertEqual(hints.hint("Hub'da açın", "respected-orchestrator memory connect"), "Şu komutu çalıştırın: respected-orchestrator memory connect")

    def test_with_the_hub_both_ways_are_named(self):
        with mock.patch.object(hints, "hub_installed", return_value=True):
            self.assertEqual(hints.hint("Hub'da açın", "respected-orchestrator memory connect"), "Hub'da açın; ya da: respected-orchestrator memory connect")


if __name__ == "__main__":
    unittest.main()
