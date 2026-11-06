import test from 'node:test';
import assert from 'node:assert/strict';
import { moveFocus, toSvg, type DagView } from '../src/dag.ts';

const n = (id: string, layer: number, row: number, issues: string[] = []) => ({ id, phase: id.split('/')[0], name: id.split('/')[1], layer, row, issues });
const view: DagView = {
  valid: false, engine_message: 'Cycle detected', findings: [],
  nodes: [n('a/x', 0, 0), n('a/y', 0, 1), n('b/z<&>', 1, 0, ['cycle'])],
  edges: [{ from: 'a/x', to: 'b/z<&>', issue: true }, { from: 'a/y', to: 'b/z<&>', issue: false }],
};

test('keyboard navigation walks the grid, clamps at edges and supports Home/End', () => {
  assert.equal(moveFocus(view.nodes, 'a/x', 'ArrowDown'), 'a/y');
  assert.equal(moveFocus(view.nodes, 'a/y', 'ArrowDown'), null);
  assert.equal(moveFocus(view.nodes, 'a/y', 'ArrowRight'), 'b/z<&>'); // nearest row in the next layer
  assert.equal(moveFocus(view.nodes, 'a/x', 'ArrowLeft'), null);
  assert.equal(moveFocus(view.nodes, 'a/x', 'End'), 'b/z<&>');
  assert.equal(moveFocus(view.nodes, 'b/z<&>', 'Home'), 'a/x');
  assert.equal(moveFocus(view.nodes, 'zzz', 'ArrowDown'), 'a/x');
  assert.equal(moveFocus(view.nodes, 'a/x', 'q'), null);
  assert.equal(moveFocus([], 'a', 'Home'), null);
});

test('svg is deterministic, escapes text, highlights the failing node and edge', () => {
  const svg = toSvg(view);
  assert.equal(svg, toSvg({ ...view, nodes: [...view.nodes].reverse(), edges: [...view.edges].reverse() }));
  assert.ok(!svg.includes('<&>') && svg.includes('b/z&lt;&amp;&gt;'));
  assert.equal((svg.match(/class="node issue"/g) ?? []).length, 1);
  assert.equal((svg.match(/class="edge issue"/g) ?? []).length, 1);
  assert.match(svg, /aria-label="Plan geçersiz"/);
  assert.match(svg, /^<svg [^>]*width="\d+" height="\d+"/);
});

test('100 nodes render and stay navigable', () => {
  const big: DagView = { valid: true, engine_message: null, findings: [], edges: [],
    nodes: Array.from({ length: 100 }, (_, i) => n(`p${i % 12}/l${i}`, i % 12, Math.floor(i / 12))) };
  assert.equal((toSvg(big).match(/class="node"/g) ?? []).length, 100);
  let id = 'p0/l0', steps = 0;
  for (let k = 0; k < 20; k++) { const nx = moveFocus(big.nodes, id, 'ArrowRight'); if (!nx) break; id = nx; steps++; }
  assert.equal(steps, 11);
});
