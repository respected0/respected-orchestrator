import test from 'node:test';
import assert from 'node:assert/strict';
import * as b4 from '../src/beta4.ts';

const ok = (result: unknown) => ({ ok: true, result });

// ---- team ------------------------------------------------------------------------------------------------------------------
const member = (over: object = {}) => ({ id: 'implementer', name: 'Geliştirici', role: 'implementer', rev: 2, tool: 'claude', profile: 'm', capabilities: ['read', 'write'], status: 'ok', reason: null, ...over });
const team = (over: object = {}) => ok({ ok: true, team: { id: 'core', name: 'Core' }, members: [member()], history: [], rejected_records: 0, ...over });

test('team: a healthy reply becomes a team view', () => {
  const v = b4.teamView(team());
  assert.equal(v.kind, 'team');
  if (v.kind === 'team') assert.deepEqual([v.team.id, v.members.length, v.rejected], ['core', 1, 0]);
});

test('team: every kind of bad reply is an error view, never an empty team', () => {
  for (const bad of [null, undefined, 'x', 5, { ok: false, error: { message: 'boom' } }, ok(null), ok([]), ok({}), team({ members: 'no' }), team({ members: [{ id: 1 }] }), team({ history: null }), team({ team: null })]) {
    assert.equal(b4.teamView(bad).kind, 'error', JSON.stringify(bad));
  }
  const broken = b4.teamView(ok({ ok: false, problem: { code: 'UNREADABLE', message: 'x' } }));
  assert.ok(broken.kind === 'error' && broken.text.includes('UNREADABLE'));
});

test('team: only "ok" reads as available; a missing tool says why', () => {
  assert.deepEqual(b4.memberStatus(member() as any), { text: 'Hazır', usable: true });
  const gone = b4.memberStatus(member({ status: 'tool_missing', reason: "tool 'codex' is not installed; nothing was substituted" }) as any);
  assert.equal(gone.usable, false);
  assert.ok(gone.text.includes('nothing was substituted'));
  assert.equal(b4.memberStatus(member({ status: 'weird' }) as any).usable, false);
});

test('team: history lines name the actors, the action, the reason and the hop, and never invent missing facts', () => {
  assert.equal(b4.historyLine({ seq: 1, kind: 'handoff', from: 'Geliştirici', to: 'Gözden geçiren', action: 'review', reason: 'needs_review', hop: 1, max_hops: 3, note: 'bakar mısın' }),
    'Geliştirici → Gözden geçiren: gözden geçirme için, gözden geçirme gerekiyor (devir 1/3) — “bakar mısın”');
  assert.ok(b4.historyLine({ seq: 2, kind: 'handoff' }).includes('neden bilinmiyor'));
  assert.ok(b4.historyLine({ seq: 3, kind: 'escalated', detail: { reasons: ['hop budget spent'] } }).includes('hop budget spent'));
  assert.ok(b4.historyLine({ seq: 4, kind: 'escalated' }).includes('neden kaydedilmemiş'));
  assert.equal(b4.roleText('lead'), 'Lider');
  assert.equal(b4.roleText('x'), 'x');
});

// ---- suggestions -----------------------------------------------------------------------------------------------------------
const sug = (over: object = {}) => ({ id: 'a:b:mcp:gh', name: 'gh', kind: 'mcp', scope: 'user', matched: ['github'], compatibility: 'compatible', compatibility_reasons: ['ok'], installed: true, trusted: false, risks: [], description: null, blocked_by_risk: false, needs_approval: true, score: 3, ...over });
const sugReply = (over: object = {}) => ok({ task_categories: ['github'], recommendations: [sug()], excluded: [], notes: [], risk_level: 'unknown', side_effects: 'none', ...over });

test('suggestions: only a reply that promises no side effects and needs approval is shown', () => {
  assert.equal(b4.suggestView(sugReply()).kind, 'suggestions');
  for (const bad of [null, ok({}), sugReply({ side_effects: 'writes' }), sugReply({ recommendations: [sug({ needs_approval: false })] }), sugReply({ recommendations: [sug({ trusted: 'yes' })] }), sugReply({ task_categories: null })]) {
    assert.equal(b4.suggestView(bad).kind, 'error', JSON.stringify(bad));
  }
});

