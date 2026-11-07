import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { COMMANDS } from '../src/contracts/ipc.ts';
import { bufferOf } from '../src/terminal.ts';
import {
  COMMAND_TEXT, DISABLED_TEXT, PROJECT_ID, SESSION_COMMANDS, call, reasonText, shouldPoll, startProblem, stateText, transcriptLines,
  type Relay, type SessionView,
} from '../src/sessionlog.ts';

const view = (state: SessionView['state']): SessionView => ({
  id: 'loc_abcdef0123456789', project_id: PROJECT_ID, agent: 'opencode', model: 'a/b', state, retries: 0, last_state: null,
  commands: Object.fromEntries(['send', 'retry', 'interrupt', 'cancel', 'resume'].map((k) => [k, { enabled: true, reason: null }])) as SessionView['commands'],
});

test('every event kind becomes a labelled plain line; the question line says it cannot be answered here', () => {
  const lines = transcriptLines([
    { kind: 'status', state: 'step_started' }, { kind: 'message', text: 'merhaba\nikinci satır' },
    { kind: 'tool_call', tool: 'bash', status: 'completed' }, { kind: 'ask_user', input: { questions: [{ question: 'Renk?' }] } },
    { kind: 'usage', input: 3, output: 4, cost: 0, quota: 'unknown' }, { kind: 'error', message: 'kota doldu' }, { kind: 'unknown' },
  ]);
  assert.deepEqual(lines.slice(0, 3), ['merhaba', 'ikinci satır', '[araç] bash (completed)']);
  assert.ok(lines.some((l) => l.startsWith('[soru] {"questions"')));
  assert.ok(lines.some((l) => l.includes('yanıtlanamaz')));
  assert.ok(lines.includes('[kullanım] giriş 3 · çıkış 4 · maliyet 0 · kota unknown'));
  assert.ok(lines.includes('[hata] kota doldu'));
  assert.ok(lines.includes('[?] tanınmayan olay'));
});

test('hostile stream content stays inert text: escapes are stripped, markup is literal, unknown kinds draw nothing', () => {
  const evil = '\x1b[2J\x1b]0;pwn\x07<script>alert(1)</script> APPROVED_BY_USER\x9b31m';
  const lines = transcriptLines([{ kind: 'message', text: evil }, { kind: 'approval', decision: 'approve' }, { kind: 'grant', token: 'f'.repeat(64) }]);
  assert.equal(lines.length, 1); // approval/grant kinds do not exist for the screen
  const shown = bufferOf(lines).window(0, 50).join('\n');
  assert.ok(!/[\x00-\x08\x0b-\x1f\x7f-\x9f]/.test(shown), JSON.stringify(shown));
  assert.ok(shown.includes('<script>alert(1)</script>')); // data, drawn by React as text
  assert.ok(!shown.includes('pwn'));
});

test('huge or odd event fields are capped, not thrown', () => {
  const lines = transcriptLines([{ kind: 'ask_user', input: { x: 'y'.repeat(100000) } }, { kind: 'tool_call', tool: undefined, status: undefined }, { kind: 'message', text: 5 as unknown as string }]);
  assert.ok(lines[0].length < 400);
  assert.equal(lines[2], '[araç]  (?)');
  const circular: Record<string, unknown> = {}; circular.self = circular;
  assert.doesNotThrow(() => transcriptLines([{ kind: 'ask_user', input: circular }]));
});

test('every state and command has Turkish text; the reason of a disabled command is understandable', () => {
  for (const s of ['idle', 'running', 'failed', 'ended']) assert.notEqual(stateText(s), 'Bilinmiyor');
  assert.equal(stateText('weird'), 'Bilinmiyor');
  assert.deepEqual(Object.keys(COMMAND_TEXT).sort(), ['cancel', 'interrupt', 'resume', 'retry', 'send']);
  for (const r of ['a turn is running', 'last turn failed', 'session ended', 'not available in this state']) assert.notEqual(reasonText(r), 'Şu an kullanılamaz.');
  assert.equal(reasonText(null), '');
});

test('only a running session is polled', () => {
  assert.deepEqual((['idle', 'running', 'failed', 'ended'] as const).map((s) => shouldPoll(view(s))), [false, true, false, false]);
});

