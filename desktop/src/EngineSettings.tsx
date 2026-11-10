import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { changesOf, draftOf, outcomeText, type Draft, type Field, type FieldError, type Outcome, type Stored } from './settingsform';

type Reply<T> = { ok: boolean; result: T; error: { message?: string } | null };
const read = <T,>(cmd: string): Promise<Reply<T>> => invoke('read_call', { cmd, payload: {} });

/** The engine's settings, drawn from its own schema. Saving only asks: the engine checks the values and the person confirms the change in a
 *  separate system dialog (several of these settings are consent switches the app window must not be able to flip by itself). */
export function EngineSettings() {
  const [fields, setFields] = useState<Field[] | null>(null);
  const [stored, setStored] = useState<Stored>({});
  const [draft, setDraft] = useState<Draft>({});
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [schema, back] = await Promise.all([read<{ fields: Field[] }>('settings.schema'), read<{ settings: Stored }>('settings.readback')]);
      if (!schema.ok || !back.ok) { setNote(`Ayarlar okunamadı: ${(schema.error ?? back.error)?.message ?? 'bilinmeyen hata'}`); return; }
      setFields(schema.result.fields); setStored(back.result.settings); setDraft(draftOf(schema.result.fields, back.result.settings));
    } catch { setNote('Motora ulaşılamadı.'); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (!fields) return <div className="card"><div className="h">Motor ayarları</div><div className="b">{note ? <p role="alert">{note}</p> : <p role="status" className="mut">Yükleniyor…</p>}</div></div>;
  const pending = changesOf(fields, stored, draft);
  const count = Object.keys(pending.changes).length;
  const shown = [...pending.errors, ...errors];
  const save = async () => {
    setBusy(true); setErrors([]);
    try {
      const o = await invoke<Outcome>('settings_request', { changes: pending.changes });
      setNote(outcomeText(o)); setErrors(o.errors ?? []);
      if (o.applied) await load();
    } catch (e) { setNote(`Kaydedilemedi: ${typeof e === 'string' ? e.slice(0, 200) : 'motora ulaşılamadı'}`); }
    setBusy(false);
  };
  const set = (key: string, v: string | boolean) => { setDraft({ ...draft, [key]: v }); setNote(null); };
  return (
    <div className="card"><div className="h">Motor ayarları</div><div className="b">
      {fields.map((f) => {
        const id = `set-${f.key}`, v = draft[f.key], bad = shown.find((e) => e.key === f.key);
        return (
          <div key={f.key} className="setrow">
            <label htmlFor={id} className="grow"><b>{f.label}</b>{f.help && <div className="mut">{f.help}</div>}
              {bad && <div role="alert">{bad.message}</div>}</label>
            {f.type === 'boolean' ? <input id={id} type="checkbox" checked={v === true} onChange={(e) => set(f.key, e.target.checked)} />
              : f.type === 'enum' ? <select id={id} value={String(v ?? '')} onChange={(e) => set(f.key, e.target.value)}>{(f.enum ?? []).map((o) => <option key={o} value={o}>{o}</option>)}</select>
              : <input id={id} type={f.secret ? 'password' : 'text'} inputMode={f.type === 'integer' ? 'numeric' : undefined} value={String(v ?? '')} autoComplete="off" spellCheck={false}
                  placeholder={f.secret ? (stored[f.key] ? 'kayıtlı; değiştirmek için yazın' : 'kayıtlı değil') : ''} onChange={(e) => set(f.key, e.target.value)} />}
          </div>
        );
      })}
      <div className="row" style={{ gap: 8, marginTop: 12 }}>
        <span className="grow mut" role="status">{note ?? (count ? `${count} ayar değişecek; kaydederken ayrı bir onay penceresi açılır.` : 'Değişiklik yok.')}</span>
        <button type="button" className="btn sm" disabled={busy || count === 0} onClick={() => setDraft(draftOf(fields, stored))}>Geri al</button>
        <button type="button" className="btn sm" disabled={busy || count === 0 || pending.errors.length > 0} onClick={() => void save()}>Kaydet…</button>
      </div>
    </div></div>
  );
}
