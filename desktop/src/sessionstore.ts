import { useSyncExternalStore } from 'react';
/** Sohbet listesi sidebar'da, mesajlar sayfada: ikisi bu küçük depo üzerinden aynı seçimi paylaşır. */
export type ConvItem = { id: string; title: string; state: 'idle' | 'running' | 'failed' | 'ended'; root: string | null; at: number; saved: boolean };
export type ConvStore = { list: ConvItem[]; sel: string; groupOrder: string[]; collapsed: string[]; newRoot: string | null };

function loadList(key: string): string[] {
  try { const v = JSON.parse(localStorage.getItem(key) ?? '[]') as unknown; return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []; } catch { return []; }
}
let st: ConvStore = { list: [], sel: 'new', groupOrder: loadList('orch.group-order'), collapsed: loadList('orch.group-collapsed'), newRoot: null };
const subs = new Set<() => void>();
export const getConvStore = () => st;
export function setConvStore(p: Partial<ConvStore>): void {
  st = { ...st, ...p };
  subs.forEach((f) => f());
}
/** Sidebar layout the person chose (group order, collapsed groups). Remembered per machine; unreadable storage only means it is forgotten. */
export function setLayout(p: { groupOrder?: string[]; collapsed?: string[] }): void {
  try {
    if (p.groupOrder) localStorage.setItem('orch.group-order', JSON.stringify(p.groupOrder));
    if (p.collapsed) localStorage.setItem('orch.group-collapsed', JSON.stringify(p.collapsed));
  } catch { /* storage unavailable */ }
  setConvStore(p);
}
export const useConvStore = () => useSyncExternalStore((cb) => { subs.add(cb); return () => { subs.delete(cb); }; }, getConvStore);
