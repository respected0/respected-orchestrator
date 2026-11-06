import { useEffect, useId, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { NO_FILTER, applyFilter, clients, inventoryView, scopeGroup, statusLabels, toggleFlag, warningText, type Filter, type InventoryView } from './inventory';

const FLAG_KEY = 'orch.inventory.falsePositives';

function loadFlags(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(FLAG_KEY) ?? '[]')); } catch { return new Set(); }
}
function saveFlags(flags: Set<string>) {
  try { localStorage.setItem(FLAG_KEY, JSON.stringify([...flags])); } catch { /* a viewer convenience only */ }
}

/** Read-only: lists what the installed clients already have. There is no button here that enables, installs, trusts or runs anything. */
export function Capabilities() {
  const [view, setView] = useState<InventoryView | { kind: 'loading' }>({ kind: 'loading' });
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const [flags, setFlags] = useState<Set<string>>(loadFlags);
  const id = useId();

  const load = () => {
    setView({ kind: 'loading' });
    invoke('capability_inventory', { projectRoot: null })
      .then((reply) => setView(inventoryView(reply)))
      .catch((e: { hint?: string }) => setView({ kind: 'error', text: 'Envanter okunamadı: motora ulaşılamadı.', hint: e?.hint ?? 'Yenile düğmesiyle tekrar deneyin.' }));
  };
  useEffect(load, []);

  if (view.kind === 'loading') return <p role="status">Yetenekler okunuyor…</p>;
  if (view.kind === 'error') return <div role="alert"><p>{view.text}</p><p>{view.hint}</p><button onClick={load}>Yenile</button></div>;

  const shown = applyFilter(view.rows, filter);
  const set = (patch: Partial<Filter>) => setFilter({ ...filter, ...patch });
  const flag = (cid: string) => { const next = toggleFlag(flags, cid); setFlags(next); saveFlags(next); };
  return (
    <section aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="sr-only">Yetenek envanteri</h2>
      <p>
        Bu liste <strong>yalnızca okunur</strong>: hiçbir şey etkinleştirilmez, kurulmaz veya çalıştırılmaz; sunuculara bağlanılmaz. Gizli değerler gösterilmez.
      </p>
      {view.approvalsError && <div role="alert"><p>{view.approvalsError}</p></div>}
      <p role="status">
        {view.counts.mcp} MCP sunucusu, {view.counts.skill} beceri · güvenilir: {view.counts.trusted} · doğrulanmış: {view.counts.verified} · gösterilen: {shown.length}
      </p>
      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Süzgeçler">
        <label>Ara <input type="search" aria-label="Ara" value={filter.query} onChange={(e) => set({ query: e.target.value })} /></label>
        <label>Tür
          <select aria-label="Tür" value={filter.kind} onChange={(e) => set({ kind: e.target.value as Filter['kind'] })}>
            <option value="all">Hepsi</option><option value="mcp">MCP</option><option value="skill">Beceri</option>
          </select>
        </label>
        <label>Kapsam
          <select aria-label="Kapsam" value={filter.scope} onChange={(e) => set({ scope: e.target.value as Filter['scope'] })}>
            <option value="all">Hepsi</option><option value="global">Genel</option><option value="project">Proje</option>
          </select>
        </label>
        <label>İstemci
          <select aria-label="İstemci" value={filter.client} onChange={(e) => set({ client: e.target.value })}>
            <option value="all">Hepsi</option>{clients(view.rows).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Göster
          <select aria-label="Göster" value={filter.only} onChange={(e) => set({ only: e.target.value as Filter['only'] })}>
            <option value="all">Hepsi</option><option value="warnings">Uyarılı</option><option value="not-installed">Kurulu olmayan</option><option value="trusted">Güvenilir</option>
          </select>
        </label>
        <button type="button" onClick={() => setFilter(NO_FILTER)}>Süzgeçleri temizle</button>
        <button type="button" onClick={load}>Yenile</button>
      </form>
      {shown.length === 0 ? <p>Süzgece uyan yetenek yok.</p> : (
        <table>
          <caption className="sr-only">MCP sunucuları ve beceriler</caption>
          <thead><tr><th scope="col">Ad</th><th scope="col">Tür</th><th scope="col">İstemci</th><th scope="col">Kapsam</th><th scope="col">Durumlar</th><th scope="col">Uyarılar</th></tr></thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.id}>
                <th scope="row">
                  {c.name}
                  <div className="path" title={c.origin.path}>{c.origin.path}</div>
                </th>
                <td>{c.kind === 'mcp' ? 'MCP' : 'Beceri'}</td>
                <td>{c.client}</td>
                <td>{scopeGroup(c) === 'global' ? 'Genel' : `Proje${c.project_path ? ` (${c.project_path})` : ''}`}</td>
                <td>
                  <ul className="statuses">
                    {statusLabels(c).map((s) => <li key={s.key} data-state={String(s.state)} title={s.reason}>{s.text}</li>)}
                  </ul>
                </td>
                <td>
                  {c.warnings.length === 0 ? '—' : (
                    <ul>
                      {c.warnings.map((w, i) => <li key={i} className={flags.has(c.id) ? 'dim' : undefined}>{warningText(w)}</li>)}
                    </ul>
                  )}
                  {c.warnings.length > 0 && (
                    <label className="flag"><input type="checkbox" aria-label={`${c.name}: yanlış alarm olarak işaretle (yalnızca not)`} checked={flags.has(c.id)} onChange={() => flag(c.id)} /> Yanlış alarm (yalnızca not; durumu değiştirmez)</label>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
