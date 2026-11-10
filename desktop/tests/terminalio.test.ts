import test from 'node:test';
import assert from 'node:assert/strict';
import { clampSize, fromBase64, keysToBase64, refusalText, terminalFor, toBase64, type TerminalView } from '../src/terminalio.ts';

test('bytes survive the trip through base64, including a large paste and non-ASCII keys', () => {
  const big = Uint8Array.from({ length: 100_000 }, (_, i) => i % 256);
  assert.deepEqual(fromBase64(toBase64(big)), big);
  assert.equal(new TextDecoder().decode(fromBase64(keysToBase64('şğ\r\x1b[A'))), 'şğ\r\x1b[A');
  assert.equal(keysToBase64('a'), 'YQ==');
});

test('a pane of any size asks for a grid the engine accepts', () => {
  assert.deepEqual(clampSize(3, 1), { cols: 20, rows: 5 });
  assert.deepEqual(clampSize(9999, 9999), { cols: 500, rows: 200 });
  assert.deepEqual(clampSize(120.7, 30.2), { cols: 120, rows: 30 });
  assert.deepEqual(clampSize(NaN, NaN), { cols: 20, rows: 5 });
});

test('the folder gets its newest terminal, whatever the slashes and case, and other folders get none', () => {
  const t = (id: string, project_root: string, started: number): TerminalView => ({ id, project_root, agent: 'opencode', started, alive: true, exit: null, cols: 80, rows: 24 });
  const list = [t('a', 'C:\\p\\one', 1), t('b', 'c:\\P\\one\\', 2), t('c', 'C:\\p\\two', 3)];
  assert.equal(terminalFor(list, 'C:\\p\\one')?.id, 'b');
  assert.equal(terminalFor(list, 'C:\\p\\three'), null);
});

test('refusals are worded from the engine code', () => {
  assert.match(refusalText({ code: 'FORBIDDEN', message: 'Not allowed for this origin.' }), /kurulu masaüstü/);
  assert.match(refusalText({ code: 'ENGINE_ERROR', reason: 'AGENT_NOT_INSTALLED', message: 'x' }), /kurulu değil/);
  assert.match(refusalText({ code: 'ENGINE_ERROR', message: 'something else' }), /something else/);
  assert.match(refusalText({ code: 'ENGINE_ERROR', reason: 'TURN_RUNNING', message: 'x' }), /çalışıyor/);
});
