// Which instruction files exist and how they are labelled. The list itself comes from the shell (files.rs); this only orders and names it.
export type Instruction = { path: string; name: string; folder: string; scope: string; exists: boolean };

export const SCOPE_LABEL: Record<string, string> = { root: 'Proje kökü', subfolder: 'Alt klasör', user: 'Kullanıcı' };

export function scopeText(scope: string): string { return SCOPE_LABEL[scope] ?? scope; }

const RANK: Record<string, number> = { root: 0, subfolder: 1, user: 2 };
const USER_DIR: Record<string, string> = { 'CLAUDE.md': '.claude', 'AGENTS.md': '.codex' };

const slashed = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '');

/** A path a person can scan: relative to the project root, or `~/.claude/CLAUDE.md` for user-level files. */
export function displayPath(i: Instruction, root: string): string {
  if (i.scope === 'user') return `~/${USER_DIR[i.name] ?? '?'}/${i.name}`;
  const dir = slashed(i.folder);
  const base = slashed(root);
  if (dir.toLowerCase() === base.toLowerCase()) return i.name;
  if (dir.toLowerCase().startsWith(base.toLowerCase() + '/')) return `${dir.slice(base.length + 1)}/${i.name}`;
  return `${dir}/${i.name}`;
}

/** Root first, then subfolders by path, then the user-level files; duplicates (same path) keep the first. */
export function orderInstructions(list: Instruction[], root: string): Instruction[] {
  const seen = new Set<string>();
  return list
    .filter((i) => { const k = i.path.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; })
    .map((i, at) => ({ i, at, rank: RANK[i.scope] ?? 9, name: displayPath(i, root).toLowerCase() }))
    .sort((a, b) => a.rank - b.rank || (a.name < b.name ? -1 : a.name > b.name ? 1 : a.at - b.at))
    .map((x) => x.i);
}