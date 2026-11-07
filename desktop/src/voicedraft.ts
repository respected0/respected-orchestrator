// Pure logic for the voice screen (B4-06). No React, no Tauri, no browser APIs: testable under `node --test`.
// Voice is text input to a DRAFT. Nothing here can start, approve or apply; a draft becomes usable text only after the person edited
// or explicitly accepted it (`confirmedText`), and that text is only ever copied for the person to paste where they choose.

export const SAMPLE_RATE = 16_000;
export const CHUNK_BYTES = 32 * 1024; // raw bytes per voice.feed; base64 of it stays well under the 64 KiB request limit
export const VOICE_COMMANDS = ['voice.status', 'voice.start', 'voice.feed', 'voice.stop', 'voice.cancel'] as const;

export type Failure = { kind: 'error'; text: string; hint: string };
export type Status = { kind: 'status'; enabled: boolean; engineReady: boolean; state: string; maxSeconds: number; held: number; networkIsolated: boolean };
export type Correction = { heard: string; replaced_with: string; at: number; applied: boolean; score: number };
export type Draft = { kind: 'draft'; id: string; language: 'tr' | 'en'; text: string; original: string; corrections: Correction[]; confidence: number; highStakes: string[] };

const str = (x: unknown): x is string => typeof x === 'string';
const failure = (text: string, hint = 'Tekrar deneyin; sorun sürerse motoru onarın.'): Failure => ({ kind: 'error', text, hint });

type Reply = { ok?: unknown; result?: unknown; error?: { message?: string } } | null;

/** "VOICE_OFF: voice input is switched off ..." -> a sentence the person understands. Unknown codes are shown as received, never hidden. */
const CODE_TEXT: Record<string, string> = {
  VOICE_OFF: 'Sesli görev taslağı ayarlarda kapalı. Ayarlardan açmadıkça mikrofon hiç kullanılmaz.',
  NO_PERMISSION: 'Mikrofon izni verilmedi; kayıt başlatılmadı.',
  PERMISSION_REVOKED: 'Mikrofon izni geri alındı; ses atıldı.',
  TOO_LONG: 'Kayıt süre sınırına ulaştı; ses atıldı.',
  TOO_LARGE: 'Ses sınırı aşıldı; ses atıldı.',
  NO_ENGINE: 'Yerel konuşma tanıma programı ayarlanmamış. Görevi yazarak girin.',
  ENGINE_FAILED: 'Konuşma tanıma programı hata verdi; ses atıldı. Görevi yazarak girin.',
  BAD_ENGINE: 'Konuşma tanıma programı ayarı geçersiz.',
  BAD_LANGUAGE: 'Dil Türkçe veya İngilizce olmalı.',
  BUSY: 'Zaten bir kayıt sürüyor.',
  NOT_RECORDING: 'Kayıt açık değil; gelen ses atıldı.',
};

export function errorText(message: string | undefined): string {
  const code = (message ?? '').split(':')[0];
  return CODE_TEXT[code] ?? (message || 'bilinmeyen hata');
}

function unwrap(reply: unknown, what: string): { ok: true; r: Record<string, any> } | { ok: false; f: Failure } {
  const r = reply as Reply;
  if (!r || typeof r !== 'object') return { ok: false, f: failure(`${what}: beklenmeyen yanıt alındı.`) };
  if (r.ok !== true) return { ok: false, f: failure(`${what}: ${errorText(r.error?.message)}`, 'Mikrofon kapalı ve ses atıldı. Görevi yazarak girebilirsiniz.') };
  if (typeof r.result !== 'object' || r.result === null || Array.isArray(r.result)) return { ok: false, f: failure(`${what}: yanıt beklenen biçimde değil; gösterilmedi.`) };
  return { ok: true, r: r.result as Record<string, any> };
}

export function statusView(reply: unknown): Status | Failure {
  const got = unwrap(reply, 'Ses durumu okunamadı');
  if (!got.ok) return got.f;
  const r = got.r;
  if (typeof r.enabled !== 'boolean' || typeof r.engine_ready !== 'boolean' || !str(r.state) || typeof r.max_seconds !== 'number') return failure('Ses durumu beklenen biçimde değil; gösterilmedi.');
  return { kind: 'status', enabled: r.enabled, engineReady: r.engine_ready, state: r.state, maxSeconds: r.max_seconds, held: Number(r.audio_bytes_held ?? 0), networkIsolated: r.network_isolated === true };
}

