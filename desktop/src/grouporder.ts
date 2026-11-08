// Pure ordering of the sidebar's project groups (no React): the person drags a group header up or down and the order is remembered.
/** Saved order first (only keys that still exist), then groups the person has not placed yet, in the order they appeared. */
export const orderGroups = (keys: string[], saved: string[]): string[] => [...saved.filter((k) => keys.includes(k)), ...keys.filter((k) => !saved.includes(k))];

/** Moves `from` so it sits where `to` is now. Unknown keys or the same key change nothing. */
export function moveGroup(order: string[], from: string, to: string): string[] {
  const a = order.indexOf(from), b = order.indexOf(to);
  if (a < 0 || b < 0 || a === b) return order;
  const out = order.filter((k) => k !== from);
  out.splice(b, 0, from);
  return out;
}

/** Keyboard version of the drag: one step up (-1) or down (+1). */
export function stepGroup(order: string[], key: string, dir: -1 | 1): string[] {
  const i = order.indexOf(key), j = i + dir;
  return i < 0 || j < 0 || j >= order.length ? order : moveGroup(order, key, order[j]);
}

/** Sessions shown per project in the sidebar, and how the "show more" button moves that number. */
export const PER_GROUP = 4;
export const nextShown = (shown: number, total: number): number => (shown >= total ? PER_GROUP : shown + PER_GROUP);
