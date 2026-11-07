"""Read-only remote observer prototype (B4-09.02). Research code: nothing starts it, and it can only look.

The core (`Observer`) is transport-independent so it can be attacked directly in tests:
  pairing     a person (HUMAN origin, at the machine) opens a one-time code valid for two minutes; a device that presents it receives a
              device id and a secret (shown once, stored only as a hash). A wrong code counts against a lockout; a used code is gone.
  tokens      a device exchanges its secret for a bearer token that lives ten minutes; tokens and secrets are stored hashed.
  revocation  removing a device kills its secret and every token at once; the next request is refused.
  requests    only GET of /status, /runs and /events. Every other method or path is refused, and no handler can write, start, approve,
              cancel, apply or change a setting: the module imports only the read models. Bodies are masked like the event store.
`serve` is a separate, optional wrapper. It binds loopback only and refuses any other address, because there is no transport encryption
in this prototype; without TLS and a verified identity, a non-loopback listener must not exist. Default: no listener, no devices."""
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..context import EngineContext, atomic_write_json, safe_path
from ..engine import read_model
from ..engine.authority import Action, Origin, authorize
from ..engine.journal import Journal, mask

PAIR_SECONDS, TOKEN_SECONDS, MAX_FAILS, LOCKOUT_SECONDS = 120, 600, 5, 300
MAX_DEVICES, MAX_EVENTS = 5, 200
READ_PATHS = ("/status", "/runs", "/events")


class ObserverError(PermissionError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Observer:
    def __init__(self, ctx: EngineContext, clock: Callable[[], float] = time.time):
        self.ctx, self.clock = ctx, clock
        self.path = safe_path(ctx.data_root / "observer" / "devices.json")
        self._pair: dict[str, Any] | None = None  # in memory only: a restart forgets an open code
        self._tokens: dict[str, dict[str, Any]] = {}
        self._fails: list[float] = []

    # ---- state --------------------------------------------------------------------------------------------------------
    def _devices(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text("utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, devices: dict[str, dict[str, Any]]) -> None:
        atomic_write_json(self.path, devices)

    # ---- pairing --------------------------------------------------------------------------------------------------------
    def open_pairing(self, *, origin: Origin) -> dict[str, Any]:
        """A person at this computer opens pairing and reads the code to the device. Nothing else can."""
        authorize(origin, Action.PRIVILEGED)
        if len(self._devices()) >= MAX_DEVICES:
            raise ObserverError("TOO_MANY_DEVICES", f"at most {MAX_DEVICES} devices can be paired; revoke one first")
        code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(8))
        self._pair = {"hash": _h(code), "expires": self.clock() + PAIR_SECONDS}
        return {"code": code, "expires_in": PAIR_SECONDS}

    def _locked(self) -> bool:
        now = self.clock()
        self._fails = [t for t in self._fails if now - t < LOCKOUT_SECONDS]
        return len(self._fails) >= MAX_FAILS

    def pair(self, code: Any, name: Any) -> dict[str, Any]:
        if self._locked():
            raise ObserverError("LOCKED", "too many wrong attempts; try again later")
        pending, self._pair = self._pair, None  # one try per opened code: the code is spent whether it matched or not
        ok = pending is not None and isinstance(code, str) and self.clock() <= pending["expires"] and hmac.compare_digest(_h(code.strip().upper()), pending["hash"])
        if not ok:
            self._fails.append(self.clock())
            raise ObserverError("BAD_CODE", "the pairing code is wrong, used or expired")
        label = str(name)[:40] if isinstance(name, str) and name.strip() else "device"
        device_id, secret = "dev-" + secrets.token_hex(6), secrets.token_urlsafe(32)
        devices = self._devices()
        devices[device_id] = {"name": label, "secret_hash": _h(secret), "paired_at": self.clock()}
        self._save(devices)
        return {"device_id": device_id, "secret": secret, "note": "the secret is shown once"}

    def revoke(self, device_id: str, *, origin: Origin) -> bool:
        authorize(origin, Action.PRIVILEGED)
        devices = self._devices()
        gone = devices.pop(device_id, None) is not None
        if gone:
            self._save(devices)
        self._tokens = {t: v for t, v in self._tokens.items() if v["device"] != device_id}
        return gone

    # ---- tokens and requests --------------------------------------------------------------------------------------------
    def token(self, device_id: Any, secret: Any) -> dict[str, Any]:
        if self._locked():
            raise ObserverError("LOCKED", "too many wrong attempts; try again later")
        device = self._devices().get(device_id) if isinstance(device_id, str) else None
        if device is None or not isinstance(secret, str) or not hmac.compare_digest(_h(secret), device["secret_hash"]):
            self._fails.append(self.clock())
            raise ObserverError("BAD_CREDENTIALS", "unknown device or wrong secret")
        value = secrets.token_urlsafe(32)
        self._tokens[_h(value)] = {"device": device_id, "expires": self.clock() + TOKEN_SECONDS}
        return {"token": value, "expires_in": TOKEN_SECONDS}

    def _authenticate(self, bearer: Any) -> str:
        record = self._tokens.get(_h(bearer)) if isinstance(bearer, str) else None
        if record is None or self.clock() > record["expires"] or record["device"] not in self._devices():
            raise ObserverError("UNAUTHENTICATED", "missing, expired or revoked token")
        return record["device"]

    def handle(self, method: str, target: str, bearer: Any) -> tuple[int, dict[str, Any]]:
        """(HTTP status, JSON body). The only entry point a transport may use for data."""
        path, _, query = target.partition("?")
        if method != "GET":
            return 405, {"error": "read-only: only GET is accepted"}  # checked before authentication so a probe learns nothing either way
        if path not in READ_PATHS:
            return 404, {"error": "unknown path"}
        try:
            self._authenticate(bearer)
        except ObserverError as error:
            return 401, {"error": error.message}
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        try:
            if path == "/status":
                page = read_model.runs_page(self.ctx, limit=200)["runs"]
                counts: dict[str, int] = {}
                for row in page:
                    counts[row["state"]] = counts.get(row["state"], 0) + 1
                return 200, {"runs_by_state": counts, "sampled": len(page)}
            if path == "/runs":
                return 200, read_model.runs_page(self.ctx, limit=min(int(params.get("limit", 25)), 50), cursor=params.get("cursor"))
            after = int(params.get("after", 0))
            events = [{"seq": r["seq"], "type": r["type"], "run": r["run"], "p": mask(r["p"])} for r in Journal(self.ctx.state_dir / "events.log").replay(after, MAX_EVENTS)]
            return 200, {"events": events, "last_seq": events[-1]["seq"] if events else after}
        except (ValueError, KeyError):
            return 400, {"error": "bad parameter"}


def serve(observer: Observer, host: str, port: int, *, origin: Origin) -> Any:
    """Optional loopback listener around Observer.handle. Returns the server object (not started); the caller decides when to run it.

    Refuses every non-loopback address: this prototype has no transport encryption, so a LAN or WAN listener must not exist."""
    authorize(origin, Action.PRIVILEGED)
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ObserverError("NO_REMOTE_LISTENER", "this prototype listens on loopback only; a remote listener needs TLS and verified identity first")
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            bearer = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip() or None
            self._send(*observer.handle("GET", self.path, bearer))

        def _refuse(self) -> None:
            self._send(*observer.handle(self.command, self.path, None))

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse  # noqa: N815

        def log_message(self, *args: Any) -> None:  # no access log: tokens never reach a log
            return

    return HTTPServer((host, port), Handler)
