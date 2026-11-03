"""ADP-03 real opt-in egress smoke: read OpenRouter's public model catalog through the gated adapter."""
import hashlib
import os
import sys

os.environ["RESPECTED_PROVIDER_NETWORK"] = "allow"
os.environ["RESPECTED_PROVIDER_CODE_GATE"] = "1"

from respected_orchestrator.engine.provider import ProviderClient, ProviderError

try:
    models = ProviderClient().models(timeout=20)
except ProviderError as error:
    print(f"SMOKE failed kind={error.kind} status={error.status}")
    sys.exit(1)

print(f"SMOKE ok models={len(models)}")
print("sha256=" + hashlib.sha256("\n".join(models).encode("utf-8")).hexdigest().upper())
print("sample=" + ", ".join(models[:3]))