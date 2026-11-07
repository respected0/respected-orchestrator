// Pure shell logic (no React, no Tauri) so it can be tested under `node --test`.
export const ROUTES = [
  { id: 'projects', label: 'Projeler', empty: 'Henüz proje yok. İlk projenizi başlattığınızda burada görünür.' },
  { id: 'runs', label: 'Çalıştırmalar', empty: 'Henüz çalıştırma yok.' },
  { id: 'reviews', label: 'İncelemeler', empty: 'İncelenecek bir şey yok.' },
  { id: 'agents', label: 'Ajanlar', empty: 'Ajan bulunamadı. Kurulu yapay zekâ araçları burada listelenecek.' },
  { id: 'sessions', label: 'Oturumlar', empty: 'Açık sohbet oturumu yok. Bir ajanla oturum başlatınca burada görünür.' },
  { id: 'capabilities', label: 'Yetenekler', empty: 'Kurulu istemcilerde MCP sunucusu veya beceri bulunamadı. Bulununca burada yalnızca okunur olarak listelenir.' },
  { id: 'settings', label: 'Ayarlar', empty: 'Ayarlar sonraki sürümde bu ekrandan yönetilecek.' },
] as const;
export type RouteId = (typeof ROUTES)[number]['id'];

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
  return (ROUTES.find((r) => r.id === id)?.id ?? 'projects') as RouteId;
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
