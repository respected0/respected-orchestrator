import { useEffect, useId, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { chunks, toBase64 } from './voicedraft';
import { MAX_MASKS, RUN_ID, canAttach, canShare, consentText, errorText, listView, previewView, rectFromDrag, stagedView, statusView, toImagePoint,
  type Failure, type Listing, type Preview, type Rect, type Staged, type Status } from './attachdraft';

const task = (cmd: string, payload: Record<string, unknown> = {}) => invoke<unknown>('session_call', { cmd, payload });
const read = (cmd: string, payload: Record<string, unknown> = {}) => invoke<unknown>('read_call', { cmd, payload });
const failText = (e: unknown) => errorText(typeof e === 'string' ? e : (e as { error?: { message?: string } })?.error?.message);

/** Attach a screenshot to a task that has not started. Capture is the person's act (choose a file or paste), masking is drawn here, the preview is the
 *  engine's cleaned copy, and attaching or sharing is confirmed in a native dialog. Nothing is uploaded until "Hazırla" and nothing is attached or
 *  sent to a model without the dialog. */
export function Screenshot() {
  const id = useId();
  const [status, setStatus] = useState<Status | Failure | null>(null);
  const [bitmap, setBitmap] = useState<ImageBitmap | null>(null);
  const [masks, setMasks] = useState<Rect[]>([]);
  const [staged, setStaged] = useState<Staged | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [seen, setSeen] = useState(false);
  const [runId, setRunId] = useState('');
  const [listing, setListing] = useState<Listing | null>(null);
  const [provider, setProvider] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => { read('attachment.status').then((r) => setStatus(statusView(r))).catch((e) => setStatus({ kind: 'error', text: failText(e), hint: 'Motoru onarın.' })); }, []);

  const draw = (extra?: Rect) => {
    const c = canvas.current;
    if (!c || !bitmap) return;
    c.width = bitmap.width; c.height = bitmap.height;
    const g = c.getContext('2d')!;
    g.drawImage(bitmap, 0, 0);
    g.fillStyle = '#000';
    for (const m of [...masks, ...(extra ? [extra] : [])]) g.fillRect(m.x, m.y, m.w, m.h);
  };
  useEffect(draw, [bitmap, masks]);

  async function load(blob: Blob | null | undefined) {
    if (!blob) return;
    setMessage(null); setStaged(null); setPreview(null); setSeen(false); setMasks([]);
    if (!(blob.type === 'image/png' || blob.type === 'image/jpeg')) { setMessage(errorText('BAD_FORMAT')); return; }
    try { setBitmap(await createImageBitmap(blob)); } catch { setMessage(errorText('MALFORMED')); }
  }

  async function prepare() {
    const c = canvas.current;
    if (!c || !bitmap) return;
    setBusy(true); setMessage(null); setPreview(null); setSeen(false); setStaged(null);
    try {
      const blob: Blob = await new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error('encode'))), 'image/png'));
      const bytes = new Uint8Array(await blob.arrayBuffer());
      const armed = await task('attachment.arm', { permission: 'granted' }) as { ok?: boolean; result?: { token: string }; error?: { message?: string } };
      if (!armed.ok || !armed.result) { setMessage(errorText(armed.error?.message)); return; }
      const token = armed.result.token;
      let seq = 0;
      for (const part of chunks(bytes)) {
        const r = await task('attachment.part', { token, seq: seq++, chunk: toBase64(part) }) as { ok?: boolean; error?: { message?: string } };
        if (!r.ok) { setMessage(errorText(r.error?.message)); return; }
      }
      const s = stagedView(await task('attachment.stage', { token }));
      if (s.kind === 'error') { setMessage(`${s.text} ${s.hint}`); return; }
      const p = previewView(await read('attachment.preview', { stage_id: s.stageId }));
      if (p.kind === 'error') { setMessage(`${p.text} ${p.hint}`); return; }
      setStaged(s); setPreview(p);
    } catch (e) { setMessage(failText(e)); } finally { setBusy(false); }
  }

  async function attach() {
    if (!staged || !canAttach(staged, preview, seen, runId)) return;
    setBusy(true); setMessage(null);
    try {
      await invoke('attach_image', { runId: runId.trim(), stageId: staged.stageId, sha256: staged.sha256, regions: Math.min(masks.length, MAX_MASKS) });
      setStaged(null); setPreview(null); setSeen(false); setBitmap(null); setMasks([]);
      setMessage('Görüntü göreve eklendi. Bu bilgisayarda kalır; hiçbir modele gönderilmedi.');
      await refreshList();
    } catch (e) { setMessage(failText(e)); } finally { setBusy(false); }
  }

  async function discard() {
    try { await task('attachment.cancel', staged ? { stage_id: staged.stageId } : {}); } catch { /* the staging file also expires on its own */ }
    setStaged(null); setPreview(null); setSeen(false); setBitmap(null); setMasks([]); setMessage('Görüntü atıldı.');
  }

  async function refreshList() {
    if (!RUN_ID.test(runId.trim())) { setMessage('Geçerli bir çalıştırma kimliği yazın (run-…).'); return; }
    const v = listView(await read('attachment.list', { run_id: runId.trim() }).catch((e) => ({ ok: false, error: { message: failText(e) } })));
    if (v.kind === 'error') setMessage(`${v.text}`); else setListing(v);
  }

  const act = (fn: () => Promise<unknown>) => async () => { setBusy(true); setMessage(null); try { await fn(); await refreshList(); } catch (e) { setMessage(failText(e)); } finally { setBusy(false); } };
  const ready = status?.kind === 'status' ? status : null;
  return (
    <section aria-labelledby={`${id}-h`} onPaste={(e) => { const f = [...e.clipboardData.files].find((x) => x.type.startsWith('image/')); if (f && ready?.enabled) { e.preventDefault(); void load(f); } }}>
      <h2 id={`${id}-h`}>Ekran görüntüsü ekle</h2>
      <p>Yalnızca <strong>sizin seçtiğiniz</strong> görüntü kullanılır: arka planda ekran yakalanmaz. Önce gizlenmesi gereken yerleri karartın, motorun temizlediği önizlemeyi görün; ekleme ve modelle paylaşma ayrı ayrı, uygulamanın dışındaki bir pencerede onaylanır.</p>
      {status?.kind === 'error' && <div role="alert"><p>{status.text}</p><p>{status.hint}</p></div>}
      {ready && !ready.enabled && <p role="status">Ekran görüntüsü ekleme ayarlarda kapalı (varsayılan). Açmadıkça hiçbir görüntü alınmaz.</p>}
      <div>
        <label>Görüntü seç (PNG veya JPEG) <input type="file" accept="image/png,image/jpeg" disabled={!ready?.enabled || busy} onChange={(e) => { void load(e.target.files?.[0]); e.target.value = ''; }} /></label>
        <p className="path">Ya da kopyaladığınız görüntüyü bu sayfaya yapıştırın (Ctrl+V).</p>
      </div>
      {bitmap && !preview && (
        <div>
          <p>Gizlemek istediğiniz yerleri fareyle sürükleyerek karartın ({masks.length} bölge).</p>
          <canvas ref={canvas} aria-label="Karartma alanı" style={{ maxWidth: '100%', border: '1px solid currentColor', touchAction: 'none', cursor: 'crosshair' }}
            onPointerDown={(e) => { const b = e.currentTarget.getBoundingClientRect(); drag.current = toImagePoint(e.clientX, e.clientY, b, bitmap.width, bitmap.height); e.currentTarget.setPointerCapture(e.pointerId); }}
            onPointerMove={(e) => { if (!drag.current) return; const b = e.currentTarget.getBoundingClientRect(); const p = toImagePoint(e.clientX, e.clientY, b, bitmap.width, bitmap.height); const r = rectFromDrag(drag.current.x, drag.current.y, p.x, p.y, bitmap.width, bitmap.height); draw(r ?? undefined); }}
            onPointerUp={(e) => { if (!drag.current) return; const b = e.currentTarget.getBoundingClientRect(); const p = toImagePoint(e.clientX, e.clientY, b, bitmap.width, bitmap.height); const r = rectFromDrag(drag.current.x, drag.current.y, p.x, p.y, bitmap.width, bitmap.height); drag.current = null; if (r && masks.length < MAX_MASKS) setMasks([...masks, r]); }} />
          <div>
            <button type="button" onClick={() => setMasks(masks.slice(0, -1))} disabled={masks.length === 0}>Son karartmayı geri al</button>{' '}
            <button type="button" onClick={prepare} disabled={busy}>Hazırla ve önizle</button>{' '}
            <button type="button" onClick={discard}>Vazgeç</button>
          </div>
        </div>
      )}
      {preview && staged && (
        <div>
          <h3>Önizleme — eklenecek görüntü bu</h3>
          <img src={preview.url} alt="Eklenecek görüntünün önizlemesi" style={{ maxWidth: '100%', border: '1px solid currentColor' }} />
          <p className="path">{staged.width} × {staged.height} · {staged.bytes} bayt · {staged.metadataRemoved} bayt üstveri silindi · {masks.length} bölge karartıldı · özet {staged.sha256.slice(0, 12)}…</p>
          <label><input type="checkbox" checked={seen} onChange={(e) => setSeen(e.target.checked)} /> Önizlemeyi gördüm; gizli bilgi kalmadı.</label>
          <div>
            <label>Çalıştırma kimliği (henüz başlamamış) <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="run-20261108000000-abcdef123456" size={36} /></label>
          </div>
          <button type="button" onClick={attach} disabled={busy || !canAttach(staged, preview, seen, runId)}>Göreve ekle (onay penceresi açılır)</button>{' '}
          <button type="button" onClick={discard}>Vazgeç</button>
        </div>
      )}
      {message && <div role="status"><p>{message}</p></div>}
      <h3>Bir çalıştırmanın ekleri</h3>
      <div><label>Çalıştırma kimliği <input value={runId} onChange={(e) => setRunId(e.target.value)} size={36} /></label>{' '}<button type="button" onClick={refreshList} disabled={busy}>Ekleri göster</button></div>
      {listing && (listing.rows.length === 0 ? <p>Bu çalıştırmada ek yok.</p> : (
        <ul>
          {listing.rows.map((r) => (
            <li key={r.id}>
              {r.width}×{r.height} · {r.bytes} bayt · {r.redacted_regions} bölge karartıldı · <span data-state={r.consent.state}>{consentText(r.consent)}</span>{' '}
              <button type="button" disabled={busy} onClick={act(() => invoke('revoke_image', { runId: runId.trim(), attachmentId: r.id }))}>Paylaşımı geri al</button>
              <label> Sağlayıcı <input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="ör. sağlayıcı adı" /></label>
              <button type="button" disabled={busy || !canShare(provider)} onClick={act(() => invoke('share_image', { runId: runId.trim(), attachmentId: r.id, provider: provider.trim() }))}>Modelle paylaş (onay penceresi açılır)</button>
            </li>
          ))}
        </ul>
      ))}
      <div><button type="button" disabled={busy || !RUN_ID.test(runId.trim())} onClick={act(() => task('attachment.delete', { run_id: runId.trim() }))}>Bu çalıştırmanın tüm eklerini sil</button></div>
    </section>
  );
}
