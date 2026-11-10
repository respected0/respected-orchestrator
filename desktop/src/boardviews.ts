// Pure views for the work boards (tasks, projects, inbox, activity). No React, no Tauri: testable under `node --test`.
// Everything is read from the engine's own records (runs.list, projects.list, activity.list). A reply that is not exactly the documented
// shape becomes an error view, never an empty or healthy-looking one.

export type Tone = 'ok' | 'warn' | 'err' | 'run' | '';
export const RUN_STATE: Record<string, { text: string; tone: Tone }> = {
  queued: { text: 'Sırada', tone: '' }, in_progress: { text: 'Çalışıyor', tone: 'run' }, done: { text: 'Bitti', tone: 'ok' },
  failed: { text: 'Başarısız', tone: 'err' }, cancelled: { text: 'İptal edildi', tone: 'warn' }, stale: { text: 'Yarıda kaldı', tone: 'warn' }, invalid: { text: 'Bozuk kayıt', tone: 'err' },
};
export const stateInfo = (s: string): { text: string; tone: Tone } => RUN_STATE[s] ?? { text: s || 'Bilinmiyor', tone: '' };
export const ATTENTION_STATES = ['failed', 'stale', 'invalid'] as const;

export type RunRow = { run_id: string; state: string; lane: string; display: string; task: string; kind: string | null; agent: string | null; project_root: string | null; created_at: string | null; updated_at: string | null; error: string | null };
export type ProjectRow = { project_id: string; state: string; goal: string; created_at: string | null; alive: boolean; stages: { name: string; status: string | null; after: string[]; attempts: number }[]; error: string | null };
export type ActivityRow = { seq: number; ts: number | null; op: string; run: string | null; type: string; stage: string | null };

export type Failure = { kind: 'error'; text: string; hint: string };
export type View<T> = { kind: 'rows'; rows: T[]; more: boolean } | Failure;
const fail = (text: string, hint = 'Yenile düğmesiyle tekrar deneyin.'): Failure => ({ kind: 'error', text, hint });
const SHAPE = 'Uygulama ve motor aynı sürümde olmalı.';

function body(reply: unknown, what: string, key: string): { ok: true; list: unknown[]; r: Record<string, unknown> } | { ok: false; f: Failure } {
  const r = reply as { ok?: unknown; result?: Record<string, unknown>; error?: { message?: string } } | null;
  if (!r || typeof r !== 'object') return { ok: false, f: fail(`${what}: beklenmeyen yanıt alındı.`, 'Motoru yeniden başlatın veya onarım çalıştırın.') };
  if (r.ok !== true) return { ok: false, f: fail(`${what}: ${r.error?.message ?? 'bilinmeyen hata'}`) };
  const list = r.result?.[key];
  if (!Array.isArray(list)) return { ok: false, f: fail(`${what}: yanıt beklenen biçimde değil; gösterilmedi.`, SHAPE) };
  return { ok: true, list, r: r.result as Record<string, unknown> };
}
const s = (v: unknown): string => (typeof v === 'string' ? v : '');
const sn = (v: unknown): string | null => (typeof v === 'string' ? v : null);
const obj = (x: unknown, key: string): x is Record<string, unknown> => typeof x === 'object' && x !== null && key in x;

export function runsView(reply: unknown): View<RunRow> {
  const b = body(reply, 'Görevler okunamadı', 'runs');
  if (!b.ok) return b.f;
  const rows = b.list.filter((x): x is Record<string, unknown> => obj(x, 'run_id') && typeof x.run_id === 'string')
    .map((x) => ({ run_id: s(x.run_id), state: s(x.state) || 'invalid', lane: s(x.lane), display: s(x.display), task: s(x.task), kind: sn(x.kind), agent: sn(x.agent), project_root: sn(x.project_root), created_at: sn(x.created_at), updated_at: sn(x.updated_at), error: sn(x.error) }));
  return rows.length === b.list.length ? { kind: 'rows', rows, more: b.r.next_cursor != null } : fail('Görev listesi beklenen biçimde değil; gösterilmedi.', SHAPE);
}

export function projectsView(reply: unknown): View<ProjectRow> {
  const b = body(reply, 'Projeler okunamadı', 'projects');
  if (!b.ok) return b.f;
  const rows = b.list.filter((x): x is Record<string, unknown> => obj(x, 'project_id') && typeof x.project_id === 'string').map((x) => ({
    project_id: s(x.project_id), state: s(x.state) || 'invalid', goal: s(x.goal), created_at: sn(x.created_at), alive: x.alive === true, error: sn(x.error),
    stages: (Array.isArray(x.stages) ? x.stages : []).filter((g): g is Record<string, unknown> => typeof g === 'object' && g !== null)
      .map((g) => ({ name: s(g.name), status: sn(g.status), after: (Array.isArray(g.after) ? g.after : []).filter((a): a is string => typeof a === 'string'), attempts: typeof g.attempts === 'number' ? g.attempts : 0 })),
  }));
  return rows.length === b.list.length ? { kind: 'rows', rows, more: b.r.next_cursor != null } : fail('Proje listesi beklenen biçimde değil; gösterilmedi.', SHAPE);
}

