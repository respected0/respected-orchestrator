// Pure helpers of the agent terminal pane (ADR-035), testable under `node --test`: bytes <-> base64, the size the engine accepts,
// which terminal belongs to a folder. What a terminal draws is the program's own output; it is only ever handed to the terminal emulator.

/** `conversation`: the chat conversation this terminal continues, when it was switched over from one. */
export type TerminalView = { id: string; project_root: string; agent: string; conversation?: string | null; started: number; alive: boolean | null; exit: number | null; cols: number | null; rows: number | null };
export type TerminalNote =
  | { event: 'terminal.data'; data: { terminal_id: string; data: string } }
  | { event: 'terminal.exit'; data: { terminal_id: string; exit: number } }
  | { event: 'terminal.closed'; data: { terminal_id: string } };

export function toBase64(bytes: Uint8Array): string {
  let text = '';
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}

export function fromBase64(text: string): Uint8Array {
  const raw = atob(text), out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/** What was typed or pasted, as the base64 `terminal.input` takes. */
export const keysToBase64 = (typed: string): string => toBase64(new TextEncoder().encode(typed));

const within = (n: number, low: number, high: number): number => Math.min(high, Math.max(low, Math.floor(n) || low));
/** The engine refuses sizes outside 20-500 x 5-200; a pane dragged very small still gets a valid grid. */
export const clampSize = (cols: number, rows: number): { cols: number; rows: number } => ({ cols: within(cols, 20, 500), rows: within(rows, 5, 200) });

const samePath = (a: string, b: string): boolean => a.replace(/[\\/]+$/, '').toLowerCase() === b.replace(/[\\/]+$/, '').toLowerCase();
/** The newest terminal opened in this folder, or null. */
export function terminalFor(list: TerminalView[], root: string): TerminalView | null {
  return list.filter((t) => samePath(t.project_root, root)).sort((a, b) => b.started - a.started)[0] ?? null;
}

const WORDS: Record<string, string> = {
  FORBIDDEN: 'Ajan terminali yalnız kurulu masaüstü uygulamasından açılabilir.', AGENT_NOT_INSTALLED: 'Ajan kurulu değil.', AGENT_UNKNOWN: 'Bu ajan tanınmıyor.',
  ROOT_INVALID: 'Proje klasörü geçerli bir mevcut tam yol olmalı.', TOO_MANY_TERMINALS: 'Çok fazla açık terminal var.', TERMINAL_UNKNOWN: 'Terminal bulunamadı ya da kapandı.',
  TERMINAL_START_FAILED: 'Terminal başlatılamadı.', TERMINAL_UNREACHABLE: 'Terminale ulaşılamadı.',
  TURN_RUNNING: 'Bir tur çalışıyor; bitmesini bekle ya da durdur.', RESUME_INVALID: 'Ajan bu oturuma henüz kimlik vermedi; terminalde sürdürülemez.',
  HANDOFF_UNSUPPORTED: 'Bu ajanın oturumu terminalde sürdürülemiyor.', SESSION_UNKNOWN: 'Oturum bulunamadı.',
};
/** An engine refusal as words; the engine's code decides, its English message is only the last resort. */
export function refusalText(error: { code?: string; message?: string; reason?: string } | null): string {
  return WORDS[error?.reason ?? ''] ?? WORDS[error?.code ?? ''] ?? `Motor reddetti: ${(error?.message ?? '').slice(0, 200)}`;
}
