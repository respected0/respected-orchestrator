import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Modal } from './ui';
import { childPath } from './chatmodel';

const FILES = ['AGENTS.md', 'CLAUDE.md'] as const;
type Doc = { text: string | null }; // null: the file is not there (or cannot be read as text)

/** The project's instruction files (the agents' own: AGENTS.md, CLAUDE.md), shown and edited as plain text. Saving asks for a confirmation
 *  in a separate system dialog; nothing else in the project can be written from this app. */
export function Instructions({ root }: { root: string }) {
  const [docs, setDocs] = useState<Record<string, Doc>>({});
  const [open, setOpen] = useState<null | { name: string; text: string }>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    FILES.forEach((name) => {
      invoke<string>('read_text_file', { path: childPath(root, name) }).then((text) => setDocs((d) => ({ ...d, [name]: { text } })), () => setDocs((d) => ({ ...d, [name]: { text: null } })));
    });
  }, [root]);
  useEffect(() => { setDocs({}); load(); }, [load]);
  const save = async () => {
    if (!open) return;
    setBusy(true);
    try {
      const written = await invoke<boolean>('write_instruction_file', { folder: root, name: open.name, text: open.text });
      setNote(written ? `${open.name} kaydedildi.` : 'Onay verilmedi; dosya değişmedi.');
      if (written) { setOpen(null); load(); }
    } catch (e) { setNote(typeof e === 'string' ? e : 'Dosya kaydedilemedi.'); }
    setBusy(false);
  };
  return (
    <>
      {FILES.map((name) => {
        const doc = docs[name];
        return (
          <div key={name} className="step"><span className="grow mono">{name}</span>
            <span className="mut">{!doc ? '…' : doc.text === null ? 'yok' : `${doc.text.split('\n').length} satır`}</span>
            <button type="button" className="btn sm" disabled={!doc} onClick={() => { setNote(null); setOpen({ name, text: doc?.text ?? '' }); }}>{doc?.text === null ? 'Oluştur' : 'Düzenle'}</button></div>
        );
      })}
      <p className="mut">Ajanların kendi talimat dosyalarıdır; ajan her oturumda okur.</p>
      {note && !open && <p role="status">{note}</p>}
      {open && <Modal title={`${open.name} · ${root}`} onClose={() => setOpen(null)}
        foot={<><span className="grow mut" role="status">{note ?? 'Kaydederken ayrı bir onay penceresi açılır.'}</span><button type="button" className="btn" onClick={() => setOpen(null)}>Vazgeç</button>
          <button type="button" className="btn" disabled={busy || open.text === (docs[open.name]?.text ?? '')} onClick={() => void save()}>Kaydet…</button></>}>
        <textarea className="mono" aria-label={`${open.name} içeriği`} spellCheck={false} value={open.text} onChange={(e) => setOpen({ ...open, text: e.target.value })} style={{ width: '70vw', maxWidth: 900, height: '55vh' }} />
      </Modal>}
    </>
  );
}
