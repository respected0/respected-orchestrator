import { useEffect, useState, type ReactNode } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Ico } from './icons';
import { Resizer, useWidth } from './ui';
import { extOf, highlightLine } from './highlight';
import { Suggestions } from './Beta4Screens';
import { PreviewPanel } from './PreviewPanel';
import { TerminalPane } from './TerminalPane';
import { AgentTerminals } from './AgentTerminal';
import { baseName, compactNumber, filesOf, toolCount, type ToolListView, type Turn } from './chatmodel';
import { reasonText, stateText, type SessionView, type Usage } from './sessionlog';
import { bufferOf } from './terminal';
import type { Loaded } from './Chat';

export type Wide = 'terminal' | 'diff' | 'browser' | 'files';
export const WIDE_TITLE: Record<Wide, string> = { terminal: 'Terminal', diff: 'Değişiklikler', browser: 'Tarayıcı', files: 'Dosyalar' };

const row = (a: string, b: ReactNode, icon?: Parameters<typeof Ico>[0]['n']) => <div className="step">{icon && <Ico n={icon} />}<div className="grow">{a}</div><span className="mut" style={{ maxWidth: 190, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b}</span></div>;

/** The narrow session bar: environment, context, adapters, outputs. A section with no data is not drawn. */
export function SessionPane({ s, turns, usage, root, tools }: { s: SessionView | null; turns: Turn[]; usage: Usage | null; root: string | null; tools: Loaded<ToolListView>; close?: () => void }) {
  const files = filesOf(turns), calls = toolCount(turns);
  return (
    <aside className="rpanel concept" aria-label="Oturum çubuğu">
            <details open><summary>Ortam</summary>
        {root ? row('Proje klasörü', <span title={root}>{baseName(root)}</span>, 'folder') : <p className="mut">Proje klasörü seçilmedi.</p>}
        {s && row('Durum', stateText(s.state), 'list')}
        {s && row('Model', <span title={s.model}>{s.model.split('/').pop()}</span>, 'tools')}
        {s && row('Ajan', s.agent, 'users')}
        {s && s.retries > 0 && row('Yeniden deneme', s.retries)}
        {s?.last_state && row('Son tur sonucu', s.last_state)}
        {calls > 0 && row('Araç çağrısı', calls)}
        {s && s.state === 'failed' && !s.commands.retry.enabled && <p className="mut">{reasonText(s.commands.retry.reason)}</p>}
      </details>
      {usage && <details open><summary>Bağlam</summary><Tokens u={usage} /></details>}
      <details open><summary>Bağdaştırıcılar</summary>
        {tools.s === 'loading' && <p className="mut" role="status">Taranıyor…</p>}
        {tools.s === 'done' && tools.v.kind === 'error' && <p role="alert">{tools.v.text}</p>}
        {tools.s === 'done' && tools.v.kind === 'rows' && <>
          {tools.v.mcp.length === 0 ? <p className="mut">MCP sunucusu bulunamadı.</p> : tools.v.mcp.map((n) => <div key={n} className="step"><span className="av2" aria-hidden="true">{n.charAt(0).toUpperCase()}</span><span className="grow" title={n}>{n}</span></div>)}
          {tools.v.skills.length > 0 && <p className="mut">{tools.v.skills.length} beceri bulundu.</p>}
          <p className="mut">Diskte bulunanlardır; sohbet oturumu bunları açmaz.</p></>}
      </details>
      {files.changed.length > 0 && <details open><summary>Çıktılar ({files.changed.length})</summary>{files.changed.map((f) => <div key={f} className="step"><span className="mono" title={f}>{baseName(f)}</span></div>)}</details>}
      {files.read.length > 0 && <details><summary>Okunan dosyalar ({files.read.length})</summary>{files.read.map((f) => <div key={f} className="step"><span className="mono" title={f}>{baseName(f)}</span></div>)}</details>}
      <details><summary>Yetenek önerileri</summary><Suggestions /></details>
    </aside>
  );
}

const PARTS = [['input', 'Girdi', 'var(--info)'], ['output', 'Çıktı', 'var(--acc)'], ['reasoning', 'Akıl yürütme', 'var(--ok)'], ['cache_read', 'Önbellekten okunan', 'var(--warn)']] as const;
/** Where the reported tokens went: a bar and a legend. Shares are of the total the agent reported; its context window size is not reported, so there is no "used" percentage. */
function Tokens({ u }: { u: Usage }) {
  const total = PARTS.reduce((n, [k]) => n + u[k], 0) || 1;
  return (
    <>
      <div className="meter" role="img" aria-label="Token dağılımı">{PARTS.map(([k, , c]) => u[k] > 0 && <i key={k} style={{ width: `${(u[k] / total) * 100}%`, background: c }} />)}</div>
      {PARTS.filter(([k]) => u[k] > 0).map(([k, name, c]) => <div key={k} className="step"><span className="sq" style={{ background: c }} /><div className="grow">{name}</div><span className="mut">{compactNumber(u[k])}</span><span className="pc">%{((u[k] / total) * 100).toFixed(1).replace('.', ',')}</span></div>)}
      {row('Son adımın girdisi', u.last_input === null ? '—' : `${compactNumber(u.last_input)} token`)}
      {row('Maliyet', u.cost === null ? 'bildirilmedi' : u.cost)}
      <p className="mut">Yüzdeler, ajanın bildirdiği toplamın payıdır. Bağlam penceresi boyutu bildirilmediği için doluluk yüzdesi gösterilmez.</p>
    </>
  );
}

/** The wide pane: one of terminal, changes, browser or files, next to the session bar. */
export function WidePane({ kind, s, turns, root, lines, pickFolder, close }: { kind: Wide; s: SessionView | null; turns: Turn[]; root: string | null; lines: string[]; pickFolder: (start?: string) => Promise<string | null>; close: () => void }) {
  const [w, setW] = useWidth('orch.wpane-w', 560, 320, 1200);
  const [big, setBig] = useState(false);
  return (
    <>{!big && <Resizer width={w} setWidth={setW} edge="left" label={`${WIDE_TITLE[kind]} genişliği`} />}
    <aside className={`wpane concept ${kind} ${big ? 'big' : ''}`} aria-label={WIDE_TITLE[kind]} style={big ? undefined : { width: w }}>
      <div className="wh"><span className="grow">{WIDE_TITLE[kind]}</span><button className="ib" onClick={close} aria-label={`${WIDE_TITLE[kind]} bölmesini kapat`}><Ico n="x" /></button></div>
      <div className="wb">
        {kind === 'terminal' && <>
          {root ? <AgentTerminals root={root} /> : <p className="mut">Ajan terminali için önce bir proje klasörü seç.</p>}
          {s && <details><summary>Sohbet dökümü (düz metin)</summary><TerminalPane id={s.id} agent={`${s.agent} (${s.model})`} buffer={bufferOf(lines)} rows={24} /></details>}</>}
        {kind === 'diff' && <Changes turns={turns} />}
        {kind === 'browser' && <PreviewPanel />}
        {kind === 'files' && (root ? <Files root={root} pickFolder={pickFolder} big={big} toggleBig={() => setBig(!big)} close={close} /> : <p className="mut">Dosyaları görmek için önce bir proje klasörü seç.</p>)}
      </div>
    </aside></>
  );
}

function Changes({ turns }: { turns: Turn[] }) {
  const { changed } = filesOf(turns);
  if (changed.length === 0) return <p className="mut">Bu oturumda ajan hiçbir dosyayı değiştirmedi. Sohbet oturumlarında dosya değiştiren araçlar kapalıdır; değişiklikler görevler/kampanyalar üzerinden onay merkezine gelir.</p>;
  return <>{changed.map((f) => <div key={f} className="step"><span className="mono" title={f}>{f}</span></div>)}
    <p className="mut">Yalnız dosya adları listelenir; sohbet akışı yama içeriği taşımaz. Uygulama izni ayrı onay penceresindedir.</p></>;
}

type Entry = { name: string; dir: boolean };
type Listing = { kind: 'loading' } | { kind: 'ok'; entries: Entry[] } | { kind: 'error'; text: string };
type Doc = { text: string | null; error: string | null };
const join = (a: string, b: string) => `${a.replace(/[\\/]+$/, '')}${a.includes('\\') ? '\\' : '/'}${b}`;
const errText = (e: unknown) => (typeof e === 'string' ? e : 'Dosya görünümü kullanılamıyor.');
const MAX_LINES = 4000;
const rel = (root: string, path: string) => (path.startsWith(root) ? path.slice(root.length).replace(/^[\\/]+/, '') : path);

/** Files pane: open files as tabs, the path above the code, line numbers and colours, and the project tree on the right with a filter. */
function Files({ root, pickFolder, big, toggleBig, close: closePane }: { root: string; pickFolder: (start?: string) => Promise<string | null>; big: boolean; toggleBig: () => void; close: () => void }) {
  const [tw, setTw] = useWidth('orch.tree-w', 270, 180, 520);
  const [tree, setTree] = useState<Record<string, Listing>>({});
  const [tabs, setTabs] = useState<string[]>([]);
  const [pinned, setPinned] = useState<string[]>([]);
  const [cur, setCur] = useState<string | null>(null);
  const [docs, setDocs] = useState<Record<string, Doc>>({});
  const [q, setQ] = useState('');
  const load = (path: string) => {
    setTree((t) => ({ ...t, [path]: { kind: 'loading' } }));
    invoke<Entry[]>('list_dir', { path }).then((entries) => setTree((t) => ({ ...t, [path]: { kind: 'ok', entries } })), (e) => setTree((t) => ({ ...t, [path]: { kind: 'error', text: errText(e) } })));
  };
  useEffect(() => { if (!tree[root]) load(root); }, [root, !!tree[root]]); // eslint-disable-line
  const toggle = (path: string) => { if (tree[path]) setTree(({ [path]: _gone, ...rest }) => rest); else load(path); };
  const openFile = (path: string) => {
    setCur(path);
    // the open tab is a preview until pinned: opening another file replaces it, a pinned tab stays
    setTabs((t) => (t.includes(path) ? t : cur && t.includes(cur) && !pinned.includes(cur) ? t.map((x) => (x === cur ? path : x)) : [...t, path]));
    if (docs[path]?.text != null) return;
    setDocs((d) => ({ ...d, [path]: { text: null, error: null } }));
    invoke<string>('read_text_file', { path }).then((text) => setDocs((d) => ({ ...d, [path]: { text, error: null } })), (e) => setDocs((d) => ({ ...d, [path]: { text: null, error: errText(e) } })));
  };
  const close = (path: string) => {
    const rest = tabs.filter((t) => t !== path);
    setTabs(rest);
    setPinned((p) => p.filter((x) => x !== path));
    if (cur === path) setCur(rest[rest.length - 1] ?? null);
  };
  const filter = q.trim().toLowerCase();
  const node = (path: string): ReactNode => {
    const l = tree[path];
    if (!l || l.kind === 'loading') return <p className="mut" role="status">Yükleniyor…</p>;
    if (l.kind === 'error') return <div role="alert"><p>{l.text}</p><button className="btn sm" onClick={async () => { if (await pickFolder(root).catch(() => null)) setTree({}); }}>Klasörü yeniden seç</button></div>;
    const rows = filter ? l.entries.filter((e) => e.dir || e.name.toLowerCase().includes(filter)) : l.entries;
    if (rows.length === 0) return <p className="mut">{filter ? 'Eşleşme yok.' : 'Boş klasör.'}</p>;
    return rows.map((e) => {
      const p = join(path, e.name);
      return (
        <div key={p}>
          <button type="button" className={`row1 ${cur === p ? 'on' : ''}`} aria-expanded={e.dir ? !!tree[p] : undefined} onClick={() => (e.dir ? toggle(p) : openFile(p))}>
            {e.dir ? <span className={`chev ${tree[p] ? 'open' : ''}`}><Ico n="chevron" /></span> : <span className="chev" />}<Ico n={e.dir ? 'folder' : 'file'} /><span className="nm">{e.name}</span></button>
          {e.dir && tree[p] && <div className="kids">{node(p)}</div>}
        </div>
      );
    });
  };
  const doc = cur ? docs[cur] : null;
  return (
    <div className="files">
      <div className="viewer">
        <div className="tabs" role="tablist">
          {tabs.map((t) => (
            <span key={t} className={`tab ${cur === t ? 'on' : ''} ${pinned.includes(t) ? 'pin' : ''}`}>
              <button type="button" role="tab" aria-selected={cur === t} onClick={() => setCur(t)} title={t}>{baseName(t)}</button>
              <button type="button" className="x pinbtn" aria-pressed={pinned.includes(t)} aria-label={pinned.includes(t) ? `${baseName(t)} sabitlemesini kaldır` : `${baseName(t)} sekmesini sabitle`} title={pinned.includes(t) ? 'Sabitlemeyi kaldır' : 'Sabitle'} onClick={() => setPinned(pinned.includes(t) ? pinned.filter((x) => x !== t) : [...pinned, t])}><Ico n="pin" /></button>
              <button type="button" className="x" aria-label={`${baseName(t)} sekmesini kapat`} onClick={() => close(t)}><Ico n="x" /></button></span>))}
          <span className="sp" />
          <button type="button" className="ib" aria-pressed={big} aria-label={big ? 'Paneli küçült' : 'Paneli büyüt'} title={big ? 'Paneli küçült' : 'Paneli büyüt'} onClick={toggleBig}><Ico n={big ? 'shrink' : 'expand'} /></button>
          <button type="button" className="ib" aria-label="Dosyalar bölmesini kapat" title="Kapat" onClick={closePane}><Ico n="x" /></button>
        </div>
        {cur ? <>
          <div className="crumb mut" title={cur}>{[baseName(root), ...rel(root, cur).split(/[\\/]/)].join('  \\  ')}</div>
          {doc?.error ? <p role="alert" style={{ padding: 12 }}>{doc.error}</p> : !doc || doc.text === null ? <p className="mut" role="status" style={{ padding: 12 }}>Yükleniyor…</p> : <Code text={doc.text} path={cur} />}
        </> : <div className="empty" style={{ margin: 'auto' }}><Ico n="folder" /><p className="mut">Açık dosyalar burada görünür.</p><p className="mut">Ağaçtan bir dosya seç.</p></div>}
      </div>
      <Resizer width={tw} setWidth={setTw} edge="left" label="Dosya ağacı genişliği" />
      <div className="treecol" style={{ width: tw }}>
        <div className="filt"><Ico n="search" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtreleyin" aria-label="Dosya ara" />
          <button type="button" className="ib" title="Tüm klasörleri daralt" aria-label="Tüm klasörleri daralt" onClick={() => setTree((t) => (t[root] ? { [root]: t[root] } : {}))}><Ico n="chevron" /></button></div>
        <div role="tree" aria-label="Proje dosyaları" className="ftree">{node(root)}</div>
      </div>
    </div>
  );
}

function Code({ text, path }: { text: string; path: string }) {
  const ext = extOf(path);
  const lines = text.split('\n'), shown = lines.slice(0, MAX_LINES);
  return (
    <div className="code" tabIndex={0} aria-label={`${baseName(path)} içeriği`}>
      {shown.map((l, i) => (
        <div key={i} className="ln"><span className="no" aria-hidden="true">{i + 1}</span>
          <span className="tx">{highlightLine(l, ext).map((t, j) => <span key={j} className={`tk-${t.k}`}>{t.v}</span>)}{l === '' && ' '}</span></div>))}
      {lines.length > MAX_LINES && <p className="mut" style={{ padding: 8 }}>İlk {MAX_LINES} satır gösteriliyor.</p>}
    </div>
  );
}
