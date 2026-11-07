import { useState } from 'react';
import { type Layout, type TerminalBuffer, gridFor, planPaste } from './terminal';

const ROW = 18;
const VISIBLE = 40;

/** Draws plain text lines only (React escapes them); only VISIBLE rows exist in the DOM, however long the scrollback is. */
export function TerminalPane({ id, agent, buffer, onSend }: { id: string; agent: string; buffer: TerminalBuffer; onSend?: (text: string) => void }) {
  const [top, setTop] = useState(Math.max(0, buffer.length - VISIBLE));
  const [pending, setPending] = useState<string | null>(null);
  const rows = buffer.window(top, VISIBLE);
  return (
    <section aria-label={`Terminal: ${agent}`} className="pane">
      <h3>{agent}</h3>
      <div role="log" aria-live="off" tabIndex={0} aria-label={`${agent} çıktısı, ${buffer.length} satır`} style={{ height: VISIBLE * ROW, overflowY: 'auto' }}
        onScroll={(e) => setTop(Math.min(Math.floor(e.currentTarget.scrollTop / ROW), Math.max(0, buffer.length - VISIBLE)))}
        onPaste={(e) => {
          e.preventDefault();
          const plan = planPaste(e.clipboardData.getData('text'));
          if (!plan.ok) return;
          if (plan.needsConfirm) setPending(plan.text); else onSend?.(plan.text);
        }}>
        <div style={{ height: buffer.length * ROW, position: 'relative' }}>
          <pre style={{ position: 'absolute', top: top * ROW, margin: 0, lineHeight: `${ROW}px` }}>{rows.join('\n')}</pre>
        </div>
      </div>
      {pending !== null && (
        <div role="alertdialog" aria-modal="true" aria-label="Çok satırlı yapıştırma">
          <p>{pending.split('\n').length} satır yapıştırılacak. Her satır bir komut olarak çalışabilir.</p>
          <pre>{pending.slice(0, 500)}</pre>
          <button autoFocus onClick={() => setPending(null)}>Vazgeç</button>
          <button onClick={() => { onSend?.(pending); setPending(null); }}>Yine de yapıştır</button>
        </div>
      )}
      <span className="sr-only" data-pane={id} />
    </section>
  );
}

export function TerminalGrid({ layout, buffers }: { layout: Layout; buffers: Record<string, TerminalBuffer> }) {
  const { rows, cols } = gridFor(layout.panes.length);
  if (layout.panes.length === 0) return <p role="status">Açık terminal bölmesi yok. Desteklenmeyen ajanlar için bölme başlatılmaz.</p>;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${rows}, auto)`, gap: 8 }}>
      {layout.panes.map((p) => buffers[p.id] && <TerminalPane key={p.id} id={p.id} agent={p.agent} buffer={buffers[p.id]} />)}
    </div>
  );
}
