import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { COMMANDS } from '../src/contracts/ipc.ts';
import { bufferOf } from '../src/terminal.ts';
import {
  COMMAND_TEXT, EXPORT_MAX_BYTES, MODE_TEXT, PROJECT_ID, REJECT_TEXT, SESSION_COMMANDS, applyLive, call, exportName, exportTooBig, joinPages, matchSnippet, modeText, notifyReason, orderConversations, reasonText, shouldNotify, stateText, transcriptLines,
  type Relay, type Transcript,
} from '../src/sessionlog.ts';

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
  for (const r of ['TURN_RUNNING', 'LAST_TURN_FAILED', 'SESSION_ENDED', 'NOT_AVAILABLE']) assert.notEqual(reasonText(r), 'Şu an kullanılamaz.');
  assert.equal(reasonText(null), '');
});

const page = (first: number, users: string[], total = 9): Transcript => ({
  id: 'loc_abcdef0123456789', title: 't', project_root: 'C:/p', agent: 'opencode', model: 'a/b', resumable: true, usage: null, live: null, first, total,
  turns: users.map((user) => ({ n: 1, user, result: null })),
});
const users = (t: Transcript): (string | null)[] => t.turns.map((x) => x.user);

test('pages of one conversation join: older in front, newer over the tail, and a hole keeps only the new page', () => {
  assert.deepEqual(joinPages(undefined, page(4, ['e', 'f'])), page(4, ['e', 'f']));
  const older = joinPages(page(4, ['e', 'f']), page(2, ['c', 'd']));
  assert.deepEqual([older.first, users(older)], [2, ['c', 'd', 'e', 'f']]);
  const newer = joinPages(older, { ...page(5, ['F', 'g']), live: { turn: 3, events: [] } }); // the last turn finished and one more began
  assert.deepEqual([newer.first, users(newer), newer.live], [2, ['c', 'd', 'e', 'F', 'g'], { turn: 3, events: [] }]);
  assert.deepEqual(users(joinPages(page(0, ['a']), page(5, ['f']))), ['f']); // turns 1-4 were never read: nothing is shown as if they were
  assert.deepEqual(users(joinPages(page(4, ['e', 'f']), page(4, ['e', 'f', 'g']))), ['e', 'f', 'g']);
  const ahead = { turn: 3, events: [{ kind: 'message' }, { kind: 'message' }] }, behind = { turn: 3, events: [{ kind: 'message' }] };
  assert.equal(joinPages({ ...page(4, ['e']), live: ahead }, { ...page(4, ['e']), live: behind }).live, ahead); // a late page does not take pushed events back
  assert.equal(joinPages({ ...page(4, ['e']), live: ahead }, page(4, ['e'])).live, null); // but the turn's end does
});

test('pushed events extend the running turn in order; a repeat is ignored and a missed one asks for a fresh read', () => {
  const ev = (seq: unknown) => ({ kind: 'message', seq });
  const one = applyLive(null, 2, ev(0));
  assert.deepEqual(one, { turn: 2, events: [ev(0)] });
  assert.deepEqual(applyLive(one, 2, ev(1))?.events.length, 2);
  assert.equal(applyLive(one, 2, ev(0)), one);
  assert.equal(applyLive(one, 2, ev(2)), null);
  assert.equal(applyLive(null, 2, ev(3)), null);
  assert.equal(applyLive(one, 2, ev('1')), null);
  assert.deepEqual(applyLive(one, 3, ev(0)), { turn: 3, events: [ev(0)] }); // a new turn starts from nothing
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
  const gone: Relay = async () => { throw { error: { kind: 'NotInstalled' } }; };
  assert.deepEqual(await call(gone, 'session.send', {}), { ok: false, text: 'Motor kurulu değil.' });
  const weird: Relay = async () => { throw 'boom'; };
  assert.deepEqual(await call(weird, 'session.send', {}), { ok: false, text: 'Motora ulaşılamadı.' });
});

test('a refusal is worded from the engine\'s reason code, never from its message text', async () => {
  const bad: Relay = async () => ({ ok: false, result: null, error: { code: 'ENGINE_ERROR', message: 'Model is not on the agent\'s list', reason: 'MODEL_INVALID' } });
  assert.deepEqual(await call(bad, 'session.start', {}), { ok: false, text: 'Bu model ajanın listesinde yok.' });
  const root: Relay = async () => ({ ok: false, result: null, error: { code: 'BAD_REQUEST', message: 'x', reason: 'ROOT_INVALID' } });
  assert.match(((await call(root, 'session.start', {})) as { text: string }).text, /klasör/i);
});

test('the screen carries no model, agent or start rule of its own', () => {
  const src = readFileSync(new URL('../src/sessionlog.ts', import.meta.url), 'utf8');
  for (const word of ['DEFAULT_MODEL', 'AGENTS', 'startProblem', 'deepseek']) assert.ok(!src.includes(word), word);
});

