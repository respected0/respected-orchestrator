import unittest

from respected_orchestrator.interfaces import rpp


class PreviewSettingsTests(unittest.TestCase):
    def test_preview_is_off_by_default_with_no_ports(self):
        defaults = rpp._defaults()
        self.assertIs(defaults["preview_enabled"], False)
        self.assertEqual(defaults["preview_ports"], "")
        keys = {f["key"] for f in rpp.schema_fields()}
        self.assertLessEqual({"preview_enabled", "preview_ports"}, keys)

    def test_port_lists_are_validated_strictly(self):
        for ok in ("", "  ", "3000", "3000, 5173", "1024", "65535", ",".join(str(p) for p in range(3000, 3008))):
            self.assertIsNone(rpp.preview_ports_error(ok), ok)
        for bad in ("80", "1023", "65536", "abc", "3000,", ",3000", "3000,3000", "3000;5173", "-3000", "3000.5", "٣٠٠٠",
                    ",".join(str(p) for p in range(3000, 3009)), "0x1f90", "3000 5173"):
            self.assertTrue(rpp.preview_ports_error(bad), repr(bad))

    def test_settings_validation_uses_it_and_types_are_checked(self):
        self.assertEqual(rpp.validate_settings({"preview_enabled": True, "preview_ports": "5173"}), [])
        self.assertEqual([e["key"] for e in rpp.validate_settings({"preview_ports": "22"})], ["preview_ports"])
        self.assertEqual([e["key"] for e in rpp.validate_settings({"preview_enabled": "yes"})], ["preview_enabled"])
        self.assertEqual([e["key"] for e in rpp.validate_settings({"preview_ports": 5173})], ["preview_ports"])


if __name__ == "__main__":
    unittest.main()
