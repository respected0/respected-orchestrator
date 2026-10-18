"""Trust boundary for worker-written code that the engine itself runs (acceptance checks, project verify).

Threat: a worker leaves code that the engine later executes as the same Windows user. Without a boundary that code
could read `.engine-key`, sign `maf-approval.json`, rewrite signed evidence or read the memory grant token.

Mechanism (Windows): such commands run through `sandbox_exec`, which starts them with a RESTRICTED TOKEN. The token
keeps every group of the user (so tools, caches and the worktree behave as before) and adds one extra restricting SID
that belongs to this data root. Access checks are then done twice (normal SIDs and restricting SIDs), so a DENY ACE for
that SID blocks the sandbox while the engine, whose token lacks the SID, is unaffected. The data root denies the SID on
every child except `workspaces/` (the worker's own area) and the engine key.

Limits (documented, not hidden): the sandboxed code still reads the user's other files (for example AI client
credentials in the profile) and can use the network; this boundary protects the engine's evidence, approvals and
secrets only. Windows only: other platforms run the command unwrapped.
"""
import json
import os
import secrets
import sys
from pathlib import Path

from . import winproc
from .context import atomic_write_json, safe_path


class SandboxError(RuntimeError):
    pass


def enabled():
    return os.name == "nt" and os.environ.get("RESPECTED_ORCH_SANDBOX", "on") != "off"


def _state(data_root):
    return safe_path(Path(data_root) / "sandbox.json")


def sandbox_sid(data_root):
    """Per data root SID (well formed, never assigned to a real principal), created once."""
    path = _state(data_root)
    try:
        sid = json.loads(path.read_text("utf-8")).get("sid")
        if isinstance(sid, str) and sid.startswith("S-1-5-21-"):
            return sid
    except (OSError, ValueError):
        pass
    sid = "S-1-5-21-" + "-".join(str(secrets.randbelow(2**31 - 1) + 1) for _ in range(3)) + "-" + str(secrets.randbelow(60000) + 5000)
    atomic_write_json(path, {"sid": sid})
    return sid


# icacls refuses a SID that maps to no account, .NET does not: ACL edits go through .NET (DACL only).
# One PowerShell start does everything (a start costs about a second); the script is idempotent.
_PS = r"""
$ErrorActionPreference = 'Stop'
$sid = New-Object System.Security.Principal.SecurityIdentifier($env:SBX_SID)
$owner = New-Object System.Security.Principal.SecurityIdentifier('S-1-3-4')
$rights = 'CreateFiles,CreateDirectories,DeleteSubdirectoriesAndFiles,Delete,WriteAttributes,WriteExtendedAttributes,ChangePermissions,TakeOwnership'
function Has($acl) { @($acl.Access | Where-Object { $_.IdentityReference.Value -eq $sid.Value -and $_.AccessControlType -eq 'Deny' }).Count -gt 0 }
function Rule($who, $r, $inherit, $type) {
  $flags = if ($inherit) { 'ContainerInherit,ObjectInherit' } else { 'None' }
  $only = if ($inherit -and $type -eq 'Deny') { 'InheritOnly' } else { 'None' }
  New-Object System.Security.AccessControl.FileSystemAccessRule($who, $r, $flags, $only, $type)
}
$root = Get-Item -LiteralPath $env:SBX_ROOT -Force
$ws = Get-Item -LiteralPath $env:SBX_WORKSPACES -Force
$key = Get-Item -LiteralPath $env:SBX_KEY -Force
$acl = $root.GetAccessControl('Access')
if (-not (Has $acl)) {
  $wa = $ws.GetAccessControl('Access'); $wa.SetAccessRuleProtection($true, $true); $ws.SetAccessControl($wa)   # explicit copy first: the inheritable deny below must never reach the worker area
  $acl = $root.GetAccessControl('Access')
  $acl.AddAccessRule((Rule $sid 'FullControl' $true 'Deny'))                       # every current and future child
  $acl.AddAccessRule((Rule $sid $rights $false 'Deny'))                            # the directory itself: nothing created/replaced/re-ACLed in it
  $acl.AddAccessRule((Rule $owner 'ReadPermissions' $true 'Allow'))                # OWNER RIGHTS: else the owner keeps WRITE_DAC, which no deny can remove
  $root.SetAccessControl($acl)
}
$ka = $key.GetAccessControl('Access')
if (-not (Has $ka)) {
  $ka.AddAccessRule((Rule $sid 'FullControl' $false 'Deny')); $ka.AddAccessRule((Rule $owner 'ReadPermissions' $false 'Allow')); $key.SetAccessControl($ka)
}
if (Has ($ws.GetAccessControl('Access'))) { throw 'workspaces/ inherited the sandbox deny' }
'ok'
"""


def protect(data_root, key_path):
    """Idempotent: workspaces/ keeps its own ACL, every other child of the data root and the key deny the sandbox SID."""
    data_root = safe_path(Path(data_root))
    key_path = safe_path(Path(key_path))
    sid = sandbox_sid(data_root)
    workspaces = data_root / "workspaces"
    workspaces.mkdir(parents=True, exist_ok=True)
    marker = _state(data_root)
    state = json.loads(marker.read_text("utf-8"))
    identity = f"{key_path.stat().st_ino}:{key_path.stat().st_dev}"
    if state.get("protected_key") == identity:       # same key file as when the ACLs were applied
        return sid
    env = dict(os.environ, SBX_SID=sid, SBX_ROOT=str(data_root), SBX_WORKSPACES=str(workspaces), SBX_KEY=str(key_path))
    done = winproc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS], capture_output=True, text=True, timeout=120, env=env)
    if done.returncode or "ok" not in done.stdout:
        raise SandboxError(f"ACL setup failed: {(done.stderr or done.stdout).strip()[:300]}")
    atomic_write_json(marker, dict(state, protected_key=identity))
    return sid


def wrap(data_root, key_path, command):
    """Command that runs `command` inside the restricted token (fails closed when the boundary cannot be set up)."""
    if not enabled():
        return list(command)
    sid = protect(data_root, key_path)
    source = str(Path(__file__).resolve().parents[1])   # importable wherever the engine itself runs from
    boot = "import sys; sys.path.insert(0, sys.argv[1]); from respected_orchestrator import sandbox_exec; sys.exit(sandbox_exec.main(sys.argv[2:]))"
    return [sys.executable, "-c", boot, source, "--sid", sid, "--", *command]
