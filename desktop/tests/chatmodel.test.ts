import test from 'node:test';
import assert from 'node:assert/strict';
import { actionText, addPaths, agentLine, baseName, chatPermissionsView, childPath, compactNumber, filesOf, itemsOf, modelsView, planOf, toolCount, toolListView, withAttachments, withLive, type Turn } from '../src/chatmodel.ts';

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

test('agent line: ready only when the engine says ready and chat is native; anything else carries the engine reason', () => {
  const d = (effective: string, chat: string) => ({ ok: true as const, value: { agent: 'opencode', version: '2.2.3', readiness: { effective, reason: 'auth_required: not logged in' }, interfaces: { chat: { status: chat, note: 'never verified' } } } });
  assert.deepEqual(agentLine(d('ready', 'native')), { ready: true, text: 'Ajan: opencode (2.2.3) · hazır' });
  assert.deepEqual(agentLine(d('not_ready', 'native')), { ready: false, text: 'Ajan: opencode (2.2.3) · hazır değil: auth_required: not logged in' });
  assert.deepEqual(agentLine(d('ready', 'unverified')), { ready: false, text: 'Ajan: opencode (2.2.3) · sohbet doğrulanmadı: never verified' });
  assert.match(agentLine(d('unknown', 'native')).text, /durumu bilinmiyor/);
  assert.match(agentLine({ ok: true, value: { agent: 'x', readiness: { effective: 'great' } } }).text, /beklenen biçimde değil/);
  assert.match(agentLine({ ok: false, text: 'Motor yanıt vermedi' }).text, /okunamadı: Motor yanıt vermedi/);
});

test('agent permission rules come from the engine policy; absent or broken data is never shown as rules', () => {
  const d = { ok: true as const, value: { agent: 'opencode', chat_permissions: {
    modes: { default: ['read', 'glob', 'grep'], 'accept-edits': ['read', 'edit'], 'bypass-permissions': ['*'] },
    always_denied: ['execute', 'opencode_worktree_create'], project_config: 'disabled', source: 'engine policy' } } };
  assert.deepEqual(chatPermissionsView(d), {
    kind: 'rules',
    modes: [{ id: 'default', actions: ['read', 'glob', 'grep'] }, { id: 'accept-edits', actions: ['read', 'edit'] }, { id: 'bypass-permissions', actions: ['*'] }],
    denied: ['execute', 'opencode_worktree_create'],
    note: 'Bu kurallar motorun kendi ilkesidir; proje yapılandırması yok sayılır.',
  });
  assert.deepEqual(chatPermissionsView({ ok: true, value: { agent: 'codex', chat_permissions: {} } }), { kind: 'none' });
  assert.equal(chatPermissionsView({ ok: true, value: { agent: 'codex' } }).kind, 'error');
  assert.equal(chatPermissionsView({ ok: true, value: { chat_permissions: { modes: { x: 'read' }, always_denied: [] } } }).kind, 'error');
  assert.equal(chatPermissionsView({ ok: true, value: { chat_permissions: { modes: {}, always_denied: [1] } } }).kind, 'error');
  assert.deepEqual(chatPermissionsView({ ok: false, text: 'Motor yanıt vermedi' }), { kind: 'error', text: 'Motor yanıt vermedi' });
  assert.equal(actionText('edit'), 'düzenleme');
  assert.equal(actionText('opencode_worktree_create'), 'opencode_worktree_create');
});

test('the running turn shows what the agent has said so far, in the turn that asked or as a turn of its own for a retry', () => {
  const live = { events: [{ kind: 'message', text: 'yazıyorum' }] };
  const asked: Turn[] = [...turns, { n: null, user: 'devam', result: null }];
  assert.deepEqual(itemsOf(withLive(asked, live)).slice(-2), [{ t: 'user', text: 'devam' }, { t: 'agent', text: 'yazıyorum' }]);
  assert.equal(withLive(turns, live).length, turns.length + 1);
  assert.deepEqual(itemsOf(withLive(turns, live)).at(-1), { t: 'agent', text: 'yazıyorum' });
  assert.equal(withLive(asked, null), asked);
  assert.equal(withLive(asked, { events: [] }), asked);
});

test('a file inside a folder keeps the folder\'s own separator', () => {
  assert.equal(childPath('C:\\p\\one\\', 'AGENTS.md'), 'C:\\p\\one\\AGENTS.md');
  assert.equal(childPath('/home/a/p', 'CLAUDE.md'), '/home/a/p/CLAUDE.md');
});
