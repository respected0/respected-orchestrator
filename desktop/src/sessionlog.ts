// Pure session-screen logic (no React, no Tauri) so it can be tested under `node --test`.
// Everything a session stream contains is untrusted data: it is turned into plain text lines and never into an action.

/** The only commands the screen sends; src-tauri/src/engine_connector.rs keeps the same list and a test compares them. There is no approve. */
export const SESSION_COMMANDS = ['sessions.list', 'session.start', 'session.events', 'session.send', 'session.retry', 'session.interrupt', 'session.cancel', 'session.resume', 'session.models', 'session.defaults', 'session.defaults.set', 'session.transcript', 'session.forget'] as const;
export type SessionCommand = (typeof SESSION_COMMANDS)[number];

export const PROJECT_ID = 'proj-sessions';

export type State = 'idle' | 'running' | 'failed' | 'ended';
export type CommandState = { enabled: boolean; reason: string | null };
export type SessionView = {
  id: string; project_id: string; agent: string; model: string; state: State; retries: number; last_state: string | null; turn: number;
  project_root: string; title: string;
  commands: Record<'send' | 'retry' | 'interrupt' | 'cancel' | 'resume', CommandState>;
};
/** One sidebar row, ordered and titled by the engine. `saved`: a conversation from an earlier run (read-only until continued). */
export type Conversation = { id: string; title: string; state: State; project_root: string; updated: number; saved: boolean };
export type Usage = { input: number; output: number; reasoning: number; cache_read: number; cost: number | null; last_input: number | null; steps: number };
export type Transcript = { id: string; title: string; project_root: string; agent: string; model: string; resumable: boolean; turns: import('./chatmodel').Turn[]; usage: Usage | null };
export type Defaults = { agents: string[]; agent: string; model: string };
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
    if (reason === 'CHAT_DISABLED') return { ok: false, text: DISABLED_TEXT };
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
  SESSION_LIVE: 'Önce oturumu bitir.', RESUME_INVALID: 'Devam ettirilecek oturum geçersiz.',
};
export const DISABLED_TEXT = 'Sohbet oturumları kapalı: ajan henüz sandbox içinde çalışamadığı için motor onu yalnız operatör RESPECTED_CHAT_UNSANDBOXED=allow ayarladığında başlatır. Dosya değiştiren ve komut çalıştıran araçlar o durumda da kapalı kalır.';

export const POLL_MS = 1000;
/** A running turn is polled; nothing else is. */
export const shouldPoll = (s: SessionView): boolean => s.state === 'running';

