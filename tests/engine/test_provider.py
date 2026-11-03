import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.engine.provider import ProviderClient, ProviderError
from respected_orchestrator.engine.secret_vault import SecretVault

ENV = {"RESPECTED_PROVIDER_NETWORK": "allow", "RESPECTED_PROVIDER_CODE_GATE": "1"}


class Vault:
    def __init__(self, secret="sk-test"):
        self.secret = secret

    def load(self):
        return self.secret


def transport(status, payload=None, calls=None):
    def call(method, url, body, headers, timeout):
        if calls is not None:
            calls.append((method, url))
        return status, json.dumps(payload if payload is not None else {}).encode()
    return call


def ok(content="ok", usage=None):
    payload = {"model": "m", "choices": [{"message": {"content": content}}]}
    if usage is not None:
        payload["usage"] = usage
    return payload


class ProviderTests(unittest.TestCase):
    def client(self, transport_fn, vault=None):
        return ProviderClient(vault=vault or Vault(), environ=ENV, transport=transport_fn)

    def test_200_completes_and_preserves_known_usage(self):
        client = self.client(transport(200, ok("done", {"total_tokens": 7})))
        result = client.complete(model="m", messages=[], idempotency_key="one")
        self.assertEqual((result["status"], result["content"], result["usage_status"]),
                         ("completed", "done", "KNOWN"))

    def test_unknown_usage_stays_unknown(self):
        client = self.client(transport(200, ok()))
        result = client.complete(model="m", messages=[], idempotency_key="one")
        self.assertEqual((result["usage"], result["usage_status"]), (None, "UNKNOWN"))

    def test_401_and_429_do_not_fallback(self):
        for status, kind in ((401, "unauthorized"), (429, "rate_limited")):
            calls = []
            client = self.client(transport(status, calls=calls))
            with self.assertRaises(ProviderError) as caught:
                client.complete(model="m", messages=[], idempotency_key="one")
            self.assertEqual((caught.exception.kind, len(calls)), (kind, 1))

    def test_500_is_provider_error(self):
        client = self.client(transport(500))
        with self.assertRaises(ProviderError) as caught:
            client.complete(model="m", messages=[], idempotency_key="one")
        self.assertEqual(caught.exception.kind, "provider_error")

    def test_timeout_is_distinct(self):
        def timed_out(*args, **kwargs):
            raise ProviderError("timeout", retryable=True)
        client = self.client(timed_out)
        with self.assertRaises(ProviderError) as caught:
            client.complete(model="m", messages=[], idempotency_key="one")
        self.assertEqual(caught.exception.kind, "timeout")

    def test_partial_stream_fails(self):
        chunks = iter([b'data: {"choices":[{"delta":{"content":"par"}}]}\n\n'])
        client = self.client(transport(200, ok()))
        with self.assertRaises(ProviderError) as caught:
            client.complete_stream(model="m", messages=[], idempotency_key="one", stream=lambda *a: chunks)
        self.assertEqual(caught.exception.kind, "stream_incomplete")

    def test_complete_stream_needs_done(self):
        chunks = iter([b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'])
        client = self.client(transport(200, ok()))
        result = client.complete_stream(model="m", messages=[], idempotency_key="one", stream=lambda *a: chunks)
        self.assertEqual((result["status"], result["content"]), ("completed", "hi"))

    def test_idempotent_key_sends_once(self):
        calls = []
        client = self.client(transport(200, ok("done"), calls=calls))
        first = client.complete(model="m", messages=[], idempotency_key="same")
        second = client.complete(model="m", messages=[], idempotency_key="same")
        self.assertEqual((first, second, len(calls)), (first, first, 1))

    def test_missing_key_fails_before_transport(self):
        calls = []
        client = self.client(transport(200, ok(), calls=calls), vault=Vault(secret=None))
        with self.assertRaises(ProviderError) as caught:
            client.complete(model="m", messages=[], idempotency_key="one")
        self.assertEqual((caught.exception.kind, len(calls)), ("auth_missing", 0))

    def test_models_uses_same_gate(self):
        payload = {"data": [{"id": "b"}, {"id": "a"}]}
        client = self.client(transport(200, payload))
        self.assertEqual(client.models(), ["a", "b"])

    def test_vault_encrypts_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key.dpapi"
            vault = SecretVault(path)
            vault.store("sk-plaintext")
            self.assertEqual(vault.load(), "sk-plaintext")
            self.assertNotIn(b"sk-plaintext", path.read_bytes())


if __name__ == "__main__":
    unittest.main()
