// Pure session-screen logic (no React, no Tauri) so it can be tested under `node --test`.
// Everything a session stream contains is untrusted data: it is turned into plain text lines and never into an action.

/** The only commands the screen sends; generated from the engine's one table, like the Rust relay's list (ADR-032). There is no approve. */
import { SESSION_COMMANDS } from './contracts/catalog.ts';
export { SESSION_COMMANDS };
export type SessionCommand = (typeof SESSION_COMMANDS)[number];

export const PROJECT_ID = 'proj-sessions';

export type State = 'idle' | 'running' | 'failed' | 'ended';
export type CommandState = { enabled: boolean; reason: string | null };
export type SessionView = {
  id: string; project_id: string; agent: string; model: string; mode: string; state: State; retries: number; last_state: string | null; turn: number;
  project_root: string; title: string;
  commands: Record<'send' | 'retry' | 'interrupt' | 'cancel' | 'resume', CommandState>;
};
/** One sidebar row, ordered and titled by the engine. `saved`: a conversation from an earlier run (read-only until continued). */
export type Conversation = { id: string; title: string; state: State; project_root: string; updated: number; saved: boolean;
  pinned: boolean; archived: boolean; match: string | null };
export type Usage = { input: number; output: number; reasoning: number; cache_read: number; cost: number | null; last_input: number | null; steps: number };
/** The running turn's events so far (ADR-034). */
export type Live = { turn: number; events: StreamEvent[] };
/** One page of a conversation: `turns` start at turn index `first` of `total`; `first` is the `before` of the page above. */
export type Transcript = { id: string; title: string; project_root: string; agent: string; model: string; resumable: boolean; turns: import('./chatmodel').Turn[]; usage: Usage | null;
  first: number; total: number; live: Live | null };
/** What the engine pushes on the notification stream; `stream.closed` is the shell's own word for "ask again". */
export type Note =
  | { event: 'session.event'; data: { session_id: string; turn: number; event: StreamEvent } }
  | { event: 'session.state'; data: { session: SessionView } }
  | { event: 'stream.closed' };
export type Defaults = { agents: string[]; modes: string[]; agent: string; model: string };

/** The engine's permission modes (KALAN_ISLER 4.6) in words: the name on the chip and what the agent may do. Only the person picks one. */
export const MODE_TEXT: Record<string, [string, string]> = {
  default: ['Salt okunur', 'Ajan projeyi okur; dosya değiştiremez, komut çalıştıramaz, ağa çıkamaz.'],
  'accept-edits': ['Düzenlemeleri kabul et', 'Ajan proje klasöründeki dosyaları sormadan değiştirir; komut çalıştıramaz, ağa çıkamaz.'],
  'bypass-permissions': ['Tüm izinler', 'Ajan sormadan dosya değiştirir, komut çalıştırır ve ağa çıkar. Yalnız güvendiğiniz bir projede kullanın.'],
};
export const modeText = (id: string): [string, string] => MODE_TEXT[id] ?? [id, 'Motorun bildirdiği kip; açıklaması yok.'];
export type StreamEvent = { kind: string; [k: string]: unknown };
export type TurnResult = { state: string; complete: boolean; events: StreamEvent[]; error?: string } | null;

export const STATE_TEXT: Record<State, string> = { idle: 'Hazır', running: 'Çalışıyor', failed: 'Başarısız', ended: 'Bitti' };
export const COMMAND_TEXT = { send: 'Gönder', retry: 'Yeniden dene', interrupt: 'Turu durdur', cancel: 'Oturumu bitir', resume: 'Sürdür' } as const;
export const REASON_TEXT: Record<string, string> = {
  TURN_RUNNING: 'Bir tur çalışıyor.', LAST_TURN_FAILED: 'Son tur başarısız oldu.', SESSION_ENDED: 'Oturum bitti.', NOT_AVAILABLE: 'Bu durumda kullanılamaz.',
};
export const stateText = (s: string): string => STATE_TEXT[s as State] ?? 'Bilinmiyor';
export const reasonText = (r: string | null): string => (r ? REASON_TEXT[r] ?? 'Şu an kullanılamaz.' : '');

