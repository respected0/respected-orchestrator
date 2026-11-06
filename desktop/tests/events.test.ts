import test from 'node:test';
import assert from 'node:assert/strict';
import { applyEvents, fromSnapshot, type EventRecord } from '../src/events.ts';

const ev = (seq: number, run: string | null = 'r1', type = 'step'): EventRecord => ({ seq, op: `op-${seq}`, run, type });
const empty = fromSnapshot({ last_seq: 0, state: {}, state_hash: '' });

test('events apply in order and duplicates are ignored', () => {
  const m = applyEvents(empty, [ev(1), ev(2), ev(2), ev(1), ev(3, 'r2', 'done')]);
  assert.equal(m.lastSeq, 3);
  assert.deepEqual(m.runs, { r1: { seq: 2, type: 'step' }, r2: { seq: 3, type: 'done' } });
  assert.equal(m.needsResync, false);
});

test('a hole asks for a resync and nothing after it is applied', () => {
  const m = applyEvents(empty, [ev(1), ev(3), ev(4)]);
  assert.equal(m.needsResync, true);
  assert.equal(m.lastSeq, 1);
});

test('snapshot then missed events reaches the same state as a full replay', () => {
  const all = Array.from({ length: 50 }, (_, i) => ev(i + 1, `r${i % 3}`, i % 2 ? 'a' : 'b'));
  const full = applyEvents(empty, all);
  const snap = applyEvents(empty, all.slice(0, 20));
  const resumed = applyEvents(fromSnapshot({ last_seq: snap.lastSeq, state: snap.runs, state_hash: '' }), all.slice(20));
  assert.deepEqual(resumed, full);
});
