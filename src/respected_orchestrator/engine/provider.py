"""OpenRouter adapter with gated egress, honest errors and idempotent calls (ADP-03).

Every request passes :func:`provider_policy.require_access` before the transport runs. 401, 429, 5xx, timeouts and
truncated streams are distinct failures; none of them falls back to another provider or model.
"""

import json
import socket
import urllib.error
import urllib.request

from .provider_policy import require_access

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
ALLOWED_DOMAINS = ("openrouter.ai",)
DEFAULT_TIMEOUT = 30.0


class ProviderError(RuntimeError):
    def __init__(self, kind, *, status=None, retryable=False):
        super().__init__(kind)
        self.kind = kind
        self.status = status
        self.retryable = retryable


def _http(method, url, body, headers, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (TimeoutError, socket.timeout) as error:
        raise ProviderError("timeout", retryable=True) from error
    except urllib.error.URLError as error:
        kind = "timeout" if isinstance(error.reason, (TimeoutError, socket.timeout)) else "network"
        raise ProviderError(kind, retryable=True) from error


class ProviderClient:
    def __init__(self, *, vault=None, environ=None, transport=_http):
        self._vault = vault
        self._environ = environ
        self._transport = transport
        self._results = {}

    def _gate(self, url):
        return require_access(url, ALLOWED_DOMAINS, self._environ)

    def _headers(self):
        secret = self._vault.load() if self._vault is not None else None
        if not secret:
            raise ProviderError("auth_missing")
        return {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}

    @staticmethod
    def _check(status):
        if status == 401:
            raise ProviderError("unauthorized", status=status)
        if status == 429:
            raise ProviderError("rate_limited", status=status, retryable=True)
        if status >= 500:
            raise ProviderError("provider_error", status=status, retryable=True)
        if status != 200:
            raise ProviderError("http_error", status=status)

    def complete(self, *, model, messages, idempotency_key, timeout=DEFAULT_TIMEOUT):
        key = (idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency_key is required")
        if key in self._results:
            return self._results[key]
        self._gate(API_URL)
        headers = self._headers()
        body = json.dumps({"model": model, "messages": messages}).encode("utf-8")
        status, raw = self._transport("POST", API_URL, body, headers, timeout)
        self._check(status)
        try:
            payload = json.loads(raw)
            message = payload["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ProviderError("invalid_response", status=status) from error
        usage = payload.get("usage")
        known = isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int)
        result = {"status": "completed", "content": message.get("content"),
                  "model": payload.get("model", model), "usage": usage if known else None,
                  "usage_status": "KNOWN" if known else "UNKNOWN"}
        self._results[key] = result
        return result

    def complete_stream(self, *, model, messages, idempotency_key, stream, timeout=DEFAULT_TIMEOUT):
        """Consume SSE events; a stream without a final [DONE] is incomplete, never a success."""
        key = (idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency_key is required")
        if key in self._results:
            return self._results[key]
        self._gate(API_URL)
        headers = self._headers()
        body = json.dumps({"model": model, "messages": messages, "stream": True}).encode("utf-8")
        content = []
        done = False
        for chunk in stream("POST", API_URL, body, headers, timeout):
            for line in chunk.decode("utf-8", "replace").splitlines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    continue
                try:
                    delta = json.loads(data)["choices"][0]["delta"]
                except (ValueError, KeyError, IndexError, TypeError):
                    continue
                content.append(delta.get("content") or "")
        if not done:
            raise ProviderError("stream_incomplete", retryable=True)
        result = {"status": "completed", "content": "".join(content), "model": model,
                  "usage": None, "usage_status": "UNKNOWN"}
        self._results[key] = result
        return result

    @staticmethod
    def _is_free(item):
        pricing = item.get("pricing")
        try:
            return isinstance(pricing, dict) and bool(pricing) and all(float(value) == 0 for value in pricing.values())
        except (TypeError, ValueError):
            return False

    def models(self, *, timeout=DEFAULT_TIMEOUT, free_only=False):
        """Read the public model catalog through the same egress gate (no key required); free_only keeps models whose every price is 0."""
        self._gate(MODELS_URL)
        status, raw = self._transport("GET", MODELS_URL, None, {"Accept": "application/json"}, timeout)
        self._check(status)
        try:
            return sorted(str(item["id"]) for item in json.loads(raw)["data"] if not free_only or self._is_free(item))
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderError("invalid_response", status=status) from error