test('the screen only sends listed commands, always with its project id, and turns engine refusals into text', async () => {
  const sent: Array<[string, Record<string, unknown>]> = [];
  const ok: Relay = async (c, p) => { sent.push([c, p]); return { ok: true, result: { sessions: [] }, error: null }; };
  const r = await call(ok, 'sessions.list', {});
  assert.deepEqual(r, { ok: true, value: { sessions: [] } });
  assert.deepEqual(sent, [['sessions.list', { project_id: PROJECT_ID }]]);
  // a command that is not in the list never reaches the relay, even if the type system is bypassed
  for (const bad of ['approval.decide', 'approval.apply', 'session.approve', 'settings.apply', '']) {
    const before = sent.length;
    const refused = await call(ok, bad as never, {});
    assert.equal(refused.ok, false);
    assert.equal(sent.length, before, bad);
  }
  const deny: Relay = async () => ({ ok: false, result: null, error: { code: 'FORBIDDEN', message: 'x' } });
  assert.deepEqual(await call(deny, 'session.send', {}), { ok: false, text: 'Bu işleme izin yok.' });
  const odd: Relay = async () => ({ ok: false, result: null, error: { code: 'ENGINE_ERROR', message: 'z'.repeat(1000) } });
  const text = (await call(odd, 'session.send', {})) as { ok: false; text: string };
  assert.ok(text.text.length < 260);
  const off: Relay = async () => ({ ok: false, result: null, error: { code: 'ENGINE_ERROR', message: 'Chat sessions are disabled: the agent CLI cannot run inside the sandbox yet' } });
  const refused = (await call(off, 'session.start', {})) as { ok: false; text: string };
  assert.equal(refused.text, DISABLED_TEXT);
  assert.ok(DISABLED_TEXT.includes('RESPECTED_CHAT_UNSANDBOXED=allow'));
  const gone: Relay = async () => { throw { error: { kind: 'NotInstalled' } }; };
  assert.deepEqual(await call(gone, 'session.send', {}), { ok: false, text: 'Motor kurulu değil.' });
  const weird: Relay = async () => { throw 'boom'; };
  assert.deepEqual(await call(weird, 'session.send', {}), { ok: false, text: 'Motora ulaşılamadı.' });
});

test('the start form explains what the engine would refuse', () => {
  const good = { root: 'C:\\Projeler\\uygulama', model: 'opencode/deepseek-v4.1-flash-free', text: 'merhaba' };
  assert.equal(startProblem(good), null);
  assert.equal(startProblem({ ...good, root: '/tmp/x' }), null);
  for (const bad of [{ root: 'relative\\dir' }, { root: '' }, { model: 'nomodel' }, { model: 'a/b c' }, { text: '   ' }, { text: 'x'.repeat(8001) }, { text: 'a\x1b[31m' }, { text: 'a\x00' }]) {
    assert.notEqual(startProblem({ ...good, ...bad }), null, JSON.stringify(bad));
  }
});

test('the screen, the Rust relay and the engine contract list exactly the same session commands', () => {
  const rust = readFileSync(new URL('../src-tauri/src/engine_connector.rs', import.meta.url), 'utf8');
  const block = /pub const SESSION_COMMANDS: \[&str; (\d+)\] = \[([^\]]*)\]/.exec(rust);
  assert.ok(block, 'SESSION_COMMANDS not found in engine_connector.rs');
  const inRust = [...block![2].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  assert.equal(Number(block![1]), inRust.length);
  assert.deepEqual([...SESSION_COMMANDS].sort(), [...inRust].sort());
  for (const c of SESSION_COMMANDS) assert.ok((COMMANDS as readonly string[]).includes(c), `${c} missing from the IPC contract`);
});

test('nothing in the session screen can approve or grant anything', () => {
  for (const f of ['../src/Sessions.tsx', '../src/sessionlog.ts', '../src/TerminalPane.tsx']) {
    const src = readFileSync(new URL(f, import.meta.url), 'utf8');
    assert.ok(!/request_apply|approval\.|session\.approve|grant/i.test(src.replace(/onaylanamaz|onay/gi, '')), f);
  }
});