const MAX_JSON = 300;
const compact = (v: unknown): string => {
  let t: string;
  try { t = typeof v === 'string' ? v : JSON.stringify(v) ?? ''; } catch { t = ''; }
  return t.length > MAX_JSON ? t.slice(0, MAX_JSON) + '…' : t;
};
const str = (v: unknown): string => (typeof v === 'string' ? v : v === undefined || v === null ? '' : compact(v));

/** One finished turn as transcript lines. Prefixes say what the line is; the text after them is the model's/tool's, shown as data. */
export function transcriptLines(events: StreamEvent[]): string[] {
  const out: string[] = [];
  for (const e of events) {
    if (e.kind === 'message') out.push(...str(e.text).split('\n'));
    else if (e.kind === 'tool_call') out.push(`[araç] ${str(e.tool)} (${str(e.status) || '?'})`);
    else if (e.kind === 'ask_user') out.push(`[soru] ${compact(e.input)}`, '[soru] Bu oturumdaki sorular buradan yanıtlanamaz.');
    else if (e.kind === 'usage') out.push(`[kullanım] giriş ${str(e.input)} · çıkış ${str(e.output)} · maliyet ${str(e.cost)} · kota ${str(e.quota) || 'unknown'}`);
    else if (e.kind === 'error') out.push(`[hata] ${str(e.message) || str(e.text) || 'bilinmeyen hata'}`);
    else if (e.kind === 'unknown') out.push('[?] tanınmayan olay');
  }
  return out;
}

export type Relay = (cmd: SessionCommand, payload: Record<string, unknown>) => Promise<{ ok: boolean; result: unknown; error: { code: string; message: string } | null }>;

/** Engine refusals are data: they become a message for the person, not an exception that hides the screen. */
export async function call<T>(relay: Relay, cmd: SessionCommand, payload: Record<string, unknown>): Promise<{ ok: true; value: T } | { ok: false; text: string }> {
  if (!SESSION_COMMANDS.includes(cmd)) return { ok: false, text: 'Bu komut ekrandan gönderilmez.' };
  try {
    const r = await relay(cmd, { project_id: PROJECT_ID, ...payload });
    if (r.ok) return { ok: true, value: r.result as T };
    const reason = (r.error as { reason?: string } | null)?.reason ?? '';
    if (REJECT_TEXT[reason]) return { ok: false, text: REJECT_TEXT[reason] };
    const code = r.error?.code ?? 'ENGINE_ERROR';
    const known: Record<string, string> = { FORBIDDEN: 'Bu işleme izin yok.', BAD_REQUEST: 'İstek geçersiz.', UNAUTHENTICATED: 'Motor oturumu doğrulanamadı.' };
    return { ok: false, text: known[code] ?? `Motor reddetti: ${(r.error?.message ?? '').slice(0, 200)}` };
  } catch (e) {
    const kind = (e as { error?: { kind?: string } })?.error?.kind;
    return { ok: false, text: kind === 'NotInstalled' ? 'Motor kurulu değil.' : 'Motora ulaşılamadı.' };
  }
}

