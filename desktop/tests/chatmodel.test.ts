import test from 'node:test';
import assert from 'node:assert/strict';
import { addPaths, baseName, compactNumber, filesOf, itemsOf, modelsView, planOf, toolCount, toolListView, withAttachments, type Turn } from '../src/chatmodel.ts';

const done = (events: Record<string, unknown>[], extra = {}): Turn['result'] => ({ state: 'complete', complete: true, events: events as { kind: string }[], ...extra });
const turns: Turn[] = [
  { n: 1, user: 'oku', result: done([
    { kind: 'status', state: 'step_started' },
    { kind: 'tool_call', tool: 'read', status: 'completed', input: { filePath: 'C:/p/a.py' } },
    { kind: 'tool_call', tool: 'todowrite', status: 'completed', input: { todos: [{ content: 'İncele', status: 'completed' }, { content: 'Yaz', status: 'pending' }] } },
    { kind: 'message', role: 'assistant', text: 'Tamam' },
    { kind: 'usage', input: 1200, output: 30, reasoning: 5, cache_read: 100, cost: 0 },
    { kind: 'usage', input: 1500, output: 20, cost: 0.5 },
  ]) },
  { n: 2, user: null, result: done([{ kind: 'tool_call', tool: 'edit', status: 'completed', input: { filePath: 'C:/p/b.py' } }, { kind: 'tool_call', tool: 'edit', status: 'error', input: { filePath: 'C:/p/c.py' } }, { kind: 'error', message: 'kota' }], { error: 'tur hatası' }) },
];

test('items come only from the user text and the engine events, in order', () => {
  const items = itemsOf(turns);
  assert.deepEqual(items.map((i) => i.t), ['user', 'tool', 'tool', 'agent', 'tool', 'tool', 'error', 'error']);
  assert.equal(items[1].t === 'tool' && items[1].detail, 'C:/p/a.py');
  assert.deepEqual(itemsOf([{ n: null, user: 'merhaba', result: null }]), [{ t: 'user', text: 'merhaba' }]); // no answer yet: nothing invented
});

test('the plan is the agent’s last todo list; none without one', () => {
  assert.deepEqual(planOf(turns), [{ content: 'İncele', status: 'completed' }, { content: 'Yaz', status: 'pending' }]);
  assert.equal(planOf([{ n: 1, user: 'x', result: done([{ kind: 'message', text: 'a' }]) }]), null);
  assert.equal(planOf([{ n: 1, user: 'x', result: done([{ kind: 'tool_call', tool: 'todowrite', input: { todos: 'zz' } }]) }]), null);
});

test('changed files need a completed write tool; read files are listed separately', () => {
  assert.deepEqual(filesOf(turns), { changed: ['C:/p/b.py'], read: ['C:/p/a.py'] });
  assert.equal(toolCount(turns), 4);
});

test('attachments travel as @paths inside the text, once each', () => {
  assert.equal(withAttachments('merhaba', []), 'merhaba');
  assert.equal(withAttachments('bak', ['C:/a.txt', 'C:/d']), 'bak\n\nEklenen yollar (okumak için):\n@C:/a.txt\n@C:/d');
  assert.deepEqual(addPaths(['a'], ['a', 'b', ' ']), ['a', 'b']);
  assert.equal(baseName('C:\\Projeler\\uygulama\\'), 'uygulama');
});

test('model and tool replies that are not exactly the documented shape become errors, not an empty picker', () => {
  assert.deepEqual(modelsView({ ok: true, value: { models: ['a/b', 'c/d'] } }), { kind: 'models', ids: ['a/b', 'c/d'] });
  assert.deepEqual(modelsView({ ok: true, value: { models: [] } }), { kind: 'empty' });
  assert.equal(modelsView({ ok: true, value: { models: [1] } }).kind, 'error');
  assert.equal(modelsView({ ok: true, value: null }).kind, 'error');
  assert.deepEqual(modelsView({ ok: false, text: 'Motora ulaşılamadı.' }), { kind: 'error', text: 'Motora ulaşılamadı.' });
  const inv = { ok: true, result: { capabilities: [{ kind: 'mcp', name: 'git' }, { kind: 'mcp', name: 'git' }, { kind: 'skill', name: 'x' }, { kind: 'mcp' }] } };
  assert.deepEqual(toolListView(inv), { kind: 'rows', mcp: ['git'], skills: ['x'] });
  assert.equal(toolListView({ ok: false, error: { message: 'boom' } }).kind, 'error');
  assert.equal(toolListView(null).kind, 'error');
  assert.equal(toolListView({ ok: true, result: {} }).kind, 'error');
});

