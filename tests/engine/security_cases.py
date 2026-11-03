"""Shared SEC-04 registry and adversarial probe for the worker boundary.

The probe is standard-library only because it runs inside the real AppContainer
worker (source tests) and inside the frozen executable's worker. Every attempt
records either ``ALLOWED`` or ``denied:<error>``; a missing line is never treated
as a pass.

The registry is intentionally data, not a list of test method names: the gate
test and both source/frozen matrices enumerate the same cases, so deleting a
case cannot silently shrink the suite.
"""

PROBE = r'''
import json, os, subprocess, sys

try:
    data, key, outside, port, secret_name = sys.argv[1:6]
except ValueError:
    print(json.dumps({"probe_error": "arguments"}))
    raise SystemExit(2)

worktree = os.getcwd()
results = {}


def negative(name, action):
    try:
        action()
    except Exception as error:
        results[name] = "denied:" + type(error).__name__
    else:
        results[name] = "ALLOWED"


def allowed(name, action):
    try:
        action()
    except Exception as error:
        results[name] = "FAILED:" + type(error).__name__ + ":" + str(error)[:120]
    else:
        results[name] = "ALLOWED"


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def write(path, text="x"):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def remove(path):
    os.remove(path)


def ensure_junction(name, target):
    link = os.path.join(worktree, name)
    if os.path.lexists(link):
        return link
    completed = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                               capture_output=True, text=True)
    if completed.returncode:
        raise PermissionError((completed.stdout + completed.stderr)[:200])
    return link


# --- negative: engine data, key, evidence and approval material ---------------
negative("read_engine_key", lambda: read(key))
negative("read_settings", lambda: read(os.path.join(data, "settings.json")))
negative("read_evidence", lambda: read(os.path.join(data, "state", "run-1", "result.json")))
negative("overwrite_evidence", lambda: write(os.path.join(data, "state", "run-1", "result.json"), "{}"))
negative("delete_evidence", lambda: remove(os.path.join(data, "state", "run-1", "result.json")))
negative("forge_approval", lambda: write(os.path.join(data, "state", "run-1", "maf-approval.json"), "{}"))
negative("write_data_root", lambda: write(os.path.join(data, "planted.json"), "{}"))
negative("tamper_run_metadata", lambda: write(os.path.join(data, "state", "run-1", "status.json"), "{}"))
negative("read_key_long_path", lambda: read("\\\\?\\" + os.path.abspath(key)))
negative(
    "read_key_unc",
    lambda: read("\\\\localhost\\" + os.path.abspath(key)[0] + "$" + os.path.abspath(key)[2:]),
)


def read_via_junction():
    link = ensure_junction("junction-data", data)
    read(os.path.join(link, ".engine-key"))


negative("read_key_via_junction", read_via_junction)


def write_via_junction():
    link = ensure_junction("junction-outside", outside)
    write(os.path.join(link, "junction-planted.txt"), "x")


negative("junction_write_outside", write_via_junction)
negative("hardlink_key_into_worktree", lambda: os.link(key, os.path.join(worktree, "stolen-key")))


def acl_rewrite():
    completed = subprocess.run(["icacls", key, "/grant", "Everyone:F"],
                               capture_output=True, text=True)
    if completed.returncode:
        raise PermissionError((completed.stdout + completed.stderr)[:200])


negative("rewrite_key_acl", acl_rewrite)


def env_secret():
    value = os.environ.get(secret_name)
    if value is None:
        raise PermissionError("absent")
    if value != "SEC04-SENTINEL-DO-NOT-LEAK":
        raise PermissionError("unexpected secret value")


negative("env_secret_visible", env_secret)


def egress():
    import socket
    connection = socket.socket()
    connection.settimeout(2)
    try:
        connection.connect(("127.0.0.1", int(port)))
    finally:
        connection.close()


negative("network_egress", egress)


def child_reads_key():
    inner = "import sys; open(sys.argv[1], 'rb').read()"
    completed = subprocess.run([sys.executable, "-c", inner, key],
                               capture_output=True, text=True)
    if completed.returncode != 0:
        raise PermissionError("child denied")


negative("child_process_read_key", child_reads_key)
negative("read_outside_file", lambda: read(os.path.join(outside, "private.txt")))
negative("write_outside_file", lambda: write(os.path.join(outside, "planted.txt"), "x"))


# --- allowed: the worker's own workspace, toolchain and scratch ---------------
def worktree_write_read():
    path = os.path.join(worktree, "probe.txt")
    write(path, "inside")
    assert read(path) == b"inside"
    remove(path)


allowed("write_worktree", worktree_write_read)


def worktree_read():
    path = os.path.join(worktree, "probe-read.txt")
    write(path, "inside")
    assert read(path) == b"inside"
    remove(path)


allowed("read_worktree", worktree_read)


def create_directory():
    path = os.path.join(worktree, "probe-dir")
    os.makedirs(path, exist_ok=True)
    os.rmdir(path)


allowed("create_directory", create_directory)


def delete_own_file():
    path = os.path.join(worktree, "probe-delete.txt")
    write(path, "x")
    remove(path)


allowed("delete_own_file", delete_own_file)
allowed("list_worktree", lambda: os.listdir(worktree))


def spawn_child():
    completed = subprocess.run([sys.executable, "-c", "print('ok')"],
                               capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr[:120])
    assert completed.stdout.strip() == "ok"


allowed("spawn_child", spawn_child)
allowed("read_stdlib", lambda: read(__import__("json").__file__))


def toolchain_version():
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.version_info[0])"],
        capture_output=True, text=True,
    )
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise RuntimeError(completed.stderr[:120])


allowed("toolchain_version", toolchain_version)


def temp_write():
    root = os.environ.get("RESPECTED_WORKER_TMP")
    if not root:
        raise RuntimeError("scratch root not published")
    path = os.path.join(root, "probe-temp.txt")
    write(path, "x")
    remove(path)


allowed("temp_write", temp_write)

print(json.dumps(results, sort_keys=True))
'''