/** The engine says why with a code; these are only the words for it. */
export const REJECT_TEXT: Record<string, string> = {
  MODEL_INVALID: 'Bu model ajanın listesinde yok.', MODELS_UNAVAILABLE: 'Ajan model listesini veremedi.', ROOT_INVALID: 'Proje klasörü geçerli bir mevcut tam yol olmalı.',
  TEXT_EMPTY: 'İleti boş.', TEXT_TOO_LONG: 'İleti çok uzun (en çok 8000 karakter).', TEXT_UNSAFE: 'İletide denetim karakteri var.',
  AGENT_NOT_INSTALLED: 'Ajan kurulu değil.', TOO_MANY_SESSIONS: 'Çok fazla açık oturum var.', SESSION_UNKNOWN: 'Oturum bulunamadı.',
  SESSION_LIVE: 'Önce oturumu bitir.', RESUME_INVALID: 'Devam ettirilecek oturum geçersiz.', MODE_INVALID: 'Bu izin kipi bilinmiyor.', TURN_RUNNING: 'Bir tur çalışıyor.',
  TITLE_EMPTY: 'Başlık boş olamaz.', TITLE_TOO_LONG: 'Başlık çok uzun (en çok 120 karakter).', TITLE_INVALID: 'Başlık geçersiz.', TITLE_UNSAFE: 'Başlıkta denetim karakteri var.',
  PIN_INVALID: 'Sabitleme değeri geçersiz.', ARCHIVE_INVALID: 'Arşiv değeri geçersiz.', EXPORT_INVALID: 'Dışa aktarma biçimi geçersiz.',
};
/** Sidebar order: pinned first, then newest. The engine sorts the same way; this keeps the screen right after a local change. */
export const orderConversations = <T extends { pinned: boolean; updated: number }>(rows: T[]): T[] =>
  [...rows].sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updated - a.updated);

/** The engine names the file; this is the screen's last line of defence against a title that is a path. */
export function exportName(title: string, format: 'markdown' | 'json'): string {
  if (format === 'json') return 'sohbet.json';
  const clean = title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, ' ').replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '').slice(0, 80).trim();
  return `${clean || 'sohbet'}.md`;
}
export const EXPORT_MAX_BYTES = 4 * 1024 * 1024;
export const exportTooBig = (text: string): boolean => new TextEncoder().encode(text).length > EXPORT_MAX_BYTES;
/** Search hits arrive as a short engine snippet; it is shown as one plain line. */
export const matchSnippet = (m: string | null | undefined): string =>
  (m ?? '').replace(/[\u0000-\u001f\u007f-\u009f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 140);

/** How long the screen waits before asking for the notification stream again after it closed or could not be opened. */
export const RESUBSCRIBE_MS = 2000;
/** Why an OS notice is due: a turn finished, failed, or the session ended. The kind, not the text, crosses into Rust, so no turn content can. */
export type NoticeKind = 'turn-finished' | 'failed' | 'ended';
export function notifyReason(prev: string | undefined, next: string): NoticeKind | null {
  if (!prev || prev === next) return null;
  if (next === 'failed') return 'failed';
  if (next === 'ended') return 'ended';
  if (next === 'idle' && prev === 'running') return 'turn-finished';
  return null;
}

/** Nothing is shown for the session the person is looking at in a focused window; anywhere else, it is. */
export function shouldNotify(prev: string | undefined, next: string, focused: boolean, selected: boolean): NoticeKind | null {
  return focused && selected ? null : notifyReason(prev, next);
}

/** A page the engine just returned joined onto the turns already on screen (an older page goes in front, a newer one replaces the tail).
 *  Everything else is the page's, because it is the newer answer. Pages that do not touch leave a hole: then only the page is kept. */
export function joinPages(old: Transcript | undefined, page: Transcript): Transcript {
  if (!old) return page;
  const [a, b] = page.first < old.first ? [page, old] : [old, page];
  if (b.first > a.first + a.turns.length) return page;
  // pushed events can be ahead of a page that was on its way: the longer view of the same running turn stays
  const live = old.live && page.live && old.live.turn === page.live.turn && old.live.events.length > page.live.events.length ? old.live : page.live;
  return { ...page, live, first: a.first, turns: [...a.turns.slice(0, b.first - a.first), ...b.turns] };
}

/** One pushed event added to the running turn. A repeat changes nothing; `null` means an event was missed and the transcript must be read again. */
export function applyLive(cur: Live | null, turn: number, event: StreamEvent): Live | null {
  const base = cur && cur.turn === turn ? cur : { turn, events: [] };
  const seq = event.seq;
  if (typeof seq !== 'number' || seq > base.events.length) return null;
  return seq < base.events.length ? base : { turn, events: [...base.events, event] };
}