test('the screen, the Rust relay and the engine contract list exactly the same session commands', () => {
  const rust = readFileSync(new URL('../src-tauri/src/catalog.rs', import.meta.url), 'utf8');
  const block = /pub const SESSION_COMMANDS: \[&str; (\d+)\] = \[([^\]]*)\]/.exec(rust);
  assert.ok(block, 'SESSION_COMMANDS not found in catalog.rs');
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

test('every permission mode has a name and says what the agent may do; an unknown one is shown by its id, never as a known one', () => {
  assert.deepEqual(Object.keys(MODE_TEXT), ['default', 'accept-edits', 'bypass-permissions']);
  assert.equal(new Set(Object.values(MODE_TEXT).map(([name]) => name)).size, 3);
  assert.equal(modeText('plan')[0], 'plan');
  assert.ok(SESSION_COMMANDS.includes('session.mode.set'));
});

test('an OS notice follows only a real turn end, and never the session the person is already looking at', () => {
  assert.equal(notifyReason(undefined, 'idle'), null);
  assert.equal(notifyReason('running', 'running'), null);
  assert.equal(notifyReason('idle', 'running'), null);
  assert.equal(notifyReason('running', 'idle'), 'turn-finished');
  assert.equal(notifyReason('running', 'failed'), 'failed');
  assert.equal(notifyReason('idle', 'ended'), 'ended');
  assert.equal(shouldNotify('running', 'idle', true, true), null);
  assert.equal(shouldNotify('running', 'idle', true, false), 'turn-finished');
  assert.equal(shouldNotify('running', 'idle', false, true), 'turn-finished');
});

test('the history tools word every engine refusal in Turkish', () => {
  for (const code of ['TITLE_EMPTY', 'TITLE_TOO_LONG', 'TITLE_INVALID', 'TITLE_UNSAFE', 'PIN_INVALID', 'ARCHIVE_INVALID', 'EXPORT_INVALID']) {
    assert.ok(REJECT_TEXT[code], code);
    assert.match(REJECT_TEXT[code], /[çğıöşü]/i, code);
    assert.ok(!REJECT_TEXT[code].startsWith('Motor reddetti'), code);
  }
});

test('sidebar order: pinned first, then newest, without touching the engine rows', () => {
  const rows = [
    { id: 'old', pinned: false, updated: 10 }, { id: 'pinned-old', pinned: true, updated: 1 },
    { id: 'new', pinned: false, updated: 30 }, { id: 'pinned-new', pinned: true, updated: 20 },
  ];
  assert.deepEqual(orderConversations(rows).map((r) => r.id), ['pinned-new', 'pinned-old', 'new', 'old']);
  assert.deepEqual(rows.map((r) => r.id), ['old', 'pinned-old', 'new', 'pinned-new']); // input is not reordered in place
  assert.deepEqual(orderConversations([]), []);
});

test('an exported file name cannot become a path, and JSON is always the same name', () => {
  assert.equal(exportName('Sohbet', 'markdown'), 'Sohbet.md');
  assert.equal(exportName('Toplantı notları 2026', 'json'), 'sohbet.json');
  assert.equal(exportName('a/b\\c:d*e?f"g<h>i|j', 'markdown'), 'a b c d e f g h i j.md');
  assert.equal(exportName('..', 'markdown'), 'sohbet.md');
  assert.equal(exportName('  ...  ', 'markdown'), 'sohbet.md');
  assert.equal(exportName('', 'markdown'), 'sohbet.md');
  assert.equal(exportName('\u0000\u001f', 'markdown'), 'sohbet.md');
  const long = exportName('a'.repeat(200), 'markdown');
  assert.equal(long, `${'a'.repeat(80)}.md`);
  assert.equal(exportName('Sohbet. . .', 'markdown'), 'Sohbet.md');
});

test('export size is counted in UTF-8 bytes, so a multi-byte title cannot sneak past 4 MB', () => {
  assert.equal(exportTooBig('a'.repeat(EXPORT_MAX_BYTES)), false);
  assert.equal(exportTooBig('a'.repeat(EXPORT_MAX_BYTES + 1)), true);
  assert.equal(exportTooBig('ş'.repeat(EXPORT_MAX_BYTES / 2)), false);
  assert.equal(exportTooBig('ş'.repeat(EXPORT_MAX_BYTES / 2 + 1)), true);
  assert.equal(exportTooBig(''), false);
});

test('a search hit is one plain line: control characters dropped, spaces collapsed, capped at 140', () => {
  assert.equal(matchSnippet('  a\n\tb  '), 'a b');
  assert.equal(matchSnippet('\u0000\u001b[31mred'), '[31mred');
  assert.equal(matchSnippet(null), '');
  assert.equal(matchSnippet(undefined), '');
  assert.equal(matchSnippet('x'.repeat(200)).length, 140);
});
