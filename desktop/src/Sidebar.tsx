import { useState } from 'react';
import { type RouteId } from './shell';
import { Ico } from './icons';
import { Logo, Resizer } from './ui';
import { setConvStore, setLayout, useConvStore } from './sessionstore';
import { stateText } from './sessionlog';
import { PER_GROUP, moveGroup, nextShown, orderGroups, stepGroup } from './grouporder';
import { baseName } from './chatmodel';

/** Pages that live under Settings. The gear stays lit on all of them. */
export const SETTINGS_ROUTES: readonly RouteId[] = ['settings', 'tasks', 'inbox', 'projects', 'flow', 'team', 'usage', 'capabilities'];
const NONE = '__none';

/** Left menu: new chat, search, then the projects with their conversations (four at a time), and the product name with the settings button. */
export function Sidebar({ route, theme, toggleTheme, width, setWidth }: { route: RouteId; theme: 'light' | 'dark'; toggleTheme: () => void; width: number; setWidth: (n: number) => void }) {
  const conv = useConvStore();
  const onChat = route === 'sessions';
  const keys = [...new Set(conv.list.map((c) => c.root ?? NONE))];
  const order = orderGroups(keys, conv.groupOrder);
  const [drag, setDrag] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [sort, setSortState] = useState<'date' | 'name'>(() => { try { return localStorage.getItem('orch.sort') === 'name' ? 'name' : 'date'; } catch { return 'date'; } });
  const setSort = (v: 'date' | 'name') => { setSortState(v); setMenu(null); try { localStorage.setItem('orch.sort', v); } catch { /* storage unavailable */ } };
  const [menu, setMenu] = useState<string | null>(null);
  const [shown, setShown] = useState<Record<string, number>>({});
  const toggle = (k: string) => setLayout({ collapsed: conv.collapsed.includes(k) ? conv.collapsed.filter((x) => x !== k) : [...conv.collapsed, k] });
  return (
    <div className="concept sidewrap">
      <nav className="side" aria-label="Ana gezinme" data-tauri-drag-region>
        <a href="#/sessions" className="nav" onClick={() => setConvStore({ sel: 'new' })}><Ico n="plus" /><span>Yeni</span></a>
        <span className="nav mut3" aria-disabled="true" title="Arama sonraki sürümde"><Ico n="search" /><span>Ara</span></span>
        <div className="grouplist">
          {keys.length === 0 && <span className="nav sub mut3">Henüz sohbet yok</span>}
          {order.map((k) => {
            const open = !conv.collapsed.includes(k), name = k === NONE ? 'Diğer oturumlar' : baseName(k);
            const all = conv.list.filter((c) => (c.root ?? NONE) === k).sort((a, b) => (sort === 'name' ? a.title.localeCompare(b.title, 'tr') : b.at - a.at)), count = Math.min(shown[k] ?? PER_GROUP, all.length);
            return (
              <div key={k} className={`grp ${over === k && drag !== k ? 'over' : ''}`} onDragOver={(e) => { if (drag) { e.preventDefault(); setOver(k); } }}
                onDrop={(e) => { e.preventDefault(); if (drag) setLayout({ groupOrder: moveGroup(order, drag, k) }); setDrag(null); setOver(null); }}>
                <div className="grprow"><button type="button" className="grphead" draggable aria-expanded={open} title={k === NONE ? name : `${k} — sürükleyerek sırala; Alt+↑/↓`}
                  onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; setDrag(k); }} onDragEnd={() => { setDrag(null); setOver(null); }}
                  onKeyDown={(e) => { if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) { e.preventDefault(); setLayout({ groupOrder: stepGroup(order, k, e.key === 'ArrowUp' ? -1 : 1) }); } }}
                  onClick={() => toggle(k)}><span>{name}</span><span className={`chev ${open ? 'open' : ''}`}><Ico n="chevron" /></span></button><button type="button" className="gadd flt" aria-label="Sohbetleri sırala" aria-haspopup="menu" aria-expanded={menu === k} title="Sırala" onClick={() => setMenu(menu === k ? null : k)}><Ico n="sort" /></button>
                {menu === k && <div className="sortmenu" role="menu" onKeyDown={(e) => { if (e.key === 'Escape') setMenu(null); }}>
                  {([['date', 'Tarihe göre (yeni önce)'], ['name', 'Ada göre']] as const).map(([v, t]) => <button key={v} type="button" role="menuitemradio" aria-checked={sort === v} className="it" autoFocus={sort === v} onClick={() => setSort(v)}><span className="grow">{t}</span>{sort === v && <Ico n="check" />}</button>)}</div>}
                {k !== NONE && <button type="button" className="gadd"  aria-label={`${name} içinde yeni sohbet`} title="Bu projede yeni sohbet" onClick={() => { setConvStore({ sel: 'new', newRoot: k }); location.hash = '#/sessions'; }}><Ico n="plus" /></button>}</div>
                {open && all.slice(0, count).map((c) => (
                  <a key={c.id} href="#/sessions" className={`nav conv ${onChat && conv.sel === c.id ? 'on' : ''}`} title={`${c.title} — ${c.saved ? 'geçmiş' : stateText(c.state)}`} onClick={() => setConvStore({ sel: c.id })}>
                    {!c.saved && (c.state === 'running' || c.state === 'failed') && <span className={`dot ${c.state === 'running' ? 'run' : 'err'}`} />}<span className="ct">{c.title}</span></a>))}
                {open && all.length > PER_GROUP && (
                  <button type="button" className="nav more" onClick={() => setShown({ ...shown, [k]: nextShown(count, all.length) })}>{count >= all.length ? 'Daha az göster' : 'Daha fazla göster'}</button>)}
              </div>
            );
          })}
        </div>
        <div className="sp" />
        <div className="row sidefoot">
          <Logo size={22} /><span className="brand grow">RESPECTED</span>
          <button type="button" className="ib" onClick={toggleTheme} aria-label={theme === 'dark' ? 'Açık moda geç' : 'Koyu moda geç'} title={theme === 'dark' ? 'Açık moda geç' : 'Koyu moda geç'}><Ico n={theme === 'dark' ? 'sun' : 'moon'} /></button>
          <a href="#/settings" className={`ib ${SETTINGS_ROUTES.includes(route) ? 'on' : ''}`} aria-label="Ayarlar" title="Ayarlar" aria-current={route === 'settings' ? 'page' : undefined}><Ico n="gear" /></a>
        </div>
      </nav>
      <Resizer width={width} setWidth={setWidth} edge="right" label="Sol menü genişliği" />
    </div>
  );
}
