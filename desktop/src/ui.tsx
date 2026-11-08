import { useState, type PointerEvent as RPointerEvent, type ReactNode } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { Ico } from './icons';

const go = (r: string) => { location.hash = `#/${r}`; };

/** Chat / activity switch in the title bar. */
export function ModeToggle({ active }: { active: 'chat' | 'flow' }) {
  return (
    <div className="toggle" role="tablist" aria-label="Görünüm">
      <button role="tab" className={active === 'chat' ? 'on' : ''} aria-selected={active === 'chat'} onClick={() => go('sessions')}>Sohbet</button>
      <button role="tab" className={active === 'flow' ? 'on' : ''} aria-selected={active === 'flow'} onClick={() => go('flow')}>Etkinlik</button>
    </div>
  );
}

export function Modal({ title, onClose, children, foot }: { title: string; onClose: () => void; children: ReactNode; foot: ReactNode }) {
  return (
    <div className="modalbg" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} style={{ position: 'static', inset: 'auto', padding: 0 }}
        onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}>
        <div className="mh">{title}<span className="sp" /><button className="ib" onClick={onClose} aria-label="Kapat"><Ico n="x" /></button></div>
        <div className="mb">{children}</div>
        <div className="mf">{foot}</div>
      </div>
    </div>
  );
}

/** One page layout for every screen: title bar, optional actions, scrolling body. */
export function Page({ title, sub, actions, children }: { title: string; sub?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="concept">
      <div className="bar" data-tauri-drag-region><div className="grow row"><h1>{title}</h1>{sub && <span className="mut">{sub}</span>}</div>{actions}</div>
      <div className="scroll"><div className="page">{children}</div></div>
    </div>
  );
}

/** The three honest non-data states every board shares. */
export const Loading = ({ text = 'Yükleniyor…' }: { text?: string }) => <p className="mut" role="status">{text}</p>;
export const Failed = ({ text, hint, retry }: { text: string; hint?: string; retry?: () => void }) => (
  <div role="alert" className="empty"><p><b>{text}</b></p>{hint && <p className="mut">{hint}</p>}{retry && <button className="btn sm" onClick={retry}>Yeniden dene</button>}</div>
);
export const Empty = ({ title, hint }: { title: string; hint?: string }) => <div className="empty"><p><b>{title}</b></p>{hint && <p className="mut">{hint}</p>}</div>;

/** The window has no native title bar: these three buttons sit in the same row as the page's own tools. Closing goes through the shell's
 *  close handler, so a window with active runs still asks first. */
export function WindowControls() {
  const w = () => getCurrentWindow();
  const b = (label: string, onClick: () => void, d: string, cls = '') => (
    <button type="button" className={`wc ${cls}`} aria-label={label} title={label} onClick={() => void onClick()}>
      <svg viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: d }} /></button>
  );
  return (
    <div className="wcs">
      {b('Küçült', () => w().minimize(), '<path d="M6 12h12"/>')}
      {b('Büyüt / eski boyut', () => w().toggleMaximize(), '<rect x="6" y="6" width="12" height="12" rx="1.5"/>')}
      {b('Kapat', () => w().close(), '<path d="M6 6l12 12M18 6 6 18"/>', 'x')}
    </div>
  );
}

/** The product mark (docs/assets/logo.svg), drawn inline so nothing is fetched. */
export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg viewBox="0 0 256 256" width={size} height={size} role="img" aria-label="Respected Orchestrator"><rect x="1.5" y="1.5" width="253" height="253" rx="55" fill="#11161d" stroke="#243243" strokeWidth="3" />
      <path fill="#2d6bb8" d="M122 166 H176 L222 214 H168 Z" /><path fill="#4c9aff" fillRule="evenodd" d="M62 40 H150 A66 66 0 0 1 150 172 H108 V214 H62 Z M108 140 V102 A29 29 0 0 1 166 102 V140 Z" />
      <g fill="none" stroke="#f2f4f8" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"><path d="M137 138 V126 C137 116 120 116 120 106 V100 C120 90 137 92 137 82 M137 126 C137 116 154 116 154 106 V100 C154 90 137 92 137 82 M137 82 V76" /></g></svg>
  );
}

/** Hide the left menu, step back and forward through the pages visited. Always in the top-left corner, also while the menu is hidden. */
export function NavTools({ hidden, toggle }: { hidden: boolean; toggle: () => void }) {
  return (
    <div className="navtools" role="toolbar" aria-label="Gezinme">
      <button type="button" className="ib" onClick={toggle} aria-pressed={hidden} aria-label={hidden ? 'Sol menüyü göster' : 'Sol menüyü gizle'} title={hidden ? 'Sol menüyü göster' : 'Sol menüyü gizle'}><Ico n="sideL" /></button>
      <button type="button" className="ib" onClick={() => history.back()} aria-label="Geri" title="Geri"><Ico n="back" /></button>
      <button type="button" className="ib" onClick={() => history.forward()} aria-label="İleri" title="İleri"><Ico n="fwd" /></button>
    </div>
  );
}

/** A width the person can drag; remembered on this machine (unreadable storage only means it is forgotten). */
export function useWidth(key: string, def: number, min: number, max: number): [number, (n: number) => void] {
  const clamp = (n: number) => Math.round(Math.max(min, Math.min(Math.min(max, Math.max(min, innerWidth - 520)), n)));
  const [w, setW] = useState(() => { try { const v = Number(localStorage.getItem(key)); return v ? clamp(v) : def; } catch { return def; } });
  return [w, (n) => { const v = clamp(n); setW(v); try { localStorage.setItem(key, String(v)); } catch { /* storage unavailable */ } }];
}

/** Drag handle on the edge of a pane. `edge` is the side of the pane it sits on: dragging toward the pane's inside shrinks it. Arrow keys work too. */
export function Resizer({ width, setWidth, edge, label }: { width: number; setWidth: (n: number) => void; edge: 'left' | 'right'; label: string }) {
  const sign = edge === 'right' ? 1 : -1;
  const down = (e: RPointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const el = e.currentTarget, x0 = e.clientX, w0 = width;
    el.setPointerCapture(e.pointerId); el.classList.add('drag'); document.body.classList.add('resizing');
    const move = (m: PointerEvent) => setWidth(w0 + sign * (m.clientX - x0));
    const up = () => { el.classList.remove('drag'); document.body.classList.remove('resizing'); el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up); el.removeEventListener('pointercancel', up); };
    el.addEventListener('pointermove', move); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);
  };
  return <div className={`resizer edge-${edge}`} role="separator" aria-orientation="vertical" aria-label={label} aria-valuenow={width} tabIndex={0} onPointerDown={down}
    onKeyDown={(e) => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); setWidth(width + (e.key === 'ArrowRight' ? 1 : -1) * sign * 16); } }} />;
}
