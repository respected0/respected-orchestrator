"""Version-controlled price catalog with explicit unknown cost (COST-02).

Every numeric quote carries the lookup timestamp, catalog model version and currency. A missing model, missing usage
or unavailable provider yields status "unknown" and amount None; it is never silently coerced to zero.
"""

from datetime import datetime

UNKNOWN = "unknown"


def _stamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("at must be an ISO timestamp")
    return datetime.fromisoformat(value)


def quote(catalog, model, input_tokens, output_tokens, *, at, observed_tokens=None, provider_available=True):
    """Return a deterministic quote dict for one model lookup.

    catalog: iterable of dicts with model, model_version, effective_from, input_per_million, output_per_million,
    currency and unit. The newest entry whose effective_from is not after ``at`` wins.
    """
    stamp = _stamp(at)
    base = {"model": model, "at": at, "amount": None, "currency": None, "status": UNKNOWN,
            "observed_tokens": None, "estimate_only": True, "confidence": "estimated"}
    if not provider_available:
        return {**base, "reason": "provider_unavailable"}
    entries = [entry for entry in catalog if entry.get("model") == model]
    if not entries:
        return {**base, "reason": "model_unknown"}
    usable = [entry for entry in entries if _stamp(entry["effective_from"]) <= stamp]
    if not usable:
        return {**base, "reason": "not_yet_effective"}
    entry = max(usable, key=lambda item: _stamp(item["effective_from"]))
    if not (isinstance(input_tokens, int) and isinstance(output_tokens, int)
            and not isinstance(input_tokens, bool) and not isinstance(output_tokens, bool)
            and input_tokens >= 0 and output_tokens >= 0):
        return {**base, "reason": "usage_unknown", "model_version": entry["model_version"],
                "effective_from": entry["effective_from"]}
    amount = (input_tokens * entry["input_per_million"] + output_tokens * entry["output_per_million"]) / 1_000_000
    seen = observed_tokens if isinstance(observed_tokens, int) and not isinstance(observed_tokens, bool) else None
    return {"model": model, "at": at, "amount": round(amount, 6), "currency": entry["currency"],
            "status": "estimate", "model_version": entry["model_version"],
            "effective_from": entry["effective_from"], "unit": entry["unit"],
            "observed_tokens": seen, "estimate_only": True,
            "confidence": "observed" if seen is not None else "estimated"}


def display(quoted):
    """User-facing amount; an unknown price is shown as the word "unknown", never as 0."""
    return UNKNOWN if quoted.get("amount") is None else f"{quoted['amount']} {quoted['currency']}"
