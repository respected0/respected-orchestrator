"""A deliberately hostile local page for the B3-06.03 real-window test. Serves one page on 127.0.0.1 that tries, from inside the preview window:
  - to call the shell's commands through every IPC route the WebView offers,
  - to read the app's storage/cookies, navigate away, open windows, reach other loopback ports and the internet,
and POSTs what happened to /report. Run: python preview_hostile_server.py PORT LOGFILE"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT, LOG = int(sys.argv[1]), sys.argv[2]
OTHER_PORT = PORT + 1  # a second loopback listener that is NOT on the allowlist

PAGE = """<!doctype html><meta charset="utf-8"><title>hostile</title><h1 id="h">hostile page loaded</h1><script>
const report = {origin: location.origin, results: {}};
const note = (k, v) => { report.results[k] = v; };
const tryit = async (k, f) => { try { note(k, 'ALLOWED: ' + String(await f()).slice(0, 120)); } catch (e) { note(k, 'blocked: ' + String((e && e.message) || e).slice(0, 120)); } };
(async () => {
  const internals = window.__TAURI_INTERNALS__;
  note('has __TAURI_INTERNALS__', String(!!internals));
  for (const cmd of ['engine_status', 'confirm_close', 'request_apply', 'capability_inventory', 'preview_open', 'plugin:event|listen', 'plugin:window|close', 'plugin:webview|create_webview_window']) {
    await tryit('invoke ' + cmd, () => internals ? internals.invoke(cmd, cmd === 'request_apply' ? {runId: 'run-20260101000000-aaaaaaaaaaaa'} : cmd === 'preview_open' ? {url: 'http://127.0.0.1:%(port)d/'} : {}) : Promise.reject(new Error('no IPC bridge')));
  }
  await tryit('window.ipc.postMessage', () => (window.ipc && window.ipc.postMessage) ? window.ipc.postMessage('{}') : Promise.reject(new Error('no ipc object')));
  await tryit('chrome.webview.postMessage', () => (window.chrome && window.chrome.webview) ? window.chrome.webview.postMessage('x') : Promise.reject(new Error('no chrome.webview')));
  await tryit('read app localStorage key', () => { const v = localStorage.getItem('orch.inventory.falsePositives'); if (v !== null) return 'FOUND ' + v; throw new Error('empty (not shared)'); });
  await tryit('document.cookie of the app origin', () => { if (document.cookie) return 'COOKIES ' + document.cookie; throw new Error('no cookies'); });
  await tryit('fetch other loopback port', async () => (await fetch('http://127.0.0.1:%(other)d/secret', {mode: 'no-cors'})).type);
  await tryit('fetch internet', async () => (await fetch('https://example.com/', {mode: 'no-cors'})).type);
  await tryit('fetch app origin', async () => (await fetch('http://tauri.localhost/', {mode: 'no-cors'})).type);
  await tryit('window.open another origin', () => { const w = window.open('http://127.0.0.1:%(other)d/x'); if (w) return 'opened a window'; throw new Error('popup refused'); });
  await tryit('top navigation to another port', () => { location.href = 'http://127.0.0.1:%(other)d/stolen'; return 'asked'; });
  await new Promise(r => setTimeout(r, 1500));
  note('final origin after the navigation attempt', location.origin);
  await tryit('report back', () => fetch('/report', {method: 'POST', body: JSON.stringify(report)}).then(r => r.status));
  document.getElementById('h').textContent = 'hostile page finished: see the server log';
})();
</script>""" % {"port": PORT, "other": OTHER_PORT}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _log(self, kind, body=""):
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": kind, "path": self.path, "body": body}) + "\n")

    def do_GET(self):
        self._log("GET")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode())

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0))).decode("utf-8", "replace")
        self._log("POST", body)
        self.send_response(204)
        self.end_headers()


class Other(BaseHTTPRequestHandler):
    """The off-allowlist port. A navigation (/stolen) or popup (/x) reaching it is a breach; a plain fetch (/secret) only shows the page has normal browser network access."""
    def log_message(self, *a):
        pass

    def do_GET(self):
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": "other-port-request", "path": self.path}) + "\n")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>BREACH</title><h1>BREACH: the other-port page replaced the preview</h1>")

    do_POST = do_GET


if __name__ == "__main__":
    import threading
    other = HTTPServer(("127.0.0.1", OTHER_PORT), Other)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