test('suggestions: wording keeps unknown apart from compatible and never offers activation', () => {
  assert.equal(b4.compatText('compatible'), 'Uyumlu');
  assert.equal(b4.compatText('unknown'), 'Uyumluluk bilinmiyor');
  assert.equal(b4.riskText('reaches_network'), 'ağa erişir');
  assert.ok(b4.noteText('no_task_category_matched: nothing is suggested').includes('hiçbir şey önerilmiyor'));
  assert.ok(b4.noteText('nothing_matched: x').includes('indirilmez'));
  assert.ok(b4.nextStepText(sug() as any).includes('onayınız'));
  assert.ok(b4.nextStepText(sug({ blocked_by_risk: true }) as any).includes('güven kaydı'));
  for (const key of Object.keys(b4)) assert.ok(!/activate|install|enable|apply|approve/i.test(key), `${key} must not exist in a read-only screen module`);
});

test('suggestions: dismissing hides a row on this screen only', () => {
  const items = [sug(), sug({ id: 'other' })] as any[];
  assert.deepEqual(b4.visibleSuggestions(items, new Set(['other'])).map((s) => s.id), ['a:b:mcp:gh']);
  assert.equal(items.length, 2);
});

// ---- usage ---------------------------------------------------------------------------------------------------------------------
const bucket = (over: object = {}) => ({ name: 'codex', runs: 7, accepted: 3, acceptance_rate: 0.4286, rate_note: null, tokens_actual: 5000, runs_with_usage: 7, runs_without_usage: 0, quota_stops: 0, ...over });
const usage = (over: object = {}) => ok({ enabled: true, window_runs: 7, totals: bucket(), by_agent: [bucket()], by_project: [bucket({ name: 'C:/a' })], estimate: { status: 'not_computed', reason: 'no catalog' },
  budget: { limit: 10000, status: 'ok', why: '5000 of 10000 tokens reported' }, warnings: [], runs: [], ...over });

test('usage: disabled collection is its own view, bad replies are errors', () => {
  assert.deepEqual(b4.usageView(ok({ enabled: false, reason: 'usage_collection is off' })), { kind: 'disabled', reason: 'usage_collection is off' });
  assert.equal(b4.usageView(usage()).kind, 'usage');
  for (const bad of [null, ok({}), ok({ enabled: 'yes' }), usage({ totals: null }), usage({ by_agent: [{}] }), usage({ budget: null }), usage({ by_project: 'x' })]) {
    assert.equal(b4.usageView(bad).kind, 'error', JSON.stringify(bad));
  }
});

test('usage: a percentage appears only with a real denominator; zero samples and small samples never show 0 %', () => {
  assert.equal(b4.rateText(bucket() as any), '%42.9');
  assert.equal(b4.rateText(bucket({ runs: 0, acceptance_rate: null }) as any), 'Henüz çalıştırma yok');
  assert.equal(b4.rateText(bucket({ runs: 3, acceptance_rate: null, rate_note: 'fewer than 5 runs: no percentage is shown' }) as any), "Örnek çok az (5'ten az çalıştırma): yüzde gösterilmiyor");
  assert.equal(b4.rateText(bucket({ runs: 3, acceptance_rate: null, rate_note: null }) as any), "Örnek çok az (5'ten az çalıştırma): yüzde gösterilmiyor");
  assert.notEqual(b4.rateText(bucket({ runs: 3, acceptance_rate: null }) as any), '%0');
});

test('usage: unknown tokens stay unknown and partial totals say what is missing', () => {
  assert.equal(b4.tokenText(bucket() as any), '5000');
  assert.equal(b4.tokenText(bucket({ tokens_actual: null, runs_with_usage: 0, runs_without_usage: 7 }) as any), 'bilinmiyor');
  assert.equal(b4.tokenText(bucket({ runs: 0, tokens_actual: null }) as any), '—');
  assert.ok(b4.tokenText(bucket({ runs_without_usage: 2 }) as any).includes('+ 2 çalıştırma için bilinmiyor'));
});

