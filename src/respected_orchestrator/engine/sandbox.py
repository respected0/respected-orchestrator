"""Trust boundary for worker-written code that the engine itself runs (acceptance checks, project verify).

ADR-018: such commands run through the same AppContainer path as the worker (`worker_policy` + `appcontainer.spawn`).
The container reaches only the worktree (writable), the interpreter/tool directories (read-only) and a scratch
directory, so it cannot read `.engine-key`, sign approvals or rewrite evidence, and the network is denied by default.

Network exception (all or nothing, AppContainer cannot filter by host): the operator lists task ids in
RESPECTED_VERIFY_NETWORK_TASKS (comma separated) in the engine's own environment. Only a listed task gets the network and
the evidence records `network: allowed`. A task prompt or worker cannot set it.

Fail closed: no AppContainer (not Windows, elevated session, ACL error) means the command does not run. There is no
restricted-token or unwrapped fallback, and RESPECTED_ORCH_SANDBOX=off is not honoured here.
"""
import os
from pathlib import Path

from ..context import safe_path


class SandboxError(RuntimeError):
    pass


def network_mode(task_id):
    allowed = {part.strip() for part in os.environ.get("RESPECTED_VERIFY_NETWORK_TASKS", "").split(",") if part.strip()}
    return "allow" if str(task_id) in allowed else "deny"


def run_check(ctx, command, cwd, timeout_seconds, *, task_id, scratch, cancel_path=None):
    """Run one acceptance/verify command in the AppContainer. Returns (completed, network)."""
    from .processes import ProcessStopped, execute
    from .worker_policy import SandboxStartError, WorkerPolicyError, default_policy, extra_readonly_roots
    if os.name != "nt":
        raise SandboxError("verify isolation needs the Windows AppContainer; no unsandboxed fallback exists")
    if timeout_seconds <= 0:
        raise ProcessStopped("timed_out")
    network = network_mode(task_id)
    try:
        scratch = safe_path(Path(scratch))
        scratch.mkdir(parents=True, exist_ok=True)
        policy = default_policy(ctx, Path(cwd), command, network_mode=network, temp_root=scratch,
                                readonly_roots=extra_readonly_roots(), ttl=timeout_seconds)
        return execute(command, Path(cwd), timeout_seconds, cancel_path=cancel_path, scrub_env=True, policy=policy), network
    except (WorkerPolicyError, SandboxStartError) as error:
        raise SandboxError(str(error)) from error
