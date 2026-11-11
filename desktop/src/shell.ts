// Pure shell logic (no React, no Tauri) so it can be tested under `node --test`.
export const ROUTES = [
  { id: 'sessions', group: 'work', label: 'Sohbet', empty: 'Açık sohbet oturumu yok. Bir ajanla oturum başlatınca burada görünür.' },
  { id: 'inbox', group: 'work', label: 'Gelen kutusu', empty: 'Dikkat isteyen bir şey yok.' },
  { id: 'flow', group: 'work', label: 'Etkinlik', empty: 'Henüz kayıtlı olay yok.' },
  { id: 'tasks', group: 'work', label: 'Görevler', empty: 'Henüz görev yok.' },
  { id: 'projects', group: 'work', label: 'Projeler', empty: 'Henüz proje yok. İlk projenizi başlattığınızda burada görünür.' },
  { id: 'team', group: 'tools', label: 'Ajanlar ve ekipler', empty: 'Takım bilgisi okunuyor.' },
  { id: 'capabilities', group: 'tools', label: 'AI araçları', empty: 'Kurulu istemcilerde MCP sunucusu veya beceri bulunamadı. Bulununca burada yalnızca okunur olarak listelenir.' },
  { id: 'usage', group: 'tools', label: 'Bütçe ve başarı', empty: 'Kullanım okunuyor.' },
  { id: 'settings', group: 'tools', label: 'Ayarlar', empty: 'Ayarlar sonraki sürümde bu ekrandan yönetilecek.' },
] as const;
export type RouteId = (typeof ROUTES)[number]['id'];

/** Real bindings only; the palette lists these and each route. */
export const SHORTCUTS = [
  { keys: 'Ctrl+/', label: 'Kısayollar ve komut paleti' },
  { keys: 'Ctrl+B', label: 'Kenar çubuğunu göster/gizle' },
  { keys: 'Ctrl+1…9', label: 'Çalışma alanına git' },
  { keys: 'Esc', label: 'Açık pencereyi kapat' },
] as const;

/** Routes whose label matches the query, in nav order; empty query lists all. */
export function paletteRoutes(query: string): (typeof ROUTES)[number][] {
  const q = query.trim().toLocaleLowerCase('tr');
  return ROUTES.filter((r) => !q || r.label.toLocaleLowerCase('tr').includes(q));
}

/** Ctrl+digit maps to the nav order; out-of-range and 0 give null. */
export function shortcutRoute(key: string): RouteId | null {
  const n = Number(key);
  return Number.isInteger(n) && n >= 1 && n <= ROUTES.length ? ROUTES[n - 1].id : null;
}

export type EngineState =
  | { phase: 'loading' }
  | { phase: 'ready'; version: string; healthy: boolean }
  | { phase: 'problem'; kind: string; hint: string };

export type ScreenView =
  | { kind: 'loading'; text: string }
  | { kind: 'error'; text: string; hint: string }
  | { kind: 'empty'; text: string };

/** Never shows a success-looking screen unless the engine answered healthy. */
export function screenView(route: RouteId, engine: EngineState): ScreenView {
  if (engine.phase === 'loading') return { kind: 'loading', text: 'Motor aranıyor…' };
  if (engine.phase === 'problem') return { kind: 'error', text: `Motora bağlanılamadı (${engine.kind}).`, hint: engine.hint };
  if (!engine.healthy) return { kind: 'error', text: 'Motor çalışıyor ama sağlıklı değil.', hint: 'Onarım için kurucuyu yeniden çalıştırın.' };
  return { kind: 'empty', text: ROUTES.find((r) => r.id === route)!.empty };
}

export function routeFromHash(hash: string): RouteId {
  const id = hash.replace(/^#\/?/, '');
  return (ROUTES.find((r) => r.id === id)?.id ?? 'sessions') as RouteId;
}

/** Keyboard order for the nav: ArrowUp/ArrowDown wrap, Home/End jump. */
export function nextRoute(current: RouteId, key: string): RouteId | null {
  const i = ROUTES.findIndex((r) => r.id === current);
  const n = ROUTES.length;
  const j = key === 'ArrowDown' ? (i + 1) % n : key === 'ArrowUp' ? (i + n - 1) % n : key === 'Home' ? 0 : key === 'End' ? n - 1 : -1;
  return j < 0 ? null : ROUTES[j].id;
}

/** Closing the window never stops work: runs are detached engine processes. With work active the user is told first. */
export type CloseAction = 'close-window' | 'quit-app';
export type CloseDecision = { allow: true } | { allow: false; message: string; confirm: string; cancel: string };
export function closeDecision(_action: CloseAction, activeRuns: number): CloseDecision {
  if (activeRuns <= 0) return { allow: true };
  return {
    allow: false,
    message: `${activeRuns} çalıştırma sürüyor. Pencereyi kapatmak bunları durdurmaz; arka planda devam ederler.`,
    confirm: 'Yine de kapat',
    cancel: 'Açık kal',
  };
}
