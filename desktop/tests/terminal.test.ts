import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { EMPTY_LAYOUT, MAX_LINES, MAX_PANES, TerminalBuffer, closePane, gridFor, openPane, planPaste, setSplit } from '../src/terminal.ts';

const text = (b: TerminalBuffer) => b.window(0, 100_000);

test('plain, Turkish and emoji text pass through unchanged', () => {
  const b = new TerminalBuffer();
  b.write('Merhaba dünya İıŞşĞğÜüÖöÇç ✓ 🙂 日本語\nikinci satır\n');
  assert.deepEqual(text(b), ['Merhaba dünya İıŞşĞğÜüÖöÇç ✓ 🙂 日本語', 'ikinci satır']);
});

test('ANSI colour, cursor, OSC title/hyperlink and DCS sequences are swallowed, not drawn', () => {
  const b = new TerminalBuffer();
  b.write('a\x1b[31mred\x1b[0m \x1b[2J\x1b[H\x1b]0;evil title\x07b \x1b]8;;http://x\x1b\\link\x1b]8;;\x1b\\ \x1bPq#0;2;0;0;0\x1b\\c \x1b(Bd\x1b=e\n');
  assert.deepEqual(text(b), ['ared b link c de']);
});

test('an escape sequence split across chunks (even byte by byte) is still swallowed', () => {
  const src = 'x\x1b[38;2;1;2;3mY\x1b]0;title\x07Z\x1b]8;;u\x1b\\W\n';
  const whole = new TerminalBuffer(); whole.write(src);
  const bytes = new TerminalBuffer(); for (const ch of src) bytes.write(ch);
  assert.deepEqual(text(bytes), text(whole));
  assert.deepEqual(text(whole), ['xYZW']);
});

test('control characters and bidi overrides are removed', () => {
  const b = new TerminalBuffer();
  b.write('a\x00b\x07c\x7fd\u009be\u202efdp.exe\u2066\u2029g\n');
  assert.deepEqual(text(b), ['abcdefdp.exeg']);
});

test('Windows CRLF is one newline; lone CR overwrites the line (progress bar shows its last state); backspace erases', () => {
  const b = new TerminalBuffer();
  b.write('one\r\ntwo\r\n');
  b.write('10%\r50%\r100%\ndone\b\bne\n');
  assert.deepEqual(text(b), ['one', 'two', '100%', 'do' + 'ne']);
  const split = new TerminalBuffer(); split.write('a\r'); split.write('\nb\n');
  assert.deepEqual(text(split), ['a', 'b']); // CR and LF in different chunks
});

test('unterminated sequences cannot swallow the rest of the stream forever (CAN/SUB cancel)', () => {
  const b = new TerminalBuffer();
  b.write('\x1b]0;never ended\x18visible\n');
  assert.deepEqual(text(b), ['visible']);
});

test('very long lines are wrapped at the cap; scrollback keeps only the newest MAX_LINES', () => {
  const b = new TerminalBuffer();
  b.write('x'.repeat(10_000) + '\n');
  assert.ok(text(b).every((l) => l.length <= 4_096));
  const c = new TerminalBuffer();
  for (let i = 0; i < MAX_LINES + 500; i++) c.write(`line ${i}\n`);
  assert.equal(c.length, MAX_LINES);
  assert.equal(c.dropped, 500);
  assert.equal(c.window(0, 1)[0], 'line 500');
});

test('10 MB of output: bounded memory, and drawing a window stays interactive at 10k lines', () => {
  const b = new TerminalBuffer();
  const line = 'log line with ünïcode and \x1b[32mcolour\x1b[0m ' + 'z'.repeat(40) + '\r\n'; // ~95 bytes
  const chunk = line.repeat(1_000);
  const t0 = performance.now();
  let bytes = 0;
  while (bytes < 10 * 1024 * 1024) { b.write(chunk); bytes += chunk.length; }
  const ingest = performance.now() - t0;
  assert.equal(b.length, MAX_LINES);
  const t1 = performance.now();
  for (let i = 0; i < 1000; i++) { b.window(MAX_LINES - 60 - (i % 50), 60); b.write('tick\n'); }
  const perFrame = (performance.now() - t1) / 1000;
  console.log(`perf: ingest ${(bytes / 1048576).toFixed(1)} MB in ${ingest.toFixed(0)} ms; window+append ${perFrame.toFixed(3)} ms/frame at ${MAX_LINES} lines`);
  assert.ok(perFrame < 5, `frame ${perFrame} ms`);
  assert.ok(ingest < 20_000, `ingest ${ingest} ms`);
});

