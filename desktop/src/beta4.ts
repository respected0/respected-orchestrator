// Pure logic for the Beta.4 screens (team, capability suggestions, budget). No React, no Tauri: testable under `node --test`.
// Every screen is READ-ONLY. Nothing here can start, approve, apply, activate or change anything; the only calls are `read_call` with the
// three commands in READ_COMMANDS, and the engine answers them from its own records. Anything that is not exactly the documented shape
// becomes an error view, never an empty or green one.

export const READ_COMMANDS = ['team.view', 'capabilities.recommend', 'analytics.summary'] as const;
export type ReadCommand = (typeof READ_COMMANDS)[number];

export type Failure = { kind: 'error'; text: string; hint: string };
const failure = (what: string, hint = 'Yenile düğmesiyle tekrar deneyin.'): Failure => ({ kind: 'error', text: what, hint });

function result(reply: unknown, what: string): { ok: true; r: Record<string, any> } | { ok: false; f: Failure } {
  const r = reply as { ok?: unknown; result?: unknown; error?: { message?: string } } | null;
  if (!r || typeof r !== 'object') return { ok: false, f: failure(`${what}: beklenmeyen yanıt alındı.`, 'Motoru yeniden başlatın veya onarım çalıştırın.') };
  if (r.ok !== true) return { ok: false, f: failure(`${what}: ${r.error?.message ?? 'bilinmeyen hata'}`) };
  if (typeof r.result !== 'object' || r.result === null || Array.isArray(r.result)) return { ok: false, f: failure(`${what}: yanıt beklenen biçimde değil; gösterilmedi.`, 'Uygulama ve motor aynı sürümde olmalı.') };
  return { ok: true, r: r.result as Record<string, any> };
}

const str = (x: unknown): x is string => typeof x === 'string';

// ---------------------------------------------------------------------------------------------------------------- team (B4-02.04)
export type Member = { id: string; name: string; role: string; rev: number; tool: string | null; profile: string | null; capabilities: string[]; status: string; reason: string | null };
export type Handoff = { seq: number; kind: string; from?: string; to?: string; action?: string; reason?: string; hop?: number; max_hops?: number; note?: string; run?: string | null; detail?: Record<string, unknown> };
export type TeamView = { kind: 'team'; team: { id: string; name: string }; members: Member[]; history: Handoff[]; rejected: number };

const ROLE_TEXT: Record<string, string> = { lead: 'Lider', implementer: 'Geliştirici', reviewer: 'Gözden geçiren', qa: 'Kalite', designer: 'Tasarımcı' };
const ACTION_TEXT: Record<string, string> = { implement: 'geliştirme', review: 'gözden geçirme', test: 'test', design: 'tasarım', escalate: 'yükseltme', stop: 'durdurma' };
const REASON_TEXT: Record<string, string> = { work_done: 'iş bitti', needs_review: 'gözden geçirme gerekiyor', needs_test: 'test gerekiyor', blocked: 'engellendi', out_of_scope: 'kapsam dışı', retry_exhausted: 'deneme hakkı bitti' };

export const roleText = (role: string) => ROLE_TEXT[role] ?? role;

export function teamView(reply: unknown): TeamView | Failure {
  const got = result(reply, 'Takım okunamadı');
  if (!got.ok) return got.f;
  const r = got.r;
  if (r.ok === false) return failure(`Takım dosyası kullanılamıyor (${r.problem?.code ?? '?'}): ${r.problem?.message ?? ''}`, 'Dosyayı düzeltin; engine hiçbir şeyi sessizce varsayılana çevirmez.');
  const okMember = (m: any): m is Member => m && str(m.id) && str(m.name) && str(m.role) && typeof m.rev === 'number' && str(m.status) && Array.isArray(m.capabilities);
  if (!r.team || !str(r.team.id) || !Array.isArray(r.members) || !r.members.every(okMember) || !Array.isArray(r.history)) return failure('Takım yanıtı beklenen biçimde değil; gösterilmedi.', 'Uygulama ve motor aynı sürümde olmalı.');
  return { kind: 'team', team: { id: r.team.id, name: String(r.team.name ?? r.team.id) }, members: r.members, history: r.history as Handoff[], rejected: Number(r.rejected_records ?? 0) };
}

/** A member who cannot run right now says why; "ok" is the only word that reads as available. */
export function memberStatus(m: Member): { text: string; usable: boolean } {
  if (m.status === 'ok') return { text: 'Hazır', usable: true };
  if (m.status === 'tool_missing') return { text: `Kullanılamıyor: ${m.reason ?? 'araç kurulu değil'}`, usable: false };
  return { text: `Bilinmiyor (${m.status})`, usable: false };
}

