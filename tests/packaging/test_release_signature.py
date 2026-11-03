"""REL-01: release artifacts are signed only when every Authenticode condition holds."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from respected_orchestrator import release_signature as sig


def result(data, code=0):
    return SimpleNamespace(returncode=code, stdout=json.dumps(data).encode(), stderr=b"")


class ReleaseSignatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.exe = Path(self.temp.name) / "setup.exe"
        self.exe.write_bytes(b"installer payload")

    def verify(self, data=None, **kwargs):
        run = kwargs.pop("run", None) or (lambda *a, **k: result(data or {}))
        with mock.patch.object(sig.os, "name", "nt"):
            return sig.verify(self.exe, run=run, **kwargs)

    def test_valid_expected_signature_is_signed(self):
        got = self.verify({"Status": "Valid", "Message": "ok", "Subject": "CN=Respected, O=Respected",
                           "NotAfter": "2099-01-01T00:00:00+00:00"}, expected_signer="Respected")
        self.assertEqual((got["signed"], got["status"]), (True, "signed"))

    def test_changed_payload_is_rejected_before_signature(self):
        got = self.verify(expected_sha256="0" * 64)
        self.assertEqual((got["signed"], got["status"]), (False, "tampered"))

    def test_wrong_signer_is_rejected(self):
        got = self.verify({"Status": "Valid", "Subject": "CN=Attacker", "NotAfter": "2099-01-01T00:00:00+00:00"},
                          expected_signer="Respected")
        self.assertEqual(got["status"], "wrong_signer")

    def test_expired_certificate_is_not_signed(self):
        got = self.verify({"Status": "Valid", "Subject": "CN=Respected", "NotAfter": "2000-01-01T00:00:00+00:00"},
                          expected_signer="Respected")
        self.assertEqual(got["status"], "cert_expired")

    def test_unsigned_and_offline_are_not_signed(self):
        self.assertEqual(self.verify({"Status": "NotSigned", "Message": "no signature"})["status"], "unsigned")
        def broken(*a, **k):
            raise OSError("powershell unavailable")
        with mock.patch.object(sig.os, "name", "nt"):
            got = sig.verify(self.exe, run=broken)
        self.assertEqual((got["signed"], got["status"]), (False, "offline_or_unknown"))

    def test_signing_key_never_comes_from_the_repository(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "RESPECTED_SIGN_CERT"):
                sig.sign(self.exe)


if __name__ == "__main__":
    unittest.main()