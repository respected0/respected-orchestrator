// Pure logic for the screenshot screen (B4-07). No React, Tauri or canvas: testable under `node --test`.
// The person picks an image, blacks out what must not leave, previews the ENGINE'S cleaned bytes, and only then asks to attach; the attach itself
// and any sharing with a model are confirmed in a native dialog the screen cannot reach. Nothing here uploads anything on its own.

export const ATTACH_COMMANDS = ['attachment.status', 'attachment.arm', 'attachment.part', 'attachment.stage', 'attachment.preview', 'attachment.list', 'attachment.cancel', 'attachment.delete'] as const;
export const RUN_ID = /^run-\d{14}-[0-9a-f]{12}$/;

export type Failure = { kind: 'error'; text: string; hint: string };
export type Status = { kind: 'status'; enabled: boolean; maxBytes: number; maxSide: number };
export type Staged = { kind: 'staged'; stageId: string; sha256: string; width: number; height: number; bytes: number; metadataRemoved: number };
export type Preview = { kind: 'preview'; stageId: string; sha256: string; url: string; width: number; height: number };
export type Consent = { state: 'none' | 'active' | 'revoked' | 'expired' | 'unreadable'; provider?: string; expires_at?: number };
export type Row = { id: string; width: number; height: number; bytes: number; redacted_regions: number; expires_at: number; consent: Consent; shared_with_model: boolean };
export type Listing = { kind: 'list'; rows: Row[] };

const CODE_TEXT: Record<string, string> = {
  CAPTURE_OFF: 'Ekran görüntüsü ekleme ayarlarda kapalı. Ayarlardan açmadıkça hiçbir görüntü alınmaz.',
  NO_PERMISSION: 'İzin verilmedi; görüntü oluşturulmadı.',
  BAD_FORMAT: 'Yalnızca PNG ve JPEG kabul edilir (SVG, GIF, WebP, PDF reddedilir).',
  TOO_LARGE: 'Görüntü çok büyük (en çok 8 MB).',
  TOO_BIG: 'Görüntünün boyutları sınırı aşıyor.',
  MALFORMED: 'Görüntü dosyası bozuk; reddedildi.',
  BAD_PART: 'Yükleme bozuldu veya çok büyüktü; görüntü atıldı.',
  NOT_ARMED: 'Yakalama başlatılmamıştı; görüntü atıldı.',
  EXPIRED: 'Süre doldu; görüntüyü yeniden seçin.',
  NOT_FOUND: 'Görüntü bulunamadı (süresi dolmuş olabilir).',
  PREVIEW_REQUIRED: 'Görüntü önizlemeden sonra değişti; yeniden önizleyin.',
  WRONG_RUN: 'Görüntü yalnızca henüz başlamamış, var olan bir çalıştırmaya eklenebilir.',
  BAD_PROVIDER: 'Görüntüyü alacak sağlayıcının adını yazın.',
  Denied: 'Onaylamadınız; hiçbir şey eklenmedi veya paylaşılmadı.',
};