NEGATIVE_CATEGORIES = {
    "read_engine_key": "data_root",
    "read_settings": "data_root",
    "read_evidence": "data_root",
    "overwrite_evidence": "tampering",
    "delete_evidence": "tampering",
    "forge_approval": "tampering",
    "write_data_root": "data_root",
    "tamper_run_metadata": "tampering",
    "read_key_long_path": "long_path",
    "read_key_unc": "unc",
    "read_key_via_junction": "junction",
    "junction_write_outside": "junction",
    "hardlink_key_into_worktree": "hardlink",
    "rewrite_key_acl": "acl_tampering",
    "env_secret_visible": "env_secret",
    "network_egress": "egress",
    "child_process_read_key": "child_process",
    "read_outside_file": "outside_workspace",
    "write_outside_file": "outside_workspace",
    "symlink_patch": "symlink_patch",
    "recursive_mcp": "recursive_mcp",
}

# These are exercised by their own tests rather than the in-worker probe.
EXTERNAL_NEGATIVE_CASES = ("symlink_patch", "recursive_mcp")

PROBE_NEGATIVE_CASES = tuple(
    name for name in NEGATIVE_CATEGORIES if name not in EXTERNAL_NEGATIVE_CASES
)

ALLOWED_CASES = (
    "write_worktree",
    "read_worktree",
    "create_directory",
    "delete_own_file",
    "list_worktree",
    "spawn_child",
    "read_stdlib",
    "toolchain_version",
    "temp_write",
)

NEGATIVE_CASES = tuple(NEGATIVE_CATEGORIES)

REQUIRED_CATEGORIES = frozenset({
    "data_root",
    "outside_workspace",
    "junction",
    "hardlink",
    "symlink_patch",
    "env_secret",
    "egress",
    "recursive_mcp",
    "child_process",
    "tampering",
    "long_path",
    "unc",
    "acl_tampering",
})
