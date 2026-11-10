import test from 'node:test';
import assert from 'node:assert/strict';
import { cardAction, displayText, lanesOf, activityView, newestCursor, projectsView, readyAgents, runsView, startedView, stateInfo, taskRequest, when } from '../src/boardviews.ts';

const run = { run_id: 'run-20261108120000-aaaaaaaaaaaa', state: 'done', lane: 'archive', display: 'done', task: 'oku', kind: 'read', agent: 'codex', project_root: 'C:/p', created_at: '2026-11-08T12:00:00Z', updated_at: null, error: null };

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

test('new task: the form becomes the engine request; gaps are named before anything is sent', () => {
  const f = { root: ' C:/p ', task: ' oku ', kind: 'read' as const, worker: '', ownership: 'src\n\n docs ', acceptance: '' };
  assert.deepEqual(taskRequest(f), { ok: true, value: { project_root: 'C:/p', task: 'oku', kind: 'read', ownership: ['src', 'docs'] } });
  assert.deepEqual(taskRequest({ ...f, kind: 'write', worker: 'codex', acceptance: 'python -m pytest -q\n' }),
    { ok: true, value: { project_root: 'C:/p', task: 'oku', kind: 'write', ownership: ['src', 'docs'], worker: 'codex', acceptance: [['python', '-m', 'pytest', '-q']] } });
  for (const bad of [{ ...f, root: ' ' }, { ...f, task: '' }, { ...f, ownership: '\n' }, { ...f, kind: 'write' as const }]) assert.equal(taskRequest(bad).ok, false);
});

test('new task: the reply is a run id or the engine refusal in words; only ready agents are offered', () => {
  assert.deepEqual(startedView({ ok: true, result: { run_id: 'run-1' } }), { ok: true, value: 'run-1' });
  assert.equal(startedView({ ok: true, result: {} }).ok, false);
  assert.match((startedView({ ok: false, error: { code: 'ENGINE_ERROR', message: 'add a command prefix to the Orchestrator setting mcp_acceptance_allow' } }) as { text: string }).text, /izin listenizde yok/);
  assert.match((startedView({ ok: false, error: { code: 'ENGINE_ERROR', message: 'Select the Git project root' } }) as { text: string }).text, /Motor reddetti: Select the Git project root/);
  assert.match((startedView(null) as { text: string }).text, /yanıt vermedi/);
  const agents = [{ agent: 'codex', readiness: { effective: 'ready' } }, { agent: 'claude', readiness: { effective: 'not_ready' } }, { agent: 'custom', readiness: { effective: 'ready' } }, { nope: 1 }];
  assert.deepEqual(readyAgents({ ok: true, result: { agents } }), ['codex']);
  assert.deepEqual(readyAgents({ ok: false }), []);
});

test('board: lanes come from the engine, an unknown lane stays in sight, and a card offers only what fits its state', () => {
  const row = (run_id: string, state: string, lane: string, display: string) => ({ run_id, state, lane, display, task: '', kind: null, agent: null, project_root: null, created_at: null, updated_at: null, error: null });
  const rows = [row('a', 'in_progress', 'working', 'in_progress'), row('b', 'done', 'ready', 'awaiting_approval'), row('c', 'failed', 'needs_you', 'failed'), row('d', 'done', 'archive', 'applied'), row('e', 'done', 'later', 'x')];
  assert.deepEqual(lanesOf(rows).map((l) => [l.id, l.rows.map((r) => r.run_id)]), [['needs_you', ['c', 'e']], ['working', ['a']], ['ready', ['b']], ['archive', ['d']]]);
  assert.deepEqual(rows.map(cardAction), ['task.cancel', null, 'task.retry', null, null]);
  assert.deepEqual(rows.slice(0, 4).map(displayText), ['Çalışıyor', 'Onayınızı bekliyor', 'Başarısız', 'Uygulandı']);
});