export function draftView(reply: unknown): Draft | Failure {
  const got = unwrap(reply, 'Ses metne çevrilemedi');
  if (!got.ok) return got.f;
  const r = got.r;
  const ok = str(r.draft_id) && str(r.text) && str(r.original) && (r.language === 'tr' || r.language === 'en') && Array.isArray(r.corrections) && Array.isArray(r.high_stakes_words)
    && r.needs_review === true && r.confirmed === false && r.source === 'voice';
  if (!ok) return failure('Taslak beklenen biçimde değil; gösterilmedi.');
  return { kind: 'draft', id: r.draft_id, language: r.language, text: r.text, original: r.original, corrections: r.corrections as Correction[], confidence: Number(r.confidence ?? 0), highStakes: r.high_stakes_words as string[] };
}

/** Source of truth for what the person may take away: the text they see in the box AFTER they pressed accept. Empty or unreviewed = nothing. */
export function confirmedText(draft: Draft | null, edited: string, accepted: boolean): string | null {
  if (!draft || !accepted) return null;
  const text = edited.trim();
  return text.length >= 1 && text.length <= 4000 ? text : null;
}

/** Words to underline in the draft text: applied corrections are shown as done, near misses as suggestions. */
export function marks(draft: Draft): { text: string; hint: string | null }[] {
  const spans = draft.corrections.filter((c) => c.applied && Number.isInteger(c.at) && draft.text.startsWith(c.replaced_with, c.at)).sort((a, b) => a.at - b.at);
  const out: { text: string; hint: string | null }[] = [];
  let at = 0;
  for (const c of spans) {
    if (c.at < at) continue;
    if (c.at > at) out.push({ text: draft.text.slice(at, c.at), hint: null });
    out.push({ text: c.replaced_with, hint: `"${c.heard}" olarak duyuldu, "${c.replaced_with}" yapıldı` });
    at = c.at + c.replaced_with.length;
  }
  if (at < draft.text.length) out.push({ text: draft.text.slice(at), hint: null });
  return out;
}

export const suggestions = (draft: Draft) => draft.corrections.filter((c) => !c.applied);

export function highStakesNote(draft: Draft): string | null {
  return draft.highStakes.length === 0 ? null : `Taslakta "${draft.highStakes.join('", "')}" sözcüğü geçiyor. Bu yalnızca metindir; onaylama, uygulama veya silme ses ile yapılamaz.`;
}

// ---------------------------------------------------------------------------------------------------------------- audio helpers
/** Float32 samples at `inRate` -> little-endian 16-bit mono PCM at 16 kHz (linear resampling; speech needs nothing fancier). */
export function toPcm16(samples: Float32Array, inRate: number): Uint8Array {
  if (!(inRate > 0)) throw new RangeError('sample rate must be positive');
  const ratio = inRate / SAMPLE_RATE;
  const n = Math.floor(samples.length / ratio);
  const out = new DataView(new ArrayBuffer(n * 2));
  for (let i = 0; i < n; i++) {
    const pos = i * ratio, a = Math.floor(pos), b = Math.min(a + 1, samples.length - 1), f = pos - a;
    const v = Math.max(-1, Math.min(1, samples[a] * (1 - f) + samples[b] * f));
    out.setInt16(i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  return new Uint8Array(out.buffer);
}

export function* chunks(bytes: Uint8Array, size = CHUNK_BYTES): Generator<Uint8Array> {
  for (let i = 0; i < bytes.length; i += size) yield bytes.subarray(i, Math.min(i + size, bytes.length));
}

export function toBase64(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

/** 0..1 loudness for the level meter. */
export function level(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  let sum = 0;
  for (const v of samples) sum += v * v;
  return Math.min(1, Math.sqrt(sum / samples.length) * 4);
}

export type Phase = 'idle' | 'recording' | 'transcribing' | 'review' | 'error';
/** What the microphone indicator says. Only "recording" means the microphone is open. */
export function indicator(phase: Phase): { text: string; micOpen: boolean } {
  if (phase === 'recording') return { text: 'Mikrofon AÇIK — kayıt sürüyor', micOpen: true };
  if (phase === 'transcribing') return { text: 'Mikrofon kapalı — ses yerelde metne çevriliyor', micOpen: false };
  return { text: 'Mikrofon kapalı', micOpen: false };
}
