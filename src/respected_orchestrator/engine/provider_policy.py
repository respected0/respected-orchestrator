"""Fail-closed egress policy for provider adapters (ADR-007).

No provider adapter may open a socket before :func:`require_access` succeeds.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

OPT_IN_ENV = "RESPECTED_PROVIDER_NETWORK"
CODE_GATE_ENV = "RESPECTED_PROVIDER_CODE_GATE"
REDACTED = "***set***"


class ProviderDenied(PermissionError):
    """Raised before any provider request is made."""


def require_access(url: str, allowed_domains, environ=None) -> str:
    """Return the approved host or raise before a request can start.

    Redirects must call this again with the redirect target, so a foreign
    host cannot be reached through a trusted-domain redirect.
    """
    env = os.environ if environ is None else environ
    if env.get(OPT_IN_ENV, "").strip().casefold() != "allow":
        raise ProviderDenied("provider network opt-in is off")
    if env.get(CODE_GATE_ENV, "").strip() != "1":
        raise ProviderDenied("provider code gate is off")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password:
        raise ProviderDenied("provider URL must be https without credentials")
    host = (parts.hostname or "").casefold().rstrip(".")
    allowed = {str(domain).casefold().rstrip(".") for domain in allowed_domains}
    if host not in allowed:
        raise ProviderDenied(f"provider domain is not allowed: {host or '<empty>'}")
    return host


def redact_secret(text: str, secret: str) -> str:
    """Remove an API key from text before it reaches a log or evidence file."""
    return text if not secret else text.replace(secret, REDACTED)
