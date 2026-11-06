import test from 'node:test';
import assert from 'node:assert/strict';
import * as inventoryModule from '../src/inventory.ts';
import { NO_FILTER, SCREEN_ACTIONS, applyFilter, clients, warningText, inventoryView, scopeGroup, statusLabels, toggleFlag, type Capability } from '../src/inventory.ts';

const st = (state: boolean | null, reason = 'because') => ({ state, reason });
const cap = (over: Partial<Capability> & { id: string }): Capability => ({
  kind: 'mcp', name: over.id, client: 'codex', scope: 'user', project_path: null,
  origin: { path: 'C:/h/.codex/config.toml', source: 'code', provenance: 'x' }, entry: {}, declared_permissions: {}, digest: 'D', secrets_removed: 0, warnings: [],
  status: { configured: st(true), installed: st(true), available: st(true), verified: st(false), trusted: st(false) }, ...over,
});
const reply = (caps: unknown[], extra: object = {}) => ({ ok: true, result: { capabilities: caps, counts: { mcp: 1, skill: 0, trusted: 0, verified: 0 }, approvals_error: null, ...extra } });

test('a well-formed reply becomes rows; the counts come from the engine', () => {
  const v = inventoryView(reply([cap({ id: 'a' })]));
  assert.equal(v.kind, 'rows');
  if (v.kind === 'rows') assert.deepEqual([v.rows.length, v.counts.mcp, v.approvalsError], [1, 1, null]);
});

test('anything that is not exactly the documented shape is an error, never an empty or green screen', () => {
  for (const bad of [null, undefined, 5, 'x', {}, { ok: false, error: { message: 'boom' } }, { ok: true }, { ok: true, result: {} }, { ok: true, result: { capabilities: 'no' } },
    reply([{ kind: 'mcp', id: 'x' }]), reply([cap({ id: 'a' }), { nope: 1 }]),
    reply([{ ...cap({ id: 'a' }), status: { configured: st(true) } }]),
    reply([{ ...cap({ id: 'a' }), status: { ...cap({ id: 'a' }).status, trusted: { state: 'yes', reason: 'x' } } }])]) {
    assert.equal(inventoryView(bad).kind, 'error', JSON.stringify(bad));
  }
  const failed = inventoryView({ ok: false, error: { message: 'boom' } });
  assert.ok(failed.kind === 'error' && failed.text.includes('boom'));
});

test('an approvals problem is carried to the screen, not swallowed', () => {
  const v = inventoryView(reply([], { approvals_error: 'the approvals file failed verification' }));
  assert.ok(v.kind === 'rows' && v.approvalsError?.includes('failed verification'));
});

test('filters combine: kind, scope group, client, text (Turkish case folding) and quick filters', () => {
  const rows = [
    cap({ id: '1', name: 'Github', client: 'codex', warnings: [{ kind: 'secrets_in_config', message: 'm' }] }),
    cap({ id: '2', name: 'ISIK', kind: 'skill', client: 'cursor', status: { ...cap({ id: '2' }).status, installed: st(false) } }),
    cap({ id: '3', name: 'proj', client: 'claude-code', scope: 'project', status: { ...cap({ id: '3' }).status, trusted: st(true) } }),
  ];
  const f = (o: object) => applyFilter(rows, { ...NO_FILTER, ...o }).map((c) => c.id);
  assert.deepEqual(f({}), ['1', '2', '3']);
  assert.deepEqual(f({ kind: 'skill' }), ['2']);
  assert.deepEqual(f({ scope: 'project' }), ['3']);
  assert.deepEqual(f({ scope: 'global' }), ['1', '2']);
  assert.deepEqual(f({ client: 'codex' }), ['1']);
  assert.deepEqual(f({ query: 'ısık' }), ['2']);
  assert.deepEqual(f({ query: 'IŞIK' }), []);  // a different word, not matched by accident
  assert.deepEqual(f({ query: 'İSİK' }), ['2']);
  assert.deepEqual(f({ query: 'isik' }), ['2']);
  assert.deepEqual(f({ query: '  GIT ' }), ['1']);
  assert.deepEqual(f({ only: 'warnings' }), ['1']);
  assert.deepEqual(f({ only: 'not-installed' }), ['2']);
  assert.deepEqual(f({ only: 'trusted' }), ['3']);
  assert.deepEqual(f({ kind: 'mcp', scope: 'global', only: 'warnings' }), ['1']);
  assert.deepEqual(f({ query: 'nothing matches this' }), []);
  assert.deepEqual(clients(rows), ['claude-code', 'codex', 'cursor']);
});

test('project entries inside a user file count as project, user-level ones as global', () => {
  assert.equal(scopeGroup(cap({ id: 'a', scope: 'user' })), 'global');
  assert.equal(scopeGroup(cap({ id: 'b', scope: 'project', project_path: 'C:/work/app' })), 'project');
});

test('five separate labels in a fixed order; unknown never reads as yes; verified and trusted default to no', () => {
  const labels = statusLabels(cap({ id: 'a', status: { configured: st(true), installed: st(null), available: st(null), verified: st(false), trusted: st(false) } }));
  assert.deepEqual(labels.map((l) => l.key), ['configured', 'installed', 'available', 'verified', 'trusted']);
  assert.equal(labels[1].text, 'Kurulum bilinmiyor');
  assert.equal(labels[2].text, 'Erişilebilirlik denenmedi');
  assert.equal(labels[3].text, 'Doğrulanmadı');
  assert.equal(labels[4].text, 'Güvenilir değil');
  const nullEverything = statusLabels(cap({ id: 'b', status: { configured: st(null), installed: st(null), available: st(null), verified: st(null), trusted: st(null) } }));
  assert.ok(nullEverything.every((l) => l.state === null && !/^(Doğrulandı|Güvenilir \()/.test(l.text)));
  assert.ok(labels.every((l) => l.reason.length > 0));
});

test('a false-positive note changes nothing but the note itself', () => {
  const rows = [cap({ id: 'a', warnings: [{ kind: 'x', message: 'm' }] })];
  const before = JSON.stringify(rows);
  const flags = toggleFlag(new Set(), 'a');
  assert.ok(flags.has('a'));
  assert.equal(toggleFlag(flags, 'a').has('a'), false);
  assert.equal(JSON.stringify(rows), before);
  assert.deepEqual(applyFilter(rows, { ...NO_FILTER, only: 'warnings' }).map((c) => c.id), ['a']);  // still listed, still warned
  assert.equal(statusLabels(rows[0])[4].state, false);
});

test('the screen is read-only: the module exports nothing that could enable, install, trust or run a capability', () => {
  assert.deepEqual([...SCREEN_ACTIONS], ['refresh', 'filter', 'flag-false-positive']);
  const exported = Object.keys(inventoryModule);
  assert.ok(exported.length >= 8);
  assert.ok(!exported.some((k) => /activate|enable|install|approve|run|execute|grant/i.test(k) || /^trust/i.test(k)), exported.join());
});

test('known warnings read in Turkish, unknown ones keep the engine text so nothing is hidden', () => {
  assert.match(warningText({ kind: 'launches_local_process', message: 'english' }), /yerel bir program/);
  assert.equal(warningText({ kind: 'brand_new_kind', message: 'engine says this' }), 'engine says this');
});
