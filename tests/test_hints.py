import unittest

from respected_orchestrator import hints


class HintsTest(unittest.TestCase):
    def test_only_the_product_command_is_named(self):
        self.assertEqual(hints.hint("rorch memory connect"), "Şu komutu çalıştırın: rorch memory connect")


if __name__ == "__main__":
    unittest.main()
