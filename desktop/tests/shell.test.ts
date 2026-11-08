import test from 'node:test';
import assert from 'node:assert/strict';
import { ROUTES, nextRoute, routeFromHash, screenView } from '../src/shell.ts';

test('ten routes exist, every one has an understandable empty text', () => {
  assert.deepEqual(ROUTES.map((r) => r.id), ['sessions', 'inbox', 'flow', 'tasks', 'projects', 'team', 'capabilities', 'usage', 'settings']);
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

test('hash routing falls back to the chat for anything unknown', () => {
  assert.equal(routeFromHash('#/flow'), 'flow');
  for (const bad of ['', '#', '#/nope', '#/../x', '#/<script>']) assert.equal(routeFromHash(bad), 'sessions');
});

test('keyboard navigation wraps and supports Home/End', () => {
  assert.equal(nextRoute('settings', 'ArrowDown'), 'sessions');
  assert.equal(nextRoute('sessions', 'ArrowUp'), 'settings');
  assert.equal(nextRoute('flow', 'Home'), 'sessions');
  assert.equal(nextRoute('flow', 'End'), 'settings');
  assert.equal(nextRoute('flow', 'a'), null);
});

import { closeDecision } from '../src/shell.ts';

test('closing is free when idle and informs (never kills) when runs are active', () => {
  assert.deepEqual(closeDecision('close-window', 0), { allow: true });
  const d = closeDecision('quit-app', 2);
  assert.equal(d.allow, false);
  if (!d.allow) assert.match(d.message, /durdurmaz/);
});
