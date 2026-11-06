// Pure logic for the read-only capability inventory screen (B3-08.03). No React, no Tauri: testable under `node --test`.
// Nothing here can enable, install, trust or run a capability; the screen has no such action to call.

export type Tri = boolean | null;
export type Status = { state: Tri; reason: string };
export type Capability = {
  kind: 'mcp' | 'skill';
  id: string;
  name: string;
  client: string;
  scope: string;
  project_path?: string | null;
  origin: { path: string; source: string; provenance: string };
  entry: Record<string, unknown>;
  declared_permissions: Record<string, unknown>;
  digest: string;
  secrets_removed: number;
  warnings: { kind: string; message: string }[];
  status: { configured: Status; installed: Status; available: Status; verified: Status; trusted: Status };
};

export type InventoryView =
  | { kind: 'rows'; rows: Capability[]; counts: { mcp: number; skill: number; trusted: number; verified: number }; approvalsError: string | null }
  | { kind: 'error'; text: string; hint: string };

const STATUS_KEYS = ['configured', 'installed', 'available', 'verified', 'trusted'] as const;

function isCapability(x: unknown): x is Capability {
  if (typeof x !== 'object' || x === null) return false;
  const c = x as Record<string, unknown>;
  if ((c.kind !== 'mcp' && c.kind !== 'skill') || typeof c.id !== 'string' || typeof c.name !== 'string' || typeof c.client !== 'string') return false;
  const st = c.status as Record<string, { state?: unknown; reason?: unknown }> | undefined;
  return !!st && STATUS_KEYS.every((k) => st[k] && (st[k].state === true || st[k].state === false || st[k].state === null) && typeof st[k].reason === 'string');
}

/** The engine's reply -> a view. Anything that is not exactly the documented shape is an error, never an empty or green screen. */
export function inventoryView(reply: unknown): InventoryView {
  const r = reply as { ok?: unknown; result?: { capabilities?: unknown; counts?: Record<string, number>; approvals_error?: unknown }; error?: { message?: string } } | null;
  if (!r || typeof r !== 'object') return { kind: 'error', text: 'Beklenmeyen yanıt alındı.', hint: 'Motoru yeniden başlatın veya onarım çalıştırın.' };
  if (r.ok !== true) return { kind: 'error', text: `Envanter okunamadı: ${r.error?.message ?? 'bilinmeyen hata'}`, hint: 'Yenile düğmesiyle tekrar deneyin.' };
  const list = r.result?.capabilities;
  if (!Array.isArray(list) || !list.every(isCapability)) return { kind: 'error', text: 'Envanter yanıtı beklenen biçimde değil; gösterilmedi.', hint: 'Uygulama ve motor aynı sürümde olmalı.' };
  const c = r.result?.counts ?? {};
  return {
    kind: 'rows',
    rows: list,
    counts: { mcp: c.mcp ?? 0, skill: c.skill ?? 0, trusted: c.trusted ?? 0, verified: c.verified ?? 0 },
    approvalsError: typeof r.result?.approvals_error === 'string' ? r.result.approvals_error : null,
  };
}

export type Filter = { kind: 'all' | 'mcp' | 'skill'; scope: 'all' | 'global' | 'project'; client: string; query: string; only: 'all' | 'warnings' | 'not-installed' | 'trusted' };
export const NO_FILTER: Filter = { kind: 'all', scope: 'all', client: 'all', query: '', only: 'all' };

/** User-level capabilities are "global"; everything tied to a project (a project file or a project entry in a user file) is "project". */
export const scopeGroup = (c: Capability): 'global' | 'project' => (c.scope === 'user' ? 'global' : 'project');

/** Search folding that works for Turkish and English typists alike: dotted/dotless i are the same letter, case is ignored, locale never matters. */
export const fold = (s: string): string => s.replace(/[ıİ]/g, 'i').toLowerCase();

export function applyFilter(rows: Capability[], f: Filter): Capability[] {
  const q = fold(f.query.trim());
  return rows.filter((c) =>
    (f.kind === 'all' || c.kind === f.kind) &&
    (f.scope === 'all' || scopeGroup(c) === f.scope) &&
    (f.client === 'all' || c.client === f.client) &&
    (f.only === 'all' ||
      (f.only === 'warnings' && c.warnings.length > 0) ||
      (f.only === 'not-installed' && c.status.installed.state === false) ||
      (f.only === 'trusted' && c.status.trusted.state === true)) &&
    (q === '' || fold(`${c.name} ${c.client} ${c.origin.path}`).includes(q)));
}

export const clients = (rows: Capability[]): string[] => [...new Set(rows.map((c) => c.client))].sort();

const WORDS: Record<(typeof STATUS_KEYS)[number], [string, string, string]> = {
  configured: ['Yapılandırılmış', 'Yapılandırılmamış', 'Bilinmiyor'],
  installed: ['Kurulu', 'Kurulu değil', 'Kurulum bilinmiyor'],
  available: ['Kullanılabilir görünüyor', 'Kullanılamıyor', 'Erişilebilirlik denenmedi'],
  verified: ['Doğrulandı', 'Doğrulanmadı', 'Doğrulanmadı'],
  trusted: ['Güvenilir (onay kaydı var)', 'Güvenilir değil', 'Güvenilir değil'],
};

/** Five separate, fixed-order labels. `verified` and `trusted` can only read positive when the engine says so; unknown is never shown as yes. */
export function statusLabels(c: Capability): { key: string; text: string; state: Tri; reason: string }[] {
  return STATUS_KEYS.map((key) => {
    const s = c.status[key];
    const [yes, no, unknown] = WORDS[key];
    return { key, text: s.state === true ? yes : s.state === false ? no : unknown, state: s.state, reason: s.reason };
  });
}

/** Local "this warning is a false alarm" notes. They are a viewer convenience: they hide nothing, and change no status or trust. */
export const toggleFlag = (flags: ReadonlySet<string>, id: string): Set<string> => {
  const next = new Set(flags);
  if (next.has(id)) next.delete(id); else next.add(id);
  return next;
};

/** There is deliberately no activate / install / trust function. This list is what the screen is allowed to offer. */
export const SCREEN_ACTIONS = ['refresh', 'filter', 'flag-false-positive'] as const;

const WARNING_TR: Record<string, string> = {
  launches_local_process: 'Etkinleştirilirse yetkilerinizle yerel bir program başlatır.',
  secrets_in_config: 'Gizli değerler istemci yapılandırmasında duruyor; bu görünümden çıkarıldı.',
  unknown_transport: 'Ne komut ne de adres tanımlı; çalışma biçimi bilinmiyor.',
  duplicate_name: 'Aynı ada sahip başka tanımlar var.',
  instruction_like_text: 'Açıklaması modele verilmiş talimat gibi okunuyor; yalnızca metin olarak gösterilir.',
  self_declared_manifest: 'İçindeki manifest.json yok sayılır: güven yalnızca onay kaydından gelir.',
};

/** Known warning kinds in Turkish; an unknown kind keeps the engine's own text so nothing is hidden. */
export const warningText = (w: { kind: string; message: string }): string => WARNING_TR[w.kind] ?? w.message;
