import unittest

from respected_orchestrator.engine.provider_policy import ProviderDenied, redact_secret, require_access

OPT_IN = {"RESPECTED_PROVIDER_NETWORK": "allow", "RESPECTED_PROVIDER_CODE_GATE": "1"}


class ProviderPolicyTests(unittest.TestCase):
    def test_opt_in_off_denies_before_any_request(self):
        with self.assertRaises(ProviderDenied):
            require_access("https://openrouter.ai/api/v1", {"openrouter.ai"}, {})

    def test_code_gate_off_denies_live_provider(self):
        with self.assertRaises(ProviderDenied):
            require_access("https://openrouter.ai/api/v1", {"openrouter.ai"},
                           {"RESPECTED_PROVIDER_NETWORK": "allow"})

    def test_denied_domain_is_rejected(self):
        with self.assertRaises(ProviderDenied):
            require_access("https://evil.example/api", {"openrouter.ai"}, OPT_IN)

    def test_redirect_target_must_pass_the_same_gate(self):
        require_access("https://openrouter.ai/api/v1", {"openrouter.ai"}, OPT_IN)
        with self.assertRaises(ProviderDenied):
            require_access("https://evil.example/steal", {"openrouter.ai"}, OPT_IN)

    def test_http_proxy_or_credentials_in_url_are_rejected(self):
        with self.assertRaises(ProviderDenied):
            require_access("http://openrouter.ai/api", {"openrouter.ai"}, OPT_IN)
        with self.assertRaises(ProviderDenied):
            require_access("https://key:secret@openrouter.ai/api", {"openrouter.ai"}, OPT_IN)

    def test_secret_is_redacted_before_logging(self):
        self.assertEqual(redact_secret("Authorization: Bearer sk-live-1", "sk-live-1"),
                         "Authorization: Bearer ***set***")
        self.assertEqual(redact_secret("nothing here", ""), "nothing here")


if __name__ == "__main__":
    unittest.main()
