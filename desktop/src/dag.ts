// Pure DAG view logic (no React): the engine's plan.view result is canonical; this only positions, navigates and prints it.
export interface DagNode { id: string; phase: string; name: string; layer: number; row: number; issues: string[] }
export interface DagEdge { from: string; to: string; issue: boolean }
export interface DagFinding { kind: string; nodes: string[]; edges: string[][]; message: string }
export interface DagView { valid: boolean; engine_message: string | null; nodes: DagNode[]; edges: DagEdge[]; findings: DagFinding[] }

export const CELL = { w: 180, h: 64, gapX: 48, gapY: 24, pad: 16 } as const;

export function position(n: Pick<DagNode, 'layer' | 'row'>) {
  return { x: CELL.pad + n.layer * (CELL.w + CELL.gapX), y: CELL.pad + n.row * (CELL.h + CELL.gapY) };
}

/** Arrow keys move between neighbouring cells (Left/Right = layer, Up/Down = row); Home/End = first/last. null = stay. */
export function moveFocus(nodes: DagNode[], currentId: string, key: string): string | null {
  const cur = nodes.find((n) => n.id === currentId);
  if (!cur) return nodes[0]?.id ?? null;
  const ordered = [...nodes].sort((a, b) => a.layer - b.layer || a.row - b.row || a.id.localeCompare(b.id));
  if (key === 'Home') return ordered[0].id;
  if (key === 'End') return ordered[ordered.length - 1].id;
  const dRow = key === 'ArrowDown' ? 1 : key === 'ArrowUp' ? -1 : 0;
  const dLayer = key === 'ArrowRight' ? 1 : key === 'ArrowLeft' ? -1 : 0;
  if (!dRow && !dLayer) return null;
  if (dRow) return nodes.find((n) => n.layer === cur.layer && n.row === cur.row + dRow)?.id ?? null;
  const next = nodes.filter((n) => n.layer === cur.layer + dLayer);
  if (!next.length) return null;
  return next.reduce((best, n) => (Math.abs(n.row - cur.row) < Math.abs(best.row - cur.row) ? n : best)).id; // nearest row
}

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

/** Deterministic SVG text: same engine result in, same bytes out (used as the snapshot; text is escaped, never HTML). */
export function toSvg(view: DagView): string {
  const maxL = Math.max(0, ...view.nodes.map((n) => n.layer));
  const maxR = Math.max(0, ...view.nodes.map((n) => n.row));
  const w = CELL.pad * 2 + (maxL + 1) * CELL.w + maxL * CELL.gapX;
  const h = CELL.pad * 2 + (maxR + 1) * CELL.h + maxR * CELL.gapY;
  const at = new Map(view.nodes.map((n) => [n.id, position(n)]));
  const edges = [...view.edges].sort((a, b) => (a.from + a.to).localeCompare(b.from + b.to)).map((e) => {
    const a = at.get(e.from), b = at.get(e.to);
    return a && b ? `<line class="${e.issue ? 'edge issue' : 'edge'}" x1="${a.x + CELL.w}" y1="${a.y + CELL.h / 2}" x2="${b.x}" y2="${b.y + CELL.h / 2}"/>` : '';
  });
  const nodes = [...view.nodes].sort((a, b) => a.id.localeCompare(b.id)).map((n) => {
    const p = position(n);
    const bad = n.issues.length > 0;
    return `<g class="${bad ? 'node issue' : 'node'}" data-id="${esc(n.id)}"><rect x="${p.x}" y="${p.y}" width="${CELL.w}" height="${CELL.h}" rx="6"/>` +
      `<text x="${p.x + 8}" y="${p.y + 24}">${esc(n.id)}</text>${bad ? `<text x="${p.x + 8}" y="${p.y + 44}">${esc(n.issues.join(', '))}</text>` : ''}</g>`;
  });
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" role="img" aria-label="${view.valid ? 'Plan geçerli' : 'Plan geçersiz'}">${edges.join('')}${nodes.join('')}</svg>`;
}
