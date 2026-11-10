import { useEffect, useState, type ReactNode } from 'react';
import { Page } from './ui';
import { Ico } from './icons';
import { PreviewPanel } from './PreviewPanel';
import { EngineSettings } from './EngineSettings';
import type { RouteId } from './shell';

const GROUPS: { title: string; items: [RouteId, string][] }[] = [
  { title: 'Tercihler', items: [['settings', 'Genel']] },
  { title: 'Çalışma', items: [['tasks', 'Görevler'], ['inbox', 'Gelen kutusu'], ['projects', 'Projeler'], ['flow', 'Etkinlik']] },
  { title: 'Araçlar', items: [['team', 'Ajanlar ve ekipler'], ['capabilities', 'AI araçları'], ['usage', 'Bütçe ve başarı']] },
];

/** Settings as a pop-up over the page, not a page of its own: sections on the left (with a search box), the chosen section on the right. */
export function SettingsModal({ route, onClose, children }: { route: RouteId; onClose: () => void; children: ReactNode }) {
  const [q, setQ] = useState('');
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    addEventListener('keydown', on);
    return () => removeEventListener('keydown', on);
  }, [onClose]);
  const needle = q.trim().toLocaleLowerCase('tr');
  return (
    <div className="smodalbg" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="smodal concept" role="dialog" aria-modal="true" aria-label="Ayarlar">
        <div className="smh"><b className="grow">Ayarlar</b><button type="button" className="ib" onClick={onClose} aria-label="Ayarları kapat" title="Kapat"><Ico n="x" /></button></div>
        <div className="smb">
          <nav className="snav" aria-label="Ayarlar bölümleri">
            <label className="ssearch"><Ico n="search" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ara" aria-label="Ayarlarda ara" /></label>
            {GROUPS.map((g) => {
              const items = g.items.filter(([, t]) => !needle || t.toLocaleLowerCase('tr').includes(needle));
              return items.length === 0 ? null : (
                <div key={g.title}><div className="lab">{g.title}</div>
                  {items.map(([id, title]) => <a key={id} href={`#/${id}`} className={`nav ${route === id ? 'on' : ''}`} aria-current={route === id ? 'page' : undefined}><span>{title}</span></a>)}</div>
              );
            })}
          </nav>
          <div className="sbody">{children}</div>
        </div>
      </div>
    </div>
  );
}

/** "Genel": the things this app itself can change. Appearance is local to this window; the engine part is read-only status. */
export function General({ theme, toggleTheme, status }: { theme: 'light' | 'dark'; toggleTheme: () => void; status: string }) {
  return (
    <Page title="Genel" sub="Bu uygulamanın kendi ayarları">
      <div className="card"><div className="h">Görünüm</div><div className="b row">
        <span className="grow">Tema</span>
        <div className="toggle" role="radiogroup" aria-label="Tema">
          <button role="radio" aria-checked={theme === 'light'} className={theme === 'light' ? 'on' : ''} onClick={() => theme !== 'light' && toggleTheme()}>Açık</button>
          <button role="radio" aria-checked={theme === 'dark'} className={theme === 'dark' ? 'on' : ''} onClick={() => theme !== 'dark' && toggleTheme()}>Koyu</button>
        </div></div></div>
      <div className="card"><div className="h">Motor</div><div className="b row"><span className="grow">Durum</span><span role="status">{status}</span></div></div>
      <EngineSettings />
      <div className="card"><div className="b"><PreviewPanel /></div></div>
    </Page>
  );
}