/** One readable line per history event; missing fields are shown as unknown, never invented. */
export function historyLine(h: Handoff): string {
  if (h.kind === 'handoff') {
    const hop = h.hop !== undefined && h.max_hops !== undefined ? ` (devir ${h.hop}/${h.max_hops})` : '';
    return `${h.from ?? '?'} → ${h.to ?? '?'}: ${ACTION_TEXT[h.action ?? ''] ?? h.action ?? '?'} için, ${REASON_TEXT[h.reason ?? ''] ?? h.reason ?? 'neden bilinmiyor'}${hop}${h.note ? ` — “${h.note}”` : ''}`;
  }
  if (h.kind === 'escalated') return `İnsana yükseltildi: ${(h.detail?.reasons as string[] | undefined)?.[0] ?? 'neden kaydedilmemiş'}`;
  if (h.kind === 'case_opened') return `Kurtarma vakası açıldı: ${String(h.detail?.problem ?? 'sınıflanamayan hata')}`;
  if (h.kind === 'operator_action') return `Operatör eylemi: ${String(h.detail?.action ?? '?')} → ${String(h.detail?.outcome ?? '?')}`;
  return `${h.kind}`;
}

// ---------------------------------------------------------------------------------------------------------- suggestions (B4-03.05)
export type Suggestion = { id: string; name: string; kind: string; scope: string; matched: string[]; compatibility: string; compatibility_reasons: string[]; installed: boolean | null; trusted: boolean; risks: string[]; description: string | null; blocked_by_risk: boolean; needs_approval: boolean };
export type SuggestView = { kind: 'suggestions'; categories: string[]; items: Suggestion[]; excluded: { id: string; name: string; why: string[] }[]; notes: string[] };

const COMPAT_TEXT: Record<string, string> = { compatible: 'Uyumlu', incompatible: 'Uyumsuz', unknown: 'Uyumluluk bilinmiyor' };
const RISK_TEXT: Record<string, string> = { launches_local_process: 'yerel program başlatır', secrets_in_config: 'yapılandırmada sır var', instruction_like_text: 'talimat benzeri metin', unknown_transport: 'aktarım bilinmiyor', reaches_network: 'ağa erişir' };
const NOTE_TEXT: Record<string, string> = {
  no_task_category_matched: 'Bu görev için tanınan bir kategori yok; bu yüzden hiçbir şey önerilmiyor.',
  nothing_matched: 'Bulunan yeteneklerden hiçbiri bu göreve uymuyor. Hiçbir şey indirilmez veya kurulmaz.',
  all_unknown: 'Adayların hepsinin uyumluluğu doğrulanamadı.',
};

export function suggestView(reply: unknown): SuggestView | Failure {
  const got = result(reply, 'Öneriler alınamadı');
  if (!got.ok) return got.f;
  const r = got.r;
  const okItem = (s: any): s is Suggestion => s && str(s.id) && str(s.name) && str(s.compatibility) && Array.isArray(s.risks) && s.needs_approval === true && typeof s.trusted === 'boolean';
  if (r.side_effects !== 'none' || !Array.isArray(r.recommendations) || !r.recommendations.every(okItem) || !Array.isArray(r.task_categories)) {
    return failure('Öneri yanıtı beklenen biçimde değil; gösterilmedi.', 'Uygulama ve motor aynı sürümde olmalı.');
  }
  return { kind: 'suggestions', categories: r.task_categories, items: r.recommendations, excluded: Array.isArray(r.excluded) ? r.excluded : [], notes: Array.isArray(r.notes) ? r.notes : [] };
}

export const compatText = (c: string) => COMPAT_TEXT[c] ?? c;
export const riskText = (r: string) => RISK_TEXT[r] ?? r;
export const noteText = (n: string) => NOTE_TEXT[n.split(':')[0]] ?? n;
/** Dismissals are a viewer convenience: they hide a row on this screen only and change nothing in the engine. */
export function visibleSuggestions(items: Suggestion[], dismissed: Set<string>): Suggestion[] { return items.filter((s) => !dismissed.has(s.id)); }
/** The screen has no activate button, so the only honest next step is text. Untrusted items say they would still need an approval. */
export function nextStepText(s: Suggestion): string {
  if (s.blocked_by_risk) return 'Risk yüksek veya bilinmiyor ve güvenilir değil: önce güven kaydı gerekir. Bu ekran hiçbir şeyi etkinleştirmez.';
  return 'Bu ekran etkinleştirmez. Etkinleştirmek için ayrı bir plan ve sizin onayınız gerekir.';
}

