import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Modal } from './ui';
import { displayPath, orderInstructions, scopeText, type Instruction } from './instructionmodel';
import { inline, parseMarkdown, type Inline } from './markdown';

type Doc = { text: string | null }; // null: the file is not there (or cannot be read as text)
type Open = { item: Instruction; text: string; preview: boolean; changed: boolean; readOnly: boolean };

function Lines({ xs }: { xs: Inline[] }) {
  return <>{xs.map((x, i) => x.t === 'code' ? <code key={i}>{x.v}</code>
    : x.t === 'strong' ? <strong key={i}>{x.v}</strong>
      : x.t === 'em' ? <em key={i}>{x.v}</em>
        : x.t === 'link' ? <a key={i} href={x.href} target="_blank" rel="noreferrer">{x.v}</a>
          : <span key={i}>{x.v}</span>)}</>;
}

/** The same minimal Markdown as the rest of the app; raw HTML stays text because every node is a React element. */
function Preview({ text }: { text: string }) {
  return <div className="mdpreview">{parseMarkdown(text).map((b, i) => {
    if (b.t === 'h') return <div key={i} className={`mdh h${b.level}`} role="heading" aria-level={b.level}><Lines xs={inline(b.text)} /></div>;
    if (b.t === 'p') return <p key={i}><Lines xs={b.inlines} /></p>;
    if (b.t === 'list') {
      const items = b.items.map((it, n) => <li key={n}><Lines xs={it} /></li>);
      return b.ordered ? <ol key={i}>{items}</ol> : <ul key={i}>{items}</ul>;
    }
    if (b.t === 'code') return <pre key={i}><code>{b.text}</code></pre>;
    if (b.t === 'quote') return <blockquote key={i}><Lines xs={b.inlines} /></blockquote>;
    return <hr key={i} />;
  })}</div>;
}

const read = (i: Instruction) => i.scope === 'user'
  ? invoke<string>('read_user_instruction', { name: i.name })
  : invoke<string>('read_text_file', { path: i.path });

/** Every instruction file the agents may read for this project (shell-side discovery), shown with its scope. Project files are plain-text
 *  editable after a native confirmation; user-level files are read-only. Saving refuses a file that changed on disk behind the editor. */
export function Instructions({ root }: { root: string }) {
  const [items, setItems] = useState<Instruction[]>([]);
  const [docs, setDocs] = useState<Record<string, Doc>>({});
  const [open, setOpen] = useState<Open | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    let alive = true;
    invoke<Instruction[]>('discover_instruction_files', { folder: root }).then((found) => {
      if (!alive) return;
      const list = orderInstructions(found, root);
      setItems(list);
      list.forEach((i) => void read(i)
        .then((text) => { if (alive) setDocs((d) => ({ ...d, [i.path]: { text } })); }, () => { if (alive) setDocs((d) => ({ ...d, [i.path]: { text: null } })); }));
    }, (e: unknown) => { if (alive) setNote(typeof e === 'string' ? e : 'Talimat dosyaları listelenemedi.'); });
    return () => { alive = false; };
  }, [root]);
  useEffect(() => { setItems([]); setDocs({}); return load(); }, [load]);

  const start = (item: Instruction) => {
    setNote(null);
    const doc = docs[item.path];
    setOpen({ item, text: doc?.text ?? '', preview: (doc?.text ?? '') !== '', changed: false, readOnly: item.scope === 'user' });
  };

  const reload = async (o: Open) => {
    setBusy(true);
    try {
      const text = await read(o.item);
      setDocs((d) => ({ ...d, [o.item.path]: { text } }));
      setOpen({ ...o, text, preview: true, changed: false });
      setNote('Dosya yeniden okundu; düzenleme alanı diskteki sürümü gösteriyor.');
    } catch (e) { setNote(typeof e === 'string' ? e : 'Dosya yeniden okunamadı.'); }
    setBusy(false);
  };

  const save = async (force = false) => {
    if (!open || open.readOnly) return;
    setBusy(true);
    try {
      const doc = docs[open.item.path];
      const written = await invoke<boolean>('write_instruction_file', {
        folder: open.item.folder, name: open.item.name, text: open.text, expected: doc?.text ?? null, force,
      });
      if (written) {
        setNote(`${displayPath(open.item, root)} kaydedildi.`);
        setOpen(null);
        load();
      } else setNote('Onay verilmedi; dosya değişmedi.');
    } catch (e) {
      const text = typeof e === 'string' ? e : 'Dosya kaydedilemedi.';
      if (text.startsWith('FILE_CHANGED:')) {
        setOpen({ ...open, changed: true });
        setNote(text.slice('FILE_CHANGED:'.length).trim());
      } else setNote(text);
    }
    setBusy(false);
  };

  return (
    <>
      {items.map((item) => {
        const doc = docs[item.path];
        return (
          <div key={item.path} className="step">
            <span className="grow mono" title={item.path}>{displayPath(item, root)}</span>
            <span className="badge">{scopeText(item.scope)}</span>
            <span className="mut">{!doc ? '…' : doc.text === null ? 'yok' : `${doc.text.split('\n').length} satır`}</span>
            <button type="button" className="btn sm" disabled={!doc} onClick={() => start(item)}>{item.scope === 'user' ? 'Gör' : doc?.text === null ? 'Oluştur' : 'Düzenle'}</button>
          </div>
        );
      })}
      {items.length === 0 && !note && <p className="mut">Talimat dosyası aranıyor…</p>}
      <p className="mut">Ajanların kendi talimat dosyalarıdır; ajan her oturumda okur. Alt klasörler üç düzeye kadar taranır, kullanıcı dosyaları salt okunur.</p>
      {note && <p role="status">{note}</p>}
      {open && <Modal title={`${scopeText(open.item.scope)} · ${displayPath(open.item, root)}`} onClose={() => setOpen(null)}
        foot={<><span className="grow mut" role="status">{open.readOnly ? 'Kullanıcı düzeyindeki dosya buradan değiştirilmez.' : open.changed ? 'Dosya diskte değişmiş.' : 'Kaydederken ayrı bir onay penceresi açılır.'}</span>
          <button type="button" className="btn" onClick={() => setOpen(null)}>Vazgeç</button>
          {open.changed && !open.readOnly && <>
            <button type="button" className="btn" disabled={busy} onClick={() => void reload(open)}>Yeniden oku</button>
            <button type="button" className="btn" disabled={busy} onClick={() => void save(true)}>Yine de kaydet…</button>
          </>}
          {!open.changed && !open.readOnly && <button type="button" className="btn" disabled={busy || open.text === (docs[open.item.path]?.text ?? '')} onClick={() => void save()}>Kaydet…</button>}
        </>}>
        <div className="row" style={{ marginBottom: 8 }}>
          <span className="grow mono mut">{open.item.path}</span>
          {!open.readOnly && <button type="button" className="btn sm" onClick={() => setOpen({ ...open, preview: !open.preview })}>{open.preview ? 'Düzenle' : 'Önizleme'}</button>}
        </div>
        {open.preview || open.readOnly
          ? <Preview text={open.text} />
          : <textarea className="mono" aria-label={`${open.item.name} içeriği`} spellCheck={false} value={open.text} onChange={(e) => setOpen({ ...open, text: e.target.value })} style={{ width: '70vw', maxWidth: 900, height: '55vh' }} />}
      </Modal>}
    </>
  );
}