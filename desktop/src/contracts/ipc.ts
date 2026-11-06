// Mirror of src/respected_orchestrator/engine/local_api.py (a Python test keeps both in step).
export const IPC_VERSION = '1' as const;
export const MAX_REQUEST_BYTES = 65536;

export const COMMANDS = [
  'hello', 'engine.manifest', 'engine.health', 'settings.schema', 'settings.readback',
  'settings.validate', 'settings.apply', 'evidence.view', 'memory.status',
  'events.snapshot', 'events.since', 'runs.active', 'runs.list', 'projects.list', 'plan.view', 'plan.create', 'plan.edit', 'plan.start', 'project.status', 'project.cancel', 'project.resume', 'review.view', 'activity.list', 'approval.open', 'approval.decide', 'approval.apply',
] as const;
export type Command = (typeof COMMANDS)[number];

export const ERROR_CODES = [
  'BAD_REQUEST', 'UNSUPPORTED_VERSION', 'UNAUTHENTICATED', 'UNKNOWN_COMMAND', 'FORBIDDEN',
  'PAYLOAD_TOO_LARGE', 'REPLAY_CONFLICT', 'ENGINE_ERROR',
] as const;
export type ErrorCode = (typeof ERROR_CODES)[number];

export interface IpcRequest {
  ipc: typeof IPC_VERSION;
  id: string; // correlation id, 8-64 chars [A-Za-z0-9_-]
  session: string;
  cmd: Command;
  payload?: Record<string, unknown>;
}

export type IpcResponse =
  | { ipc: typeof IPC_VERSION; id: string | null; ok: true; result: unknown; error: null }
  | { ipc: typeof IPC_VERSION; id: string | null; ok: false; result: null; error: { code: ErrorCode; message: string } };
