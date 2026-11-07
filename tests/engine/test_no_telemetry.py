"""B3-09.04 release gate input: the product contains no telemetry path and exactly one module that can open a network connection.

This is a static scan of the shipped sources (Python engine, React shell, Tauri shell and its dependency list), not a packet capture.
The runtime side is `tests/engine/offline_inventory_proof.py` (network/process attempts raise and are recorded). The one
network-capable engine module is the provider client, which is behind the explicit opt-in of ADR-007.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NETWORK_MODULES = re.compile(r"^\s*(?:import|from)\s+(?:socket|urllib\.request|urllib\.error|http\b|requests|httpx|aiohttp|ssl|ftplib|smtplib|websockets?|xmlrpc)", re.M)
ALLOWED_NETWORK = {"src/respected_orchestrator/engine/provider.py"}
TELEMETRY = re.compile(r"sentry|posthog|mixpanel|amplitude|segment\.io|google-analytics|gtag\(|telemetry|appinsights|datadog|bugsnag|rollbar|crashpad", re.I)
BROWSER_NETWORK = re.compile(r"\bfetch\(|XMLHttpRequest|sendBeacon|new WebSocket\(|new EventSource\(")


def files(pattern, *roots):
    for root in roots:
        yield from (p for p in (ROOT / root).rglob(pattern) if "node_modules" not in p.parts and "target" not in p.parts and "dist" not in p.parts)


def rel(p):
    return p.relative_to(ROOT).as_posix()


class NoTelemetryTests(unittest.TestCase):
    def test_only_the_provider_client_can_open_a_network_connection(self):
        found = {rel(p) for p in files("*.py", "src") if NETWORK_MODULES.search(p.read_text(encoding="utf-8", errors="replace"))}
        self.assertEqual(found, ALLOWED_NETWORK)

    def test_no_telemetry_or_crash_reporting_in_any_shipped_source(self):
        hits = []
        for pattern, roots in (("*.py", ["src"]), ("*.ts", ["desktop/src"]), ("*.tsx", ["desktop/src"]), ("*.rs", ["desktop/src-tauri/src"]),
                               ("Cargo.toml", ["desktop/src-tauri"]), ("package.json", ["desktop"]), ("pyproject.toml", ["."])):
            for p in files(pattern, *roots):
                if p.name == "package.json" and p.parent != ROOT / "desktop":
                    continue
                if p.name == "pyproject.toml" and p.parent != ROOT:
                    continue
                for m in TELEMETRY.finditer(p.read_text(encoding="utf-8", errors="replace")):
                    hits.append(f"{rel(p)}: {m.group(0)}")
        self.assertEqual(hits, [])

    def test_the_react_shell_makes_no_network_calls(self):
        hits = [rel(p) for p in [*files("*.ts", "desktop/src"), *files("*.tsx", "desktop/src")] if BROWSER_NETWORK.search(p.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(hits, [])

    def test_the_tauri_shell_has_no_http_client_dependency(self):
        cargo = (ROOT / "desktop" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
        for crate in ("reqwest", "hyper", "ureq", "isahc", "surf", "tauri-plugin-http", "tauri-plugin-updater", "tauri-plugin-websocket"):
            self.assertNotRegex(cargo, rf"(?m)^\s*{re.escape(crate)}\s*=", crate)

    def test_the_scan_itself_detects_what_it_looks_for(self):
        self.assertTrue(NETWORK_MODULES.search("import urllib.request\n"))
        self.assertTrue(TELEMETRY.search("init(Sentry)"))
        self.assertTrue(BROWSER_NETWORK.search("await fetch(url)"))


if __name__ == "__main__":
    unittest.main()