export type ActivityView = { kind: 'rows'; rows: ActivityRow[]; more: boolean; lastSeq: number } | Failure;
export function activityView(reply: unknown): ActivityView {
  const b = body(reply, 'Etkinlik okunamadı', 'events');
  if (!b.ok) return b.f;
  const rows = b.list.filter((x): x is Record<string, unknown> => obj(x, 'seq') && typeof x.seq === 'number')
    .map((x) => ({ seq: x.seq as number, ts: typeof x.ts === 'number' ? x.ts : null, op: s(x.op), run: sn(x.run), type: s(x.type), stage: sn(x.stage) }));
  if (rows.length !== b.list.length) return fail('Etkinlik listesi beklenen biçimde değil; gösterilmedi.', SHAPE);
  return { kind: 'rows', rows, more: b.r.has_more === true, lastSeq: typeof b.r.last_seq === 'number' ? b.r.last_seq : 0 };
}

/** The engine pages forward from a cursor, so the newest page starts `limit` before the last sequence. */
export const newestCursor = (lastSeq: number, limit: number): number => Math.max(0, lastSeq - limit);

/** ISO text or epoch seconds -> short local date and time; anything unreadable shows as an em dash, never as "now". */
export function when(v: string | number | null): string {
  if (v === null || v === '') return '—';
  const d = new Date(typeof v === 'number' ? v * 1000 : v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' });
}

export type TaskForm = { root: string; task: string; kind: 'read' | 'write'; worker: string; ownership: string; acceptance: string };
type Checked<T> = { ok: true; value: T } | { ok: false; text: string };
const refuse = (text: string): { ok: false; text: string } => ({ ok: false, text });

/** The new-task form -> the engine's `task.start` payload. Only obvious gaps are caught here; the engine checks everything again. */
export function taskRequest(f: TaskForm): Checked<Record<string, unknown>> {
  const lines = (s: string) => s.split('\n').map((x) => x.trim()).filter(Boolean);
  if (!f.root.trim()) return refuse('Proje klasörünü seçin.');
  if (!f.task.trim()) return refuse('Görevi yazın.');
  const ownership = lines(f.ownership);
  if (!ownership.length) return refuse('En az bir kapsam yolu yazın (ör. src ya da .).');
  // shortcut: a command line is split on spaces, so an argument that contains a space cannot be written; use a quoting parser when one is needed
  const acceptance = lines(f.acceptance).map((l) => l.split(/\s+/));
  if (f.kind === 'write' && !acceptance.length) return refuse('Yazan görev en az bir kabul komutu ister.');
  return { ok: true, value: { project_root: f.root.trim(), task: f.task.trim(), kind: f.kind, ownership, ...(f.worker ? { worker: f.worker } : {}), ...(acceptance.length ? { acceptance } : {}) } };
}

/** The engine's `task.start` reply -> the run id, or the engine's refusal as a sentence. */
export function startedView(reply: unknown): Checked<string> {
  const r = reply as { ok?: unknown; result?: { run_id?: unknown }; error?: { code?: string; message?: string } } | null;
  if (r?.ok === true) return typeof r.result?.run_id === 'string' ? { ok: true, value: r.result.run_id } : refuse('Motorun yanıtı beklenen biçimde değil.');
  const message = r?.error?.message ?? '';
  if (message.includes('mcp_acceptance_allow')) return refuse('Kabul komutu izin listenizde yok. Önce `rorch config set mcp_acceptance_allow=...` ile komutun başını ekleyin.');
  if (r?.error?.code === 'FORBIDDEN') return refuse('Bu işleme izin yok.');
  return refuse(message ? `Motor reddetti: ${message.slice(0, 300)}` : 'Motor yanıt vermedi.');
}

/** Agents the form may offer as the worker: the ones `agent.describe` calls ready. A user-defined command is never offered here. */
export function readyAgents(reply: unknown): string[] {
  const list = (reply as { ok?: unknown; result?: { agents?: unknown } } | null)?.result?.agents;
  if (!Array.isArray(list)) return [];
  return list.filter((a): a is { agent: string } => typeof a?.agent === 'string' && a.agent !== 'custom' && a?.readiness?.effective === 'ready').map((a) => a.agent);
}

/** The board's lanes, in the engine's order. The lane of a run is the engine's (derived from its records on every read); nothing is moved here. */
export const LANES: { id: string; title: string }[] = [
  { id: 'needs_you', title: 'Sizi bekliyor' }, { id: 'working', title: 'Çalışıyor' }, { id: 'ready', title: 'Onaya hazır' }, { id: 'archive', title: 'Arşiv' },
];
const DISPLAY: Record<string, string> = { awaiting_approval: 'Onayınızı bekliyor', apply_failed: 'Uygulama başarısız oldu', applied: 'Uygulandı' };
export const displayText = (r: RunRow): string => DISPLAY[r.display] ?? stateInfo(r.state).text;

/** Rows grouped by lane. A run whose lane this screen does not know stays visible: it goes to "Sizi bekliyor", never out of sight. */
export function lanesOf(rows: RunRow[]): { id: string; title: string; rows: RunRow[] }[] {
  const known = new Set(LANES.map((l) => l.id));
  return LANES.map((l) => ({ ...l, rows: rows.filter((r) => (known.has(r.lane) ? r.lane : 'needs_you') === l.id) }));
}

/** What a card may ask the engine for: cancel while it works, retry after it failed or was cut off. The engine decides again. */
export const cardAction = (r: RunRow): 'task.cancel' | 'task.retry' | null =>
  r.lane === 'working' ? 'task.cancel' : r.display === 'failed' || r.display === 'stale' ? 'task.retry' : null;
