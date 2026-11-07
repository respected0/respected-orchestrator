// Pure session-screen logic (no React, no Tauri) so it can be tested under `node --test`.
// Everything a session stream contains is untrusted data: it is turned into plain text lines and never into an action.

/** The only commands the screen sends; src-tauri/src/engine_connector.rs keeps the same list and a test compares them. There is no approve. */
export const SESSION_COMMANDS = ['sessions.list', 'session.start', 'session.events', 'session.send', 'session.retry', 'session.interrupt', 'session.cancel', 'session.resume'] as const;
export type SessionCommand = (typeof SESSION_COMMANDS)[number];

export const PROJECT_ID = 'proj-sessions';
export const DEFAULT_MODEL = 'opencode/deepseek-v4.1-flash-free';
export const AGENTS = ['opencode'] as const; // the only agent with a verified structured stream (engine/chat_session.py)

export type State = 'idle' | 'running' | 'failed' | 'ended';
export type CommandState = { enabled: boolean; reason: string | null };
export type SessionView = {
  id: string; project_id: string; agent: string; model: string; state: State; retries: number; last_state: string | null;
  commands: Record<'send' | 'retry' | 'interrupt' | 'cancel' | 'resume', CommandState>;
};
export type StreamEvent = { kind: string; [k: string]: unknown };
export type TurnResult = { state: string; complete: boolean; events: StreamEvent[]; error?: string } | null;

export const STATE_TEXT: Record<State, string> = { idle: 'Hazır', running: 'Çalışıyor', failed: 'Başarısız', ended: 'Bitti' };
export const COMMAND_TEXT = { send: 'Gönder', retry: 'Yeniden dene', interrupt: 'Turu durdur', cancel: 'Oturumu bitir', resume: 'Sürdür' } as const;
export const REASON_TEXT: Record<string, string> = {
  'a turn is running': 'Bir tur çalışıyor.', 'last turn failed': 'Son tur başarısız oldu.', 'session ended': 'Oturum bitti.',
  'not available in this state': 'Bu durumda kullanılamaz.',
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
    if ((r.error?.message ?? '').startsWith('Chat sessions are disabled')) return { ok: false, text: DISABLED_TEXT };
    const code = r.error?.code ?? 'ENGINE_ERROR';
    const known: Record<string, string> = { FORBIDDEN: 'Bu işleme izin yok.', BAD_REQUEST: 'İstek geçersiz.', UNAUTHENTICATED: 'Motor oturumu doğrulanamadı.' };
    return { ok: false, text: known[code] ?? `Motor reddetti: ${(r.error?.message ?? '').slice(0, 200)}` };
  } catch (e) {
    const kind = (e as { error?: { kind?: string } })?.error?.kind;
    return { ok: false, text: kind === 'NotInstalled' ? 'Motor kurulu değil.' : 'Motora ulaşılamadı.' };
  }
}

export const DISABLED_TEXT = 'Sohbet oturumları kapalı: ajan henüz sandbox içinde çalışamadığı için motor onu yalnız operatör RESPECTED_CHAT_UNSANDBOXED=allow ayarladığında başlatır. Dosya değiştiren ve komut çalıştıran araçlar o durumda da kapalı kalır.';

export const POLL_MS = 1000;
/** A running turn is polled; nothing else is. */
export const shouldPoll = (s: SessionView): boolean => s.state === 'running';

export type StartForm = { root: string; model: string; text: string };
/** The same rules the engine applies; here only to give the person an immediate reason (the engine still decides). */
export function startProblem(f: StartForm): string | null {
  if (!/^([A-Za-z]:[\\/]|\\\\|\/)/.test(f.root.trim())) return 'Proje klasörü tam yol olmalı (ör. C:\\Projeler\\uygulama).';
  if (!/^[\w.-]+\/[\w.:-]+$/.test(f.model.trim())) return 'Model "sağlayıcı/ad" biçiminde olmalı.';
  if (!f.text.trim()) return 'İleti boş.';
  if (f.text.length > 8000) return 'İleti çok uzun (en çok 8000 karakter).';
  if (/[\x00-\x08\x0b-\x1f\x7f-\x9f]/.test(f.text)) return 'İletide denetim karakteri var.';
  return null;
}
