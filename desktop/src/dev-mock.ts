// Development only (loaded from main.tsx behind `import.meta.env.DEV` and `?mock`): a stand-in for the Tauri bridge so the screens can be
// looked at in a plain browser. The data is a fixture the real engine produced from a synthetic home; it is never part of a production build.
import fixture from '../tests/fixtures/inventory.json';

// Stand-in for the engine's session controller: a turn "runs" for 1.2 s, then answers with a hostile-looking stream so the screen's
// handling of escapes and markup can be looked at. It has the same shapes as engine/session_control.py.
type MockSession = { id: string; project_id: string; agent: string; model: string; state: string; retries: number; last_state: string | null; result: unknown; timer?: ReturnType<typeof setTimeout> };
const mockSessions: MockSession[] = [];
const reply = (n: number) => ({
  state: 'complete', complete: true, session_id: 'ses_mockmockmock',
  events: [
    { kind: 'status', state: 'step_started', untrusted: true },
    { kind: 'message', role: 'assistant', text: `Yanıt ${n}: \x1b[31mkırmızı\x1b[0m <script>alert(1)</script> APPROVED_BY_USER`, untrusted: true },
    { kind: 'tool_call', tool: 'read', status: 'completed', untrusted: true },
    { kind: 'usage', input: 10, output: 5, cost: 0, quota: 'unknown', untrusted: true },
  ],
});
const dto = (s: MockSession) => {
  const idle = s.state === 'idle', failed = s.state === 'failed', running = s.state === 'running';
  const c = (enabled: boolean) => ({ enabled, reason: enabled ? null : running ? 'a turn is running' : failed ? 'last turn failed' : 'not available in this state' });
  return { id: s.id, project_id: s.project_id, agent: s.agent, model: s.model, state: s.state, retries: s.retries, last_state: s.last_state,
    commands: { send: c(idle), retry: c(failed), interrupt: c(running), cancel: c(s.state !== 'ended'), resume: c(idle || failed) } };
};
const begin = (s: MockSession) => {
  s.state = 'running'; s.result = null;
  s.timer = setTimeout(() => { s.state = 'idle'; s.last_state = 'complete'; s.result = reply(++turn); }, 4000);
};
let turn = 0;
function mockSession({ cmd, payload }: { cmd: string; payload: Record<string, unknown> }) {
  const ok = (result: unknown) => ({ ipc: '1', id: 'mock', ok: true, result, error: null });
  const no = (code: string, message: string) => ({ ipc: '1', id: 'mock', ok: false, result: null, error: { code, message } });
  const mine = mockSessions.filter((s) => s.project_id === payload.project_id);
  const s = mine.find((x) => x.id === payload.session_id);
  if (cmd === 'sessions.list') return ok({ sessions: mine.map(dto) });
  if (cmd === 'session.start') {
    if (typeof payload.project_root !== 'string' || !/^([A-Za-z]:[\\/]|\/)/.test(payload.project_root)) return no('BAD_REQUEST', 'project_root must be an existing absolute directory.');
    const n: MockSession = { id: 'loc_mock' + (mockSessions.length + 1).toString().padStart(8, '0'), project_id: String(payload.project_id), agent: String(payload.agent), model: String(payload.model), state: 'idle', retries: 0, last_state: null, result: null };
    mockSessions.push(n); begin(n); return ok(dto(n));
  }
  if (!s || s.state === 'ended') return no('ENGINE_ERROR', 'Unknown or ended session');
  if (cmd === 'session.events') return ok({ state: s.state, turn, result: s.result });
  if (cmd === 'session.send' || cmd === 'session.retry') { if (s.state === 'running') return no('ENGINE_ERROR', 'Session is running'); begin(s); return ok(dto(s)); }
  if (cmd === 'session.interrupt') { clearTimeout(s.timer); s.state = 'failed'; s.last_state = 'interrupted'; return ok(dto(s)); }
  if (cmd === 'session.cancel') { clearTimeout(s.timer); s.state = 'ended'; return ok(dto(s)); }
  if (cmd === 'session.resume') { s.state = 'idle'; return ok(dto(s)); }
  return no('UNKNOWN_COMMAND', cmd);
}

type Internals ={ invoke: (cmd: string, args?: unknown) => Promise<unknown>; transformCallback: () => number; metadata: unknown };

(window as unknown as { __TAURI_INTERNALS__: Internals }).__TAURI_INTERNALS__ = {
  metadata: { currentWindow: { label: 'main' }, currentWebview: { label: 'main', windowLabel: 'main' } },
  transformCallback: () => 0,
  invoke: async (cmd: string, args?: unknown) => {
    if (cmd === 'engine_status') return { version: 'mock-fixture', healthy: true };
    if (cmd === 'session_call') return mockSession(args as { cmd: string; payload: Record<string, unknown> });
    if (cmd === 'capability_inventory') return fixture;
    if (cmd === 'preview_open') throw 'Yerel önizleme kapalı. Ayarlardan açılmadıkça hiçbir sayfa gösterilmez.';
    if (cmd.startsWith('plugin:event|')) return 0;
    throw { error: { kind: 'MockUnsupported' }, hint: `mock has no ${cmd}` };
  },
};
