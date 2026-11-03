"""REL-04: ten security fixtures gate every platform; POSIX stays out of GA until parity is proven."""
import unittest

from respected_orchestrator import release_platform

PASSING = {name: "pass" for name in release_platform.REQUIRED_FIXTURES}


class ReleasePlatformTests(unittest.TestCase):
    def test_windows_with_all_ten_fixtures_is_go(self):
        got = release_platform.decide("windows", PASSING)
        self.assertEqual((got["release"], got["ga"], got["fixtures"]), ("go", True, 10))

    def test_one_red_fixture_blocks_release(self):
        fixtures = dict(PASSING, symlink="fail")
        got = release_platform.decide("windows", fixtures)
        self.assertEqual((got["release"], got["red"]), ("no-go", ["symlink"]))

    def test_missing_fixture_blocks_release(self):
        got = release_platform.decide("windows", {name: "pass" for name in release_platform.REQUIRED_FIXTURES[:-1]})
        self.assertEqual(got["release"], "no-go")

    def test_each_security_family_can_block(self):
        for name in release_platform.REQUIRED_FIXTURES:
            with self.subTest(name=name):
                self.assertEqual(release_platform.decide("windows", dict(PASSING, **{name: "fail"}))["release"], "no-go")

    def test_linux_even_with_all_fixtures_stays_no_go(self):
        got = release_platform.decide("linux", PASSING)
        self.assertEqual((got["release"], got["ga"]), ("no-go", False))

    def test_macos_even_with_all_fixtures_stays_no_go(self):
        got = release_platform.decide("darwin", PASSING)
        self.assertEqual((got["release"], got["ga"]), ("no-go", False))


if __name__ == "__main__":
    unittest.main()