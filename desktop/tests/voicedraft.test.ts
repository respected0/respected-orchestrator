import test from 'node:test';
import assert from 'node:assert/strict';
import { CHUNK_BYTES, chunks, confirmedText, draftView, errorText, highStakesNote, indicator, level, marks, statusView, suggestions, toBase64, toPcm16, VOICE_COMMANDS } from '../src/voicedraft.ts';
import { COMMANDS } from '../src/contracts/ipc.ts';

const ok = (result: unknown) => ({ ok: true, result, error: null });
const DRAFT = { draft_id: 'vd-1', language: 'en', text: 'Fix the parse config and run the pytest tests', original: 'Fix the parse config and run the ptest tests',
  corrections: [{ heard: 'ptest', replaced_with: 'pytest', at: 33, applied: true, score: 0.9 }, { heard: 'unitist', replaced_with: 'unittest', at: 0, applied: false, score: 0.8 }],
  confidence: 0.9, high_stakes_words: [], needs_review: true, confirmed: false, source: 'voice' };

test('every voice command exists in the IPC contract', () => {
  for (const c of VOICE_COMMANDS) assert.ok((COMMANDS as readonly string[]).includes(c), c);
  assert.ok(!VOICE_COMMANDS.some((c) => /confirm|approve|apply/.test(c)));
});

test('status and draft shapes: anything else is an error view, never a green or empty one', () => {
  const s = statusView(ok({ enabled: false, engine_ready: false, state: 'idle', max_seconds: 60, audio_bytes_held: 0 }));
  assert.equal(s.kind, 'status');
  assert.equal(statusView(ok({ enabled: 'yes' })).kind, 'error');
  assert.equal(statusView(null).kind, 'error');
  assert.equal(draftView(ok(DRAFT)).kind, 'draft');
  for (const bad of [{ ...DRAFT, confirmed: true }, { ...DRAFT, needs_review: false }, { ...DRAFT, source: 'typed' }, { ...DRAFT, language: 'de' }, { ...DRAFT, text: 5 }]) {
    assert.equal(draftView(ok(bad)).kind, 'error', JSON.stringify(bad).slice(0, 60));
  }
});

test('engine errors become sentences and keep the typed-entry fallback in sight', () => {
  const e = draftView({ ok: false, result: null, error: { code: 'ENGINE_ERROR', message: 'NO_ENGINE: no offline speech engine is configured' } });
  assert.equal(e.kind, 'error');
  assert.match((e as any).text, /ayarlanmamış/);
  assert.match((e as any).hint, /yazarak/);
  assert.match(errorText('VOICE_OFF: voice input is switched off'), /kapalı/);
  assert.equal(errorText('SOMETHING_NEW: x'), 'SOMETHING_NEW: x');
});

test('nothing leaves the screen until the person accepted a non-empty text', () => {
  const d = draftView(ok(DRAFT)) as any;
  assert.equal(confirmedText(null, 'typed', true), null);
  assert.equal(confirmedText(d, 'hello', false), null);
  assert.equal(confirmedText(d, '   ', true), null);
  assert.equal(confirmedText(d, 'x'.repeat(4001), true), null);
  assert.equal(confirmedText(d, '  fixed text ', true), 'fixed text');
});

test('applied corrections are marked where they sit; near misses are only suggestions', () => {
  const d = draftView(ok(DRAFT)) as any;
  const m = marks(d);
  assert.equal(m.map((x) => x.text).join(''), d.text);
  assert.deepEqual(m.filter((x) => x.hint).map((x) => x.text), ['pytest']);
  assert.deepEqual(suggestions(d).map((c) => c.heard), ['unitist']);
  const stale = { ...d, corrections: [{ heard: 'a', replaced_with: 'zzz', at: 3, applied: true, score: 1 }] };
  assert.equal(marks(stale).map((x) => x.text).join(''), d.text); // a stale offset is ignored rather than corrupting the text
});

test('high-stakes words are explained as plain text', () => {
  const d = draftView(ok({ ...DRAFT, high_stakes_words: ['approve', 'apply'] })) as any;
  assert.match(highStakesNote(d)!, /yalnızca metindir/);
  assert.equal(highStakesNote(draftView(ok(DRAFT)) as any), null);
});

test('audio: 48 kHz float -> 16 kHz little-endian 16-bit; chunks stay under the request limit and round-trip', () => {
  const input = new Float32Array(4800).map((_, i) => Math.sin(i / 10));
  const pcm = toPcm16(input, 48000);
  assert.equal(pcm.length, 1600 * 2);
  assert.equal(toPcm16(new Float32Array([2, -2, 0.5]), 16000).length, 6);
  const clipped = new DataView(toPcm16(new Float32Array([5, -5]), 16000).buffer);
  assert.deepEqual([clipped.getInt16(0, true), clipped.getInt16(2, true)], [32767, -32768]);
  const big = new Uint8Array(CHUNK_BYTES * 2 + 5).fill(7);
  const parts = [...chunks(big)];
  assert.deepEqual(parts.map((p) => p.length), [CHUNK_BYTES, CHUNK_BYTES, 5]);
  assert.ok(toBase64(parts[0]).length + 200 < 65536);
  assert.equal(Buffer.from(toBase64(big), 'base64').length, big.length);
  assert.throws(() => toPcm16(input, 0), RangeError);
});

test('level meter and the microphone indicator: only "recording" says the microphone is open', () => {
  assert.equal(level(new Float32Array(0)), 0);
  assert.ok(level(new Float32Array(100).fill(0.5)) > 0.9);
  assert.equal(level(new Float32Array(100)), 0);
  assert.equal(indicator('recording').micOpen, true);
  for (const p of ['idle', 'transcribing', 'review', 'error'] as const) assert.equal(indicator(p).micOpen, false, p);
});
