import os

os.environ["RESPECTED_ORCH_TEST_ISOLATION"] = "1"
# The engine marks every child (incl. acceptance runs) with this; tests must not inherit the worker identity.
os.environ.pop("RESPECTED_ORCH_CHILD", None)