// ------------------------------------------------------------------------------------------------------------------ budget (B4-04.03)
export type Bucket = { name: string; runs: number; accepted: number; acceptance_rate: number | null; rate_note: string | null; tokens_actual: number | null; runs_with_usage: number; runs_without_usage: number; quota_stops: number };
export type UsageView =
  | { kind: 'disabled'; reason: string }
  | { kind: 'usage'; totals: Bucket; byAgent: Bucket[]; byProject: Bucket[]; budget: { limit: number | null; status: string; why: string }; warnings: { kind: string; message: string }[]; windowRuns: number; estimate: { status: string; reason: string } };

export function usageView(reply: unknown): UsageView | Failure {
  const got = result(reply, 'Kullanım okunamadı');
  if (!got.ok) return got.f;
  const r = got.r;
  if (r.enabled === false) return { kind: 'disabled', reason: String(r.reason ?? 'veri toplama kapalı') };
  const okBucket = (b: any): b is Bucket => b && typeof b.runs === 'number' && typeof b.accepted === 'number' && (b.acceptance_rate === null || typeof b.acceptance_rate === 'number') && typeof b.runs_without_usage === 'number';
  if (r.enabled !== true || !okBucket(r.totals) || !Array.isArray(r.by_agent) || !r.by_agent.every(okBucket) || !Array.isArray(r.by_project) || !r.by_project.every(okBucket) || !r.budget || !str(r.budget.status)) {
    return failure('Kullanım yanıtı beklenen biçimde değil; gösterilmedi.', 'Uygulama ve motor aynı sürümde olmalı.');
  }
  return { kind: 'usage', totals: r.totals, byAgent: r.by_agent, byProject: r.by_project, budget: r.budget, warnings: Array.isArray(r.warnings) ? r.warnings : [], windowRuns: Number(r.window_runs ?? 0), estimate: r.estimate ?? { status: 'not_computed', reason: '' } };
}

/** A percentage only when the engine computed one from a meaningful denominator; otherwise the reason, never 0 %. */
export function rateText(b: Pick<Bucket, 'acceptance_rate' | 'rate_note' | 'runs'>): string {
  if (b.acceptance_rate === null) return b.runs === 0 ? 'Henüz çalıştırma yok' : "Örnek çok az (5'ten az çalıştırma): yüzde gösterilmiyor";
  return `%${Math.round(b.acceptance_rate * 1000) / 10}`;
}

/** Tokens: a number only when something reported; "bilinmiyor" otherwise (never 0), and how many runs are missing. */
export function tokenText(b: Pick<Bucket, 'tokens_actual' | 'runs_without_usage' | 'runs'>): string {
  if (b.tokens_actual === null) return b.runs === 0 ? '—' : 'bilinmiyor';
  return b.runs_without_usage > 0 ? `${b.tokens_actual} (+ ${b.runs_without_usage} çalıştırma için bilinmiyor)` : String(b.tokens_actual);
}

/** The engine's English warning, in Turkish. Numbers are taken from its message; an unknown kind is shown as the engine wrote it. */
export function warningText(w: { kind: string; message: string }): string {
  const n = w.message.match(/\d+/g) ?? [];
  if (w.kind === 'quota_stops' && n.length) return `${n[0]} çalıştırma sağlayıcı sınırında durdu.`;
  if (w.kind === 'unknown_usage' && n.length >= 2) return `${n[1]} çalıştırmanın ${n[0]} tanesi token kullanımını bildirmedi.`;
  return w.message;
}

/** Why the budget has the status it has, in Turkish, from the numbers the engine sent. */
export function budgetWhy(status: string, why: string, limit: number | null): string {
  const n = why.match(/\d+/g) ?? [];
  if (status === 'unknown_possible_overrun' && n.length) return `${n[0]} çalıştırma kullanım bildirmedi; gerçek toplam daha yüksek olabilir.`;
  if (['ok', 'near', 'over'].includes(status) && n.length >= 2) return `${n[0]} / ${n[1]} token bildirildi.`;
  if (status === 'no_budget') return 'Token bütçesi tanımlı değil.';
  return limit ? why : why;
}

export type Tone = 'neutral' | 'ok' | 'warn' | 'bad';
/** `ok` is the only green; a missing measurement is a warning, so an unknown can never look fine. */
export function budgetBadge(status: string): { text: string; tone: Tone } {
  switch (status) {
    case 'ok': return { text: 'Bütçe içinde', tone: 'ok' };
    case 'near': return { text: 'Bütçeye yaklaşıldı', tone: 'warn' };
    case 'over': return { text: 'Bütçe aşıldı', tone: 'bad' };
    case 'unknown_possible_overrun': return { text: 'Bilinmeyen kullanım var: aşım olabilir', tone: 'warn' };
    case 'no_budget': return { text: 'Bütçe belirlenmedi', tone: 'neutral' };
    default: return { text: `Durum anlaşılamadı (${status})`, tone: 'warn' };
  }
}
