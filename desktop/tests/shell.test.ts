import test from 'node:test';
import assert from 'node:assert/strict';
import { ROUTES, nextRoute, routeFromHash, screenView } from '../src/shell.ts';

test('five routes exist, every one has an understandable empty text', () => {
  assert.deepEqual(ROUTES.map((r) => r.id), ['projects', 'runs', 'reviews', 'agents', 'settings']);
  for (const r of ROUTES) assert.ok(r.empty.length > 10);
});

test('no data: healthy engine shows the empty state on every route', () => {
  for (const r of ROUTES) assert.equal(screenView(r.id, { phase: 'ready', version: '1', healthy: true }).kind, 'empty');
});

test('a lost or unhealthy engine never looks like success', () => {
  for (const r of ROUTES) {
    assert.equal(screenView(r.id, { phase: 'problem', kind: 'Disconnected', hint: 'x' }).kind, 'error');
    assert.equal(screenView(r.id, { phase: 'ready', version: '1', healthy: false }).kind, 'error');
    assert.equal(screenView(r.id, { phase: 'loading' }).kind, 'loading');
  }
});

test('hash routing falls back to projects for anything unknown', () => {
  assert.equal(routeFromHash('#/agents'), 'agents');
  for (const bad of ['', '#', '#/nope', '#/../x', '#/<script>']) assert.equal(routeFromHash(bad), 'projects');
});

test('keyboard navigation wraps and supports Home/End', () => {
  assert.equal(nextRoute('settings', 'ArrowDown'), 'projects');
  assert.equal(nextRoute('projects', 'ArrowUp'), 'settings');
  assert.equal(nextRoute('runs', 'Home'), 'projects');
  assert.equal(nextRoute('runs', 'End'), 'settings');
  assert.equal(nextRoute('runs', 'a'), null);
});