test('reconnect: a snapshot restored later continues exactly like the uninterrupted stream', () => {
  const stream = ['alpha\n', 'be\x1b[3', '1mta\n', 'ga\rmma\n', 'del', 'ta\n'];
  const straight = new TerminalBuffer(); for (const c of stream) straight.write(c);
  const first = new TerminalBuffer(); for (const c of stream.slice(0, 2)) first.write(c);
  const resumed = TerminalBuffer.restore(JSON.parse(JSON.stringify(first.snapshot()))); // survives serialisation
  for (const c of stream.slice(2)) resumed.write(c);
  assert.deepEqual(text(resumed), text(straight));
});

test('paste: multi-line needs confirmation, never ends with a submit, and cannot break out of bracketed paste', () => {
  const one = planPaste('ls -la');
  assert.deepEqual(one.ok && [one.text, one.lines, one.needsConfirm], ['ls -la', 1, false]);
  const multi = planPaste('echo a\r\necho b\r\n');
  assert.ok(multi.ok);
  if (multi.ok) assert.deepEqual([multi.text, multi.lines, multi.needsConfirm], ['echo a\necho b', 2, true]);
  const evil = planPaste('safe\x1b[201~\nrm -rf /\x03\x04\u009b');
  assert.ok(evil.ok);
  if (evil.ok) { assert.ok(!/[\x00-\x09\x0b-\x1f\x7f-\x9f]/.test(evil.text)); assert.ok(evil.needsConfirm); assert.ok(!evil.text.includes('201~\x1b')); }
  for (const bad of ['', 'x'.repeat(100_001), 5 as unknown as string]) assert.equal(planPaste(bad).ok, false);
  const long = planPaste('x'.repeat(2_000));
  assert.ok(long.ok && long.needsConfirm);
});

test('panes: closed by default; unsupported or unverified terminal modes never open', () => {
  for (const st of ['unsupported', 'source', 'advertised_missing', undefined, 'whatever']) {
    const r = openPane(EMPTY_LAYOUT, 'opencode', st, 'p1');
    assert.equal(r.ok, false, String(st));
    if (!r.ok) assert.match(r.reason, /başlatılmaz/);
  }
});

test('panes: 2-4 only after opting in; never more than four; close and opt-out shrink the layout', () => {
  let l = EMPTY_LAYOUT;
  const open = (id: string) => { const r = openPane(l, 'a', 'verified', id); if (r.ok) l = r.layout; return r; };
  assert.ok(open('p1').ok);
  assert.equal(open('p2').ok, false); // not opted in
  l = setSplit(l, true);
  assert.ok(open('p2').ok && open('p3').ok && open('p4').ok);
  assert.equal(open('p5').ok, false);
  assert.equal(open('p4').ok, false); // duplicate
  assert.equal(l.panes.length, MAX_PANES);
  assert.deepEqual([1, 2, 3, 4].map((n) => gridFor(n)), [{ rows: 1, cols: 1 }, { rows: 1, cols: 2 }, { rows: 2, cols: 2 }, { rows: 2, cols: 2 }]);
  assert.equal(closePane(l, 'p2').panes.length, 3);
  assert.equal(setSplit(l, false).panes.length, 1);
});

test('against the real engine matrix: no agent has a verified PTY mode in this build, so no pane may start', () => {
  let rows: Record<string, { found: boolean; caps: Record<string, { status: string }> }>;
  try {
    rows = JSON.parse(execFileSync('python', ['-c', 'import json;from respected_orchestrator.engine import agent_adapters as a;print(json.dumps(a.matrix()))'],
      { env: { ...process.env, PYTHONPATH: '../src' }, encoding: 'utf8' }));
  } catch { return; /* no python on this machine: covered by tests/engine/test_conpty_feasibility.py and the Python matrix tests */ }
  for (const [agent, row] of Object.entries(rows)) {
    const r = openPane(EMPTY_LAYOUT, agent, row.caps.pty.status, 'p1');
    assert.equal(r.ok, false, agent);
  }
});