test('usage: only a fully measured, in-budget state is green', () => {
  const tones = Object.fromEntries(['ok', 'near', 'over', 'unknown_possible_overrun', 'no_budget', 'garbage'].map((s) => [s, b4.budgetBadge(s).tone]));
  assert.deepEqual(tones, { ok: 'ok', near: 'warn', over: 'bad', unknown_possible_overrun: 'warn', no_budget: 'neutral', garbage: 'warn' });
  assert.equal(Object.values(tones).filter((t) => t === 'ok').length, 1);
});

test('the three read commands are exactly the ones the engine lists as read-only', () => {
  assert.deepEqual([...b4.READ_COMMANDS], ['team.view', 'capabilities.recommend', 'analytics.summary']);
});

// ---- contract with the REAL engine: tests/tools/make_beta4_fixture.py wrote these replies from a synthetic data root ----------------
import { readFileSync } from 'node:fs';
const real = JSON.parse(readFileSync(new URL('./fixtures/beta4.json', import.meta.url), 'utf8'));

test('real engine reply: team screen', () => {
  const v = b4.teamView(real.team);
  assert.equal(v.kind, 'team');
  if (v.kind !== 'team') return;
  assert.deepEqual(v.members.map((m) => [m.id, b4.memberStatus(m).usable]), [['lead', true], ['implementer', false], ['reviewer', true]]);
  assert.ok(b4.memberStatus(v.members[1]).text.includes('nothing was substituted'));
  const lines = v.history.map(b4.historyLine);
  assert.ok(lines[0].includes('Geliştirici → Gözden geçiren: gözden geçirme için'));
  assert.ok(lines[0].includes('devir 1/3'));
  assert.ok(lines[1].startsWith('İnsana yükseltildi'));
});

test('real engine reply: suggestions screen explains and never promises activation', () => {
  const v = b4.suggestView(real.suggestions);
  assert.equal(v.kind, 'suggestions');
  if (v.kind !== 'suggestions') return;
  assert.deepEqual(v.categories, ['testing', 'docs']);
  assert.ok(v.items.every((s) => s.needs_approval && !s.trusted));
  assert.deepEqual(v.items.map((s) => [s.name, b4.compatText(s.compatibility)]), [['docs-writer', 'Uyumlu'], ['pytest-runner', 'Uyumluluk bilinmiyor']]);
  assert.ok(v.items.every((s) => b4.nextStepText(s).includes('etkinleştirmez')));
});

test('real engine reply: usage screen never shows an unknown as green or zero', () => {
  const v = b4.usageView(real.usage);
  assert.equal(v.kind, 'usage');
  if (v.kind !== 'usage') return;
  assert.equal(b4.budgetBadge(v.budget.status).tone, 'warn');   // 3 of 7 runs reported nothing
  assert.ok(b4.tokenText(v.totals).includes('+ 3 çalıştırma için bilinmiyor'));
  assert.equal(b4.rateText(v.totals), '%57.1');
  assert.ok(v.warnings.some((w) => w.kind === 'quota_stops'));
  assert.ok(v.byProject.every((p) => p.name.startsWith('C:/projeler/')));
});

test('usage: engine warnings and the budget reason read in Turkish and keep their numbers', () => {
  assert.equal(b4.warningText({ kind: 'quota_stops', message: '2 run(s) stopped on a provider limit' }), '2 çalıştırma sağlayıcı sınırında durdu.');
  assert.equal(b4.warningText({ kind: 'unknown_usage', message: '3 of 7 run(s) did not report token usage' }), '7 çalıştırmanın 3 tanesi token kullanımını bildirmedi.');
  assert.equal(b4.warningText({ kind: 'other', message: 'as written' }), 'as written');
  assert.equal(b4.budgetWhy('unknown_possible_overrun', '3 run(s) reported no usage, so the real total may be higher', 60000), '3 çalıştırma kullanım bildirmedi; gerçek toplam daha yüksek olabilir.');
  assert.equal(b4.budgetWhy('ok', '5000 of 10000 tokens reported', 10000), '5000 / 10000 token bildirildi.');
  assert.equal(b4.budgetWhy('no_budget', 'no token budget is set', null), 'Token bütçesi tanımlı değil.');
});
