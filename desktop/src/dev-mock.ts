// Development only (loaded from main.tsx behind `import.meta.env.DEV` and `?mock`): a stand-in for the Tauri bridge so the screens can be
// looked at in a plain browser. The data is a fixture the real engine produced from a synthetic home; it is never part of a production build.
import fixture from '../tests/fixtures/inventory.json';
import beta4 from '../tests/fixtures/beta4.json';

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
    if (cmd === 'attach_image' || cmd === 'share_image' || cmd === 'revoke_image') return mockAttachConsent(cmd, args as Record<string, any>);
    if ((cmd === 'session_call' || cmd === 'read_call') && (args as { cmd: string }).cmd.startsWith('attachment.')) return mockAttachment(args as { cmd: string; payload: Record<string, any> });
    if (cmd === 'session_call' && (args as { cmd: string }).cmd.startsWith('voice.')) return mockVoice(args as { cmd: string; payload: Record<string, any> });
    if (cmd === 'read_call' && (args as { cmd: string }).cmd === 'voice.status') return { ipc: '1', id: 'mock', ok: true, error: null, result: { enabled: true, engine_ready: true, state: 'idle', audio_bytes_held: 0, closed_reason: null, max_seconds: 60, sample_rate: 16000, network_isolated: false } };
    if (cmd === 'session_call') return mockSession(args as { cmd: string; payload: Record<string, unknown> });
    if (cmd === 'capability_inventory') return fixture;
    if (cmd === 'read_call') {  // replies the real engine produced from a synthetic data root (tests/tools/make_beta4_fixture.py)
      const c = (args as { cmd: string }).cmd;
      return c === 'team.view' ? beta4.team : c === 'capabilities.recommend' ? beta4.suggestions : c === 'analytics.summary' ? beta4.usage : Promise.reject({ error: { kind: 'Refused' }, hint: 'Bu komut ekrandan çağrılamaz.' });
    }
    if (cmd === 'preview_open') throw 'Yerel önizleme kapalı. Ayarlardan açılmadıkça hiçbir sayfa gösterilmez.';
    if (cmd.startsWith('plugin:event|')) return 0;
    throw { error: { kind: 'MockUnsupported' }, hint: `mock has no ${cmd}` };
  },
};

// Push-to-talk stand-in: counts the bytes it receives and answers with a draft shaped like the engine's (tests/engine/test_voice_api.py).
let heldBytes = 0;
function mockVoice({ cmd, payload }: { cmd: string; payload: Record<string, any> }) {
  const ok = (result: unknown) => ({ ipc: '1', id: 'mock', ok: true, result, error: null });
  if (cmd === 'voice.start') { heldBytes = 0; return ok({ token: 'mocktoken', sample_rate: 16000, max_seconds: 60 }); }
  if (cmd === 'voice.feed') { if (payload.permission !== 'granted') { heldBytes = 0; return { ipc: '1', id: 'mock', ok: false, result: null, error: { code: 'ENGINE_ERROR', message: 'PERMISSION_REVOKED: x' } }; } heldBytes += atob(payload.chunk).length; return ok({ held: heldBytes }); }
  if (cmd === 'voice.cancel') { heldBytes = 0; return ok({ state: 'idle', audio_bytes_held: 0 }); }
  const bytes = heldBytes; heldBytes = 0;
  return ok({ draft_id: 'vd-mock', language: payload.language, text: `Parse config fonksiyonunu düzelt ve pytest testlerini çalıştır (${bytes} bayt ses)`, original: 'Parse config fonksiyonunu düzelt ve ptest testlerini çalıştır',
    corrections: [{ heard: 'ptest', replaced_with: 'pytest', at: 43, applied: true, score: 0.9 }], confidence: 0.9, high_stakes_words: ['sil'], needs_review: true, confirmed: false, source: 'voice' });
}

// Screenshot stand-in: keeps what it is sent and "cleans" nothing; the real cleaning is tested in tests/engine/test_attachment*.py.
const okReply = (result: unknown) => ({ ipc: '1', id: 'mock', ok: true, result, error: null });
let upload: number[] = [];
let stagedData = '';
const rows: Record<string, any>[] = [];
function mockAttachment({ cmd, payload }: { cmd: string; payload: Record<string, any> }) {
  if (cmd === 'attachment.status') return okReply({ enabled: true, state: 'idle', held: 0, max_bytes: 8388608, max_side: 8192, chunk_bytes: 49152, stage_seconds: 600 });
  if (cmd === 'attachment.arm') { upload = []; return okReply({ token: 'mocktoken', chunk_bytes: 49152 }); }
  if (cmd === 'attachment.part') { upload.push(...atob(payload.chunk).split('').map((c) => c.charCodeAt(0))); return okReply({ held: upload.length }); }
  if (cmd === 'attachment.stage') { stagedData = btoa(String.fromCharCode(...upload.slice(0, 200000))); return okReply({ stage_id: 'stg-0123456789abcdef', sha256: 'a'.repeat(64), mime: 'image/png', width: 64, height: 48, bytes: upload.length, metadata_removed_bytes: 0, expires_in: 600 }); }
  if (cmd === 'attachment.preview') return okReply({ stage_id: payload.stage_id, sha256: 'a'.repeat(64), mime: 'image/png', width: 64, height: 48, data: stagedData });
  if (cmd === 'attachment.list') return okReply({ run_id: payload.run_id, attachments: rows });
  if (cmd === 'attachment.cancel') { upload = []; return okReply({ state: 'idle', held: 0 }); }
  rows.length = 0; return okReply({ removed: 2 });
}
function mockAttachConsent(cmd: string, a: Record<string, any>) {
  if (cmd === 'attach_image') { rows.push({ id: 'att-0123456789abcdef', width: 64, height: 48, bytes: upload.length, redacted_regions: a.regions, expires_at: 0, shared_with_model: false, consent: { state: 'none' } }); return { id: rows[0].id }; }
  if (cmd === 'share_image') { rows[0].consent = { state: 'active', provider: a.provider }; return {}; }
  rows[0].consent = { state: 'revoked' }; return {};
}
