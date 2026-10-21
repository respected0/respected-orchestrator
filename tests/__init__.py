"""Test packages. Importing this package (unittest discovery does it first) isolates the whole run:

* the engine refuses real codex/AI calls (RESPECTED_ORCH_TEST_ISOLATION) and tests never inherit a worker identity;
* HOME, USERPROFILE, APPDATA and LOCALAPPDATA point at a fresh empty folder, so no test can reach the real AI-client
  configuration or data root of the person running the suite. Child processes inherit both.
"""
import atexit
import os
from pathlib import Path
import shutil
import tempfile

os.environ["RESPECTED_ORCH_TEST_ISOLATION"] = "1"
# The engine marks every child (incl. acceptance runs) with this; tests must not inherit the worker identity.
os.environ.pop("RESPECTED_ORCH_CHILD", None)

if not os.environ.get("RESPECTED_TEST_SANDBOX"):
    _home = Path(tempfile.mkdtemp(prefix="respected-test-home-"))
    for _sub in ("AppData/Roaming", "AppData/Local"):
        (_home / _sub).mkdir(parents=True)
    os.environ.update(USERPROFILE=str(_home), HOME=str(_home), APPDATA=str(_home / "AppData/Roaming"),
                      LOCALAPPDATA=str(_home / "AppData/Local"), RESPECTED_TEST_SANDBOX=str(_home))
    atexit.register(shutil.rmtree, _home, ignore_errors=True)
