"""REL-04: fail-closed platform GA decision; parity must be measured per OS before release."""

REQUIRED_FIXTURES = (
    "permission", "symlink", "network", "child_tree", "key_read",
    "migration", "installer_rollback", "janitor", "secret_env", "mcp_recursion",
)
GA_PLATFORMS = frozenset({"windows", "win32"})


def decide(platform, fixtures):
    """Return a release decision; an unknown or red fixture is always a no-go."""
    if platform not in GA_PLATFORMS:
        return {"platform": platform, "release": "no-go", "ga": False,
                "reason": "platform parity not proven; ADR-REL04 keeps POSIX out of GA"}
    if not isinstance(fixtures, dict) or set(fixtures) != set(REQUIRED_FIXTURES):
        return {"platform": platform, "release": "no-go", "ga": False,
                "reason": "the security fixture matrix is incomplete", "fixtures": REQUIRED_FIXTURES}
    red = sorted(name for name, value in fixtures.items() if value != "pass")
    if red:
        return {"platform": platform, "release": "no-go", "ga": False, "red": red}
    return {"platform": platform, "release": "go", "ga": True, "red": [], "fixtures": len(fixtures)}