import test from 'node:test';
import assert from 'node:assert/strict';
import { activityView, newestCursor, projectsView, runsView, stateInfo, when } from '../src/boardviews.ts';

const run = { run_id: 'run-20261108120000-aaaaaaaaaaaa', state: 'done', task: 'oku', kind: 'read', agent: 'codex', project_root: 'C:/p', created_at: '2026-11-08T12:00:00Z', updated_at: null, error: null };

test('runs: documented rows become rows; any other shape is an error, never an empty list', () => {
  const v = runsView({ ok: true, result: { runs: [run], next_cursor: 'x' } });
  assert.equal(v.kind === 'rows' && v.rows[0].agent, 'codex');
  assert.equal(v.kind === 'rows' && v.more, true);
  assert.equal(runsView({ ok: true, result: { runs: [] } }).kind, 'rows');
  for (const bad of [null, { ok: false, error: { message: 'boom' } }, { ok: true, result: {} }, { ok: true, result: { runs: [1] } }, 'x']) assert.equal(runsView(bad).kind, 'error');
  assert.match((runsView({ ok: false, error: { message: 'boom' } }) as { text: string }).text, /boom/);
});

test('projects keep their stages; a malformed project hides the whole list', () => {
  const p = { project_id: 'proj-a', state: 'running', goal: 'hedef', created_at: null, alive: true, error: null, stages: [{ name: 'a', status: 'done', after: ['b', 3], attempts: 2 }] };
  const v = projectsView({ ok: true, result: { projects: [p] } });
  assert.deepEqual(v.kind === 'rows' && v.rows[0].stages, [{ name: 'a', status: 'done', after: ['b'], attempts: 2 }]);
  assert.equal(projectsView({ ok: true, result: { projects: [{ goal: 'no id' }] } }).kind, 'error');
});

test('activity rows and the newest-page cursor', () => {
  const v = activityView({ ok: true, result: { events: [{ seq: 5, ts: 10, op: 'o', run: null, type: 't', stage: 'running' }], has_more: true, last_seq: 300 } });
  assert.equal(v.kind === 'rows' && v.lastSeq, 300);
  assert.equal(activityView({ ok: true, result: { events: [{ seq: 'x' }] } }).kind, 'error');
  assert.equal(newestCursor(300, 100), 200);
  assert.equal(newestCursor(20, 100), 0);
});

test('states have Turkish text, unknown ones are shown as given; unreadable times are dashes', () => {
  assert.equal(stateInfo('in_progress').text, 'Çalışıyor');
  assert.equal(stateInfo('weird').text, 'weird');
  assert.equal(when(null), '—');
  assert.equal(when('not a date'), '—');
  assert.notEqual(when(1_700_000_000), '—');
});
