import { useState, type ReactNode } from 'react';
import { Ico } from './icons';
import { addPaths, baseName, compactNumber, filesOf, itemsOf, planOf, type ModelsView, type Todo, type ToolListView, type Turn } from './chatmodel';
import type { Usage } from './sessionlog';

/** What a loader reports: nothing yet, an answer, or why there is none. The composer draws each of these; none is drawn as success. */
export type Loaded<T> = { s: 'loading' } | { s: 'done'; v: T };

type Pop = null | 'model' | 'ctx' | 'tools' | 'attach';
const IcoMini = ({ d }: { d: string }) => <svg viewBox="0 0 24 24" aria-hidden="true" style={{ width: 13, height: 13 }} dangerouslySetInnerHTML={{ __html: d }} />;
const Svg = ({ d }: { d: string }) => <svg viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: d }} />;
const P = {
  ctx: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16"/>',
  tools: '<path d="M14 6l4 4-8 8H6v-4zM13 7l4 4"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  shot: '<path d="M4 8V5h3M17 5h3v3M20 16v3h-3M7 19H4v-3"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  send: '<path d="M5 12l14-7-5 14-2-6z"/>',
  enter: '<path d="M20 5v7a3 3 0 0 1-3 3H5M9 11l-4 4 4 4"/>',
  clip: '<path d="M12 5v14M5 12h14"/>',
};

export type ComposerProps = {
  value: string; onChange: (v: string) => void; onSend: () => void; canSend: boolean; disabled?: boolean; placeholder: string;
  onVoice: () => void; onShot: () => void;
  /** The model shown on the chip. `onPickModel` only exists before a session starts: the engine cannot change a running session's model. */
  model: string; models: Loaded<ModelsView>; onPickModel?: (id: string) => void;
  usage: Usage | null; // the engine's totals for this conversation
  tools: Loaded<ToolListView>;
  attachments: string[]; setAttachments: (a: string[]) => void;
  pickFiles: () => Promise<string[]>; pickFolder: () => Promise<string | null>;
  /** Extra chip(s) before the model chip (the new-chat screen puts the project there). */
  lead?: ReactNode;
  /** Present only while a turn runs: stops it. Replaces send and the microphone. */
  onStop?: () => void;
  children?: ReactNode;
};