export function errorText(message: unknown): string {
  const text = typeof message === 'string' ? message : '';
  const code = text.split(':')[0].replace(/^Engine\("/, '').trim();
  return CODE_TEXT[code] ?? (text || 'bilinmeyen hata');
}

type Reply = { ok?: unknown; result?: unknown; error?: { message?: string } } | null;
const failure = (text: string): Failure => ({ kind: 'error', text, hint: 'Görüntü atıldı; hiçbir şey eklenmedi.' });
const str = (x: unknown): x is string => typeof x === 'string';
const num = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

function unwrap(reply: unknown, what: string): { ok: true; r: Record<string, any> } | { ok: false; f: Failure } {
  const r = reply as Reply;
  if (!r || typeof r !== 'object') return { ok: false, f: failure(`${what}: beklenmeyen yanıt.`) };
  if (r.ok !== true) return { ok: false, f: failure(`${what}: ${errorText(r.error?.message)}`) };
  if (typeof r.result !== 'object' || r.result === null || Array.isArray(r.result)) return { ok: false, f: failure(`${what}: yanıt beklenen biçimde değil.`) };
  return { ok: true, r: r.result as Record<string, any> };
}

export function statusView(reply: unknown): Status | Failure {
  const g = unwrap(reply, 'Durum okunamadı');
  if (!g.ok) return g.f;
  if (typeof g.r.enabled !== 'boolean' || !num(g.r.max_bytes) || !num(g.r.max_side)) return failure('Durum beklenen biçimde değil.');
  return { kind: 'status', enabled: g.r.enabled, maxBytes: g.r.max_bytes, maxSide: g.r.max_side };
}

export function stagedView(reply: unknown): Staged | Failure {
  const g = unwrap(reply, 'Görüntü hazırlanamadı');
  if (!g.ok) return g.f;
  const r = g.r;
  if (!str(r.stage_id) || !/^stg-[0-9a-f]{16}$/.test(r.stage_id) || !str(r.sha256) || !/^[0-9a-f]{64}$/.test(r.sha256) || !num(r.width) || !num(r.height) || !num(r.bytes)) return failure('Hazırlanan görüntü beklenen biçimde değil.');
  return { kind: 'staged', stageId: r.stage_id, sha256: r.sha256, width: r.width, height: r.height, bytes: r.bytes, metadataRemoved: Number(r.metadata_removed_bytes ?? 0) };
}

/** The preview is only built from the engine's own answer, with the data URL type taken from the engine's mime (png/jpeg), never from the renderer. */
export function previewView(reply: unknown): Preview | Failure {
  const g = unwrap(reply, 'Önizleme alınamadı');
  if (!g.ok) return g.f;
  const r = g.r;
  if (!str(r.stage_id) || !str(r.sha256) || !(r.mime === 'image/png' || r.mime === 'image/jpeg') || !str(r.data) || !/^(?:[A-Za-z0-9+/]{4})+(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(r.data) || !num(r.width) || !num(r.height)) return failure('Önizleme beklenen biçimde değil.');
  return { kind: 'preview', stageId: r.stage_id, sha256: r.sha256, url: `data:${r.mime};base64,${r.data}`, width: r.width, height: r.height };
}

export function listView(reply: unknown): Listing | Failure {
  const g = unwrap(reply, 'Ekler okunamadı');
  if (!g.ok) return g.f;
  const ok = (a: any): a is Row => a && str(a.id) && num(a.width) && num(a.height) && a.consent && str(a.consent.state);
  if (!Array.isArray(g.r.attachments) || !g.r.attachments.every(ok)) return failure('Ek listesi beklenen biçimde değil.');
  return { kind: 'list', rows: g.r.attachments };
}

export const consentText = (c: Consent) => c.state === 'active' ? `Modelle paylaşılıyor: ${c.provider ?? '?'} (süreli)` : c.state === 'revoked' ? 'Paylaşım geri alındı' : c.state === 'expired' ? 'Paylaşım süresi doldu' : c.state === 'unreadable' ? 'Paylaşım kaydı doğrulanamadı' : 'Modelle paylaşılmıyor';

// ------------------------------------------------------------------------------------------------------------------------ gates
/** Attach is possible only for the exact image the person previewed, with a valid queued-run id typed by them, and after they ticked the box. */
export function canAttach(staged: Staged | null, preview: Preview | null, seen: boolean, runId: string): boolean {
  return !!staged && !!preview && preview.stageId === staged.stageId && preview.sha256 === staged.sha256 && seen && RUN_ID.test(runId.trim());
}
export const canShare = (provider: string) => provider.trim().length >= 1 && provider.trim().length <= 80;

// -------------------------------------------------------------------------------------------------------------------- redaction
export type Rect = { x: number; y: number; w: number; h: number };
/** A drag in image pixels -> a clamped rectangle; a stray click (smaller than 4 px) is not a mask. */
export function rectFromDrag(x0: number, y0: number, x1: number, y1: number, width: number, height: number): Rect | null {
  const l = Math.max(0, Math.min(x0, x1)), t = Math.max(0, Math.min(y0, y1)), r = Math.min(width, Math.max(x0, x1)), b = Math.min(height, Math.max(y0, y1));
  return r - l < 4 || b - t < 4 ? null : { x: Math.round(l), y: Math.round(t), w: Math.round(r - l), h: Math.round(b - t) };
}
/** Screen -> image pixels for an element drawn at a different size than the bitmap. */
export const toImagePoint = (clientX: number, clientY: number, box: { left: number; top: number; width: number; height: number }, imgW: number, imgH: number) =>
  ({ x: ((clientX - box.left) / box.width) * imgW, y: ((clientY - box.top) / box.height) * imgH });
export const MAX_MASKS = 200;
