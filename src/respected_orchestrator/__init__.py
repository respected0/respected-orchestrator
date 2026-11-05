"""Respected Orchestrator: independent engine, no memory vault required."""
# The PEP 440 spelling of the pyproject.toml version, written here because reading it from the package metadata at start-up cost ~200 ms per
# process (importlib.metadata). Bump it with pyproject.toml: a test fails when the two disagree.
__version__ = "0.1.0b2"