export function Composer(p: ComposerProps) {
  const [pop, setPop] = useState<Pop>(null);
  const [filter, setFilter] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const toggle = (x: Pop) => setPop(pop === x ? null : x);
  const attach = async (pick: () => Promise<string[] | string | null>) => {
    setPop(null);
    try {
      const got = await pick();
      const paths = Array.isArray(got) ? got : got ? [got] : [];
      if (paths.length) p.setAttachments(addPaths(p.attachments, paths));
      setProblem(null);
    } catch { setProblem('Dosya seçici açılamadı.'); }
  };
  const ids = p.models.s === 'done' && p.models.v.kind === 'models' ? p.models.v.ids.filter((id) => id.toLowerCase().includes(filter.trim().toLowerCase())) : [];
  const u = p.usage;
  const popBody = {
    model: <>
      <div className="lab" style={{ paddingTop: 4 }}>Model {p.onPickModel ? '' : '(bu oturumda sabit)'}</div>
      {p.models.s === 'loading' && <div className="mut" role="status" style={{ padding: '4px 9px' }}>Model listesi yükleniyor…</div>}
      {p.models.s === 'done' && p.models.v.kind === 'error' && <div role="alert" style={{ padding: '4px 9px' }}>{p.models.v.text}</div>}
      {p.models.s === 'done' && p.models.v.kind === 'empty' && <div className="mut" style={{ padding: '4px 9px' }}>Ajan hiç model bildirmedi.</div>}
      {p.models.s === 'done' && p.models.v.kind === 'models' && <>
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Ara…" aria-label="Model ara" style={{ margin: '0 9px 6px', width: 'calc(100% - 18px)' }} />
        <div style={{ maxHeight: 260, overflow: 'auto' }}>
          {ids.slice(0, 100).map((id) => <button key={id} className={`it ${id === p.model ? 'on' : ''}`} disabled={!p.onPickModel} onClick={() => { p.onPickModel?.(id); setPop(null); }}><div className="mono">{id}</div></button>)}
          {ids.length === 0 && <div className="mut" style={{ padding: '4px 9px' }}>Eşleşen model yok.</div>}
        </div></>}
      <div className="mut" style={{ padding: '6px 9px', fontSize: 12 }}>Seçili: <span className="mono">{p.model || '—'}</span></div></>,
    ctx: u && <>
      <div className="lab" style={{ paddingTop: 4 }}>Token kullanımı (ajanın bildirdiği)</div>
      {[['Son adımın girdisi', u.last_input === null ? '—' : String(u.last_input)], ['Toplam girdi', String(u.input)], ['Toplam çıktı', String(u.output)], ['Akıl yürütme', String(u.reasoning)], ['Önbellekten okunan', String(u.cache_read)], ['Maliyet', u.cost === null ? 'bildirilmedi' : String(u.cost)], ['Adım sayısı', String(u.steps)]]
        .map(([a, b]) => <div key={a} className="it"><div className="grow">{a}</div><span className="mut mono">{b}</span></div>)}
      <div className="mut" style={{ padding: '6px 9px', fontSize: 12 }}>Ajan bağlam penceresinin boyutunu bildirmez; bu yüzden yüzde gösterilmez.</div></>,
    tools: <>
      {p.tools.s === 'loading' && <div className="mut" role="status" style={{ padding: '4px 9px' }}>Araçlar taranıyor…</div>}
      {p.tools.s === 'done' && p.tools.v.kind === 'error' && <div role="alert" style={{ padding: '4px 9px' }}>{p.tools.v.text}</div>}
      {p.tools.s === 'done' && p.tools.v.kind === 'rows' && <>
        <div className="lab" style={{ paddingTop: 4 }}>Bulunan MCP sunucuları ({p.tools.v.mcp.length})</div>
        {p.tools.v.mcp.length === 0 && <div className="mut" style={{ padding: '2px 9px' }}>Bulunamadı.</div>}
        {p.tools.v.mcp.slice(0, 30).map((n) => <div key={n} className="it"><div className="mono">{n}</div></div>)}
        <div className="lab">Bulunan beceriler ({p.tools.v.skills.length})</div>
        {p.tools.v.skills.slice(0, 15).map((n) => <div key={n} className="it"><div className="mono">{n}</div></div>)}
        {p.tools.v.skills.length > 15 && <div className="mut" style={{ padding: '2px 9px' }}>… ve {p.tools.v.skills.length - 15} tane daha</div>}</>}
      <hr /><div className="mut" style={{ padding: '4px 9px', fontSize: 12 }}>Bu liste diskte bulunanlardır; sohbet oturumu bunlardan hiçbirini açmaz. Komut çalıştırma ve dosya değiştirme sohbette kapalıdır.</div>
      <button className="it" onClick={() => { location.hash = '#/capabilities'; setPop(null); }}><div>Ayrıntılar: MCP ve beceriler</div></button></>,
    attach: <>
      <button className="it" onClick={() => void attach(p.pickFiles)}><Ico n="file" /><div>Dosya ekle</div></button>
      <button className="it" onClick={() => void attach(p.pickFolder)}><Ico n="folder" /><div>Klasör ekle</div></button>
      <button className="it" onClick={() => { setPop(null); p.onShot(); }}><Svg d={P.shot} /><div>Ekran görüntüsü al</div></button></>,
  };
  const toolsLabel = p.tools.s === 'loading' ? 'Araçlar…' : p.tools.v.kind === 'error' ? 'Araçlar ✕' : `${p.tools.v.mcp.length} MCP`;
  const near = pop === 'attach';
  const grow = (el: HTMLTextAreaElement) => { el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 200)}px`; };
  return (
    <div className="comp" style={{ position: 'relative' }}>
      {pop && popBody[pop] && <div className="pop" role="menu" style={{ position: 'absolute', bottom: 'calc(100% - 4px)', left: near ? 'max(24px, calc(50% - 384px))' : 'auto', right: near ? 'auto' : 'max(24px, calc(50% - 384px))', zIndex: 20 }}
        onKeyDown={(e) => { if (e.key === 'Escape') setPop(null); }}>{popBody[pop]}</div>}
      <div className="compbox">
        {p.children}
        {p.attachments.length > 0 && <div className="row atts" aria-label="Ekler">
          {p.attachments.map((a) => <span key={a} className="chip" title={a}><Ico n="file" /> {baseName(a)}
            <button type="button" className="ib" aria-label={`${baseName(a)} ekini kaldır`} onClick={() => p.setAttachments(p.attachments.filter((x) => x !== a))}><Ico n="x" /></button></span>)}</div>}
        <div className="pill">
          <button type="button" className="ib" title="Ekle" aria-label="Ekle" aria-haspopup="menu" aria-expanded={pop === 'attach'} onClick={() => toggle('attach')}><Svg d={P.clip} /></button>
          <textarea rows={1} value={p.value} disabled={p.disabled} placeholder={p.placeholder} aria-label="Mesaj" onChange={(e) => { p.onChange(e.target.value); grow(e.target); }}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (p.canSend) p.onSend(); } }} />
          {p.onStop ? <button type="button" className="send" aria-label="Turu durdur" title="Turu durdur" onClick={p.onStop}><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none" /></svg></button>
            : <>{p.value.trim() && <button type="button" className="ib sendk" aria-label="Gönder" title="Gönder" disabled={!p.canSend} onClick={p.onSend}><Svg d={P.enter} /></button>}
              <button type="button" className="ib" title="Bas-konuş" aria-label="Sesle görev ver" onClick={p.onVoice}><Svg d={P.mic} /></button></>}
        </div>
      </div>
      {problem && <p role="alert" className="cprob">{problem}</p>}
      <div className="below">
        {p.lead}
        <span className="sp" />
        {u && <button type="button" className="chip flat" title="Token kullanımı" onClick={() => toggle('ctx')}>{compactNumber(u.last_input ?? u.input)} token</button>}
        <button type="button" className="chip flat" onClick={() => toggle('tools')}>{toolsLabel}</button>
        <button type="button" className="chip flat" aria-haspopup="menu" onClick={() => toggle('model')}>{p.model ? p.model.split('/').pop() : 'Model seç'} <IcoMini d={P.down} /></button>
      </div>
    </div>
  );
}

/* ---------- konuşma: yalnızca session.events'ten türeyen öğeler ---------- */
const todoMark = (s: string): string => (s === 'completed' ? '✓' : s === 'in_progress' ? '…' : '');

function PlanCard({ todos }: { todos: Todo[] }) {
  return (
    <div className="card"><div className="h"><Ico n="list" /> Ajanın planı <span className="mut">({todos.filter((t) => t.status === 'completed').length}/{todos.length})</span></div><div className="b">
      {todos.map((t, i) => <div key={i} className="step"><span className={`ic ${t.status === 'completed' ? 'ok' : ''}`}>{todoMark(t.status)}</span><div className="grow">{t.content}</div><span className="mut">{t.status}</span></div>)}</div></div>
  );
}

function ChangeCard({ files }: { files: string[] }) {
  return (
    <div className="card"><div className="h"><Ico n="file" /> Değişen dosyalar ({files.length})</div><div className="b">
      {files.map((f) => <div key={f} className="step"><div className="grow mono">{f}</div></div>)}
      <p className="mut">Değişiklik projeye henüz uygulanmış sayılmaz; uygulama izni ayrı onay penceresindedir.</p></div></div>
  );
}

export function ChatThread({ turns, running }: { turns: Turn[]; running: boolean }) {
  const items = itemsOf(turns), plan = planOf(turns), changed = filesOf(turns).changed;
  return (
    <>
      {items.map((m, i) => m.t === 'user' ? <div key={i} className="m user"><pre>{m.text}</pre></div>
        : m.t === 'agent' ? <div key={i} className="m agent"><pre>{m.text}</pre></div>
        : m.t === 'tool' ? <div key={i} className="tool"><span className="mono">{m.tool}{m.detail ? ` · ${m.detail}` : ''} ({m.status})</span></div>
        : <div key={i} className="m" role={m.t === 'error' ? 'alert' : undefined}><pre>{m.t === 'error' ? `[hata] ${m.text}` : m.text}</pre></div>)}
      {plan && <PlanCard todos={plan} />}
      {changed.length > 0 && <ChangeCard files={changed} />}
      {running && <p role="status" className="mut">Ajan çalışıyor…</p>}
    </>
  );
}
