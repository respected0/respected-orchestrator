import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { Modal } from './ui';
import { ChatThread, Composer, type Loaded } from './Chat';
import { SessionPane, WIDE_TITLE, WidePane, type Wide } from './Panes';
import { agentLine, baseName, modelsView, toolListView, withAttachments, withLive, type AgentLine, type ModelsView, type ToolListView, type Turn } from './chatmodel';
import { Voice } from './Voice';
import { Screenshot } from './Screenshot';
import { Ico } from './icons';
import { getConvStore, setConvStore, useConvStore } from './sessionstore';
import { refusalText } from './terminalio';
import {
  COMMAND_TEXT, PROJECT_ID, RESUBSCRIBE_MS, applyLive, call, joinPages, reasonText, shouldNotify, stateText, transcriptLines,
  type Conversation, type Defaults, type Note, type Relay, type SessionView, type Transcript,
} from './sessionlog';

const relay: Relay = (cmd, payload) => invoke('session_call', { cmd, payload });
const NEW = 'new';

/** Chat sessions with a supported agent CLI. Everything on screen comes from the engine's replies; output is the agent's own text shown as data. */
export function Sessions() {
  const [list, setList] = useState<SessionView[]>([]);
  const [listState, setListState] = useState<'loading' | 'ok' | 'error'>('loading');
  const [conversations, setConversations] = useState<Conversation[]>([]); // the engine's list: this run's sessions and saved conversations, newest first
  const [tr, setTr] = useState<Record<string, Transcript>>({});
  const [defaults, setDefaults] = useState<Defaults | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [form, setForm] = useState({ root: '', model: '', text: '', mode: 'default' });
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [attach, setAttach] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const [models, setModels] = useState<Loaded<ModelsView>>({ s: 'loading' });
  const [tools, setTools] = useState<Loaded<ToolListView>>({ s: 'loading' });
  const [agent, setAgent] = useState<AgentLine | null>(null);
  const { sel, newRoot } = useConvStore();
  const turns = Object.fromEntries(Object.entries(tr).map(([k, v]) => [k, withLive(v.turns, v.live)]));
  useEffect(() => { if (newRoot) { setForm((f) => ({ ...f, root: newRoot })); setConvStore({ newRoot: null }); } }, [newRoot]);

  const refresh = useCallback(async () => {
    const r = await call<{ sessions: SessionView[]; conversations: Conversation[] }>(relay, 'sessions.list', {});
    if (r.ok) { setList(r.value.sessions); setConversations(r.value.conversations); setListState('ok'); setNote(null); } else { setListState('error'); setNote(r.text); }
  }, []);

  const trNow = useRef<Record<string, Transcript>>({}); // the transcripts on screen, readable by the stream handler between renders
  const stateNow = useRef<Record<string, string>>({}); // last state per session, so a notice only follows a real change
  const put = useCallback((id: string, next: (old: Transcript | undefined) => Transcript | undefined) => {
    const v = next(trNow.current[id]);
    if (!v || v === trNow.current[id]) return;
    trNow.current = { ...trNow.current, [id]: v };
    setTr(trNow.current);
  }, []);
  const seen = useRef<Record<string, string>>({}); // conversation -> the engine state already fetched, so nothing is fetched twice
  /** Reads the newest page of a conversation once per `marker`, or (with `before`) the page above the turns already shown. */
  const collect = useCallback(async (id: string, marker: string, before?: number) => {
    if (before === undefined) {
      if (seen.current[id] === marker) return;
      seen.current[id] = marker;
    }
    const r = await call<Transcript>(relay, 'session.transcript', { session_id: id, ...(before === undefined ? {} : { before }) });
    if (r.ok) put(id, (old) => joinPages(old, r.value)); else if (before === undefined) seen.current[id] = '';
  }, [put]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    let live = true;
    void call<Defaults>(relay, 'session.defaults', {}).then((r) => { if (live && r.ok) { setDefaults(r.value); setForm((f) => ({ ...f, model: f.model || r.value.model })); } });
    void call<unknown>(relay, 'session.models', {}).then((r) => { if (live) setModels({ s: 'done', v: modelsView(r) }); });
    return () => { live = false; };
  }, []);
  useEffect(() => {
    if (!defaults?.agent) return;
    let live = true;
    void call<unknown>(relay, 'agent.describe', { agent: defaults.agent }).then((r) => { if (live) setAgent(agentLine(r)); });
    return () => { live = false; };
  }, [defaults?.agent]);

  const active = sel === NEW ? null : list.find((x) => x.id === sel) ?? null;
  const archived = sel === NEW || active ? null : conversations.find((c) => c.id === sel) ?? null;
  const archT = archived ? tr[archived.id] ?? null : null;
  const root = active ? active.project_root : archived ? archived.project_root : form.root.trim() || null;
  useEffect(() => { if (archived) void collect(archived.id, 'saved'); }, [archived?.id, collect]); // eslint-disable-line react-hooks/exhaustive-deps
  // Continue a saved conversation: a new engine session whose first turn resumes the agent's own session, then it takes over the old record.
  const resumeSaved = async (c: Conversation) => {
    const text = withAttachments(draft[c.id] ?? '', attach[c.id] ?? []);
    setBusy(true);
    const r = await call<SessionView>(relay, 'session.start', { continue_conversation: c.id, text });
    setBusy(false);
    setNote(r.ok ? null : r.text);
    if (!r.ok) return;
    setDraft((d) => ({ ...d, [c.id]: '' })); setAttach((a) => ({ ...a, [c.id]: [] }));
    setConvStore({ sel: r.value.id });
    await refresh();
  };
  const forget = async (id: string) => {
    const r = await call(relay, 'session.forget', { session_id: id });
    setNote(r.ok ? null : r.text);
    setConvStore({ sel: NEW });
    await refresh();
  };
  useEffect(() => {
    let live = true;
    setTools({ s: 'loading' });
    invoke('capability_inventory', { projectRoot: root }).then((r) => toolListView(r), () => toolListView(null)).then((v) => { if (live) setTools({ s: 'done', v }); });
    return () => { live = false; };
  }, [root]);

  // The engine tells what changes (ADR-034), nothing is polled: a session's new state re-reads the list, an event of the running turn is
  // added where it is shown. When the stream closes it is asked for again, and the list is read anew once it is back.
  useEffect(() => {
    let on = true, timer: ReturnType<typeof setTimeout> | undefined;
    const subscribe = () => {
      invoke('engine_subscribe', { projectId: PROJECT_ID }).then(() => { if (on) void refresh(); }, () => { if (on) timer = setTimeout(subscribe, RESUBSCRIBE_MS); });
    };
    const off = listen<Note>('engine-event', ({ payload: n }) => {
      if (!on) return;
      if (n.event === 'stream.closed') timer = setTimeout(subscribe, RESUBSCRIBE_MS);
      else if (n.event === 'session.state') {
        const s = n.data.session, prev = stateNow.current[s.id];
        stateNow.current[s.id] = s.state;
        const kind = shouldNotify(prev, s.state, document.hasFocus(), getConvStore().sel === s.id);
        if (kind) void invoke('notify_attention', { kind }).catch(() => {}); // a refused or unavailable notice never disturbs the screen
        void refresh();
      }
      else if (n.event === 'session.event') {
        const { session_id: id, turn, event } = n.data;
        const cur = trNow.current[id];
        if (!cur) return; // not read yet: the first read brings the running turn's events with it
        const live = applyLive(cur.live, turn, event);
        if (live) put(id, (old) => (old ? { ...old, live } : old)); else void collect(id, `missed:${turn}:${String(event.seq)}`);
      }
    });
    subscribe();
    return () => { on = false; clearTimeout(timer); void off.then((stop) => stop()); };
  }, [refresh, collect, put]);
  useEffect(() => { list.forEach((s) => void collect(s.id, `${s.state}:${s.turn}`)); }, [list, collect]);

  const act = async (cmd: Parameters<typeof call>[1], s: SessionView, extra: Record<string, unknown> = {}) => {
    const r = await call<SessionView>(relay, cmd, { session_id: s.id, ...extra });
    setNote(r.ok ? null : r.text);
    await refresh();
    return r.ok;
  };

  const [panel, setPanel] = useState(true); // the narrow session bar: open by default in every conversation
  const [wideBy, setWideBy] = useState<Record<string, Wide | null>>({}); // files, browser...: open only in the conversation where it was opened
  const [menu, setMenu] = useState(false);
  const [modal, setModal] = useState<null | 'voice' | 'shot'>(null);
  useEffect(() => {
    setConvStore({ list: conversations.map((c) => ({ id: c.id, title: c.title, state: c.state, root: c.project_root, at: c.updated * 1000, saved: c.saved, pinned: c.pinned, archived: c.archived, match: c.match ?? '' })) });
  }, [conversations]);

  const pickFolder = async (start?: string): Promise<string | null> => invoke<string | null>('pick_folder', { start: start ?? null });
  const pickFiles = async (): Promise<string[]> => invoke<string[]>('pick_files');
  const newText = withAttachments(form.text, attach[NEW] ?? []);

  const start = async () => {
    setBusy(true);
    const r = await call<SessionView>(relay, 'session.start', { project_root: form.root.trim(), model: form.model, text: newText, mode: form.mode });
    setBusy(false);
    setNote(r.ok ? null : r.text);
    if (r.ok) {
      setForm({ ...form, text: '' }); setAttach({ ...attach, [NEW]: [] });
      setConvStore({ sel: r.value.id });
    }
    await refresh();
  };

  const send = async (s: SessionView) => {
    const text = withAttachments(draft[s.id] ?? '', attach[s.id] ?? []);
    setBusy(true);
    const ok = await act('session.send', s, { text });
    setBusy(false);
    if (ok) { setDraft({ ...draft, [s.id]: '' }); setAttach({ ...attach, [s.id]: [] }); }
  };

  // Chat -> terminal (ADR-035): the engine starts the agent's own interface on the same agent session and lets the chat side go; the
  // conversation stays in the list and the terminal pane of its folder shows the new terminal.
  const toTerminal = async (s: SessionView) => {
    try {
      const r = await invoke<{ ok: boolean; error: { code?: string; message?: string; reason?: string } | null }>('session_call', { cmd: 'terminal.start', payload: { project_id: PROJECT_ID, session_id: s.id } });
      setNote(r.ok ? null : refusalText(r.error));
      if (r.ok) setWideBy((w) => ({ ...w, [s.id]: 'terminal' }));
    } catch { setNote('Motora ulaşılamadı.'); }
    await refresh();
  };

  const [chipOpen, setChipOpen] = useState(false);
  const pickRoot = (r: string) => { setForm({ ...form, root: r }); setNote(null); };
  const chooseRoot = async () => { try { const p = await pickFolder(); if (p) pickRoot(p); } catch { setNote('Klasör seçici açılamadı.'); } };
  const wideKey = active?.id ?? archived?.id ?? NEW;
  const wide = wideBy[wideKey] ?? null;
  const setWide = (w: Wide | null) => setWideBy({ ...wideBy, [wideKey]: w });
  const known = [...new Set([form.root, ...conversations.map((c) => c.project_root)].filter(Boolean))].slice(0, 10);
  const pickModel = async (id: string) => {
    setForm((f) => ({ ...f, model: id }));
    const r = await call<Defaults>(relay, 'session.defaults.set', { model: id }); // the engine checks it and remembers it
    if (r.ok) { setDefaults(r.value); setNote(null); } else { setNote(r.text); setForm((f) => ({ ...f, model: defaults?.model ?? '' })); }
  };
  const model = active ? active.model : form.model;
  const common = {
    models, tools, pickFiles, pickFolder, onVoice: () => setModal('voice'), onShot: () => setModal('shot'),
    usage: active ? tr[active.id]?.usage ?? null : null,
    modes: defaults?.modes ?? ['default'], mode: active ? active.mode : form.mode,
  };
  const title = active ? active.title : archived ? archived.title : 'Yeni oturum';
  /** The conversation is read a page at a time: this asks for the page above the turns on screen, when there is one. */
  const olderOf = (id: string) => (tr[id]?.first ?? 0) > 0 && <button type="button" className="btn sm" onClick={() => void collect(id, '', tr[id].first)}>Daha eski turları göster ({tr[id].first})</button>;

  return (
    <section aria-labelledby="sessions-h" className="chatpage">
      <h2 id="sessions-h" className="sr-only">Sohbet oturumları</h2>
      <div className="thread concept">
        <div className="concept inline"><div className="bar" data-tauri-drag-region>
          <div className="grow row"><h1 title={title}>{title}</h1>{active && <span role="status" className="sr-only">{stateText(active.state)}</span>}</div>
          <div className="toptools" role="toolbar" aria-label="Oturum araçları">
            {(active || archived) && <button className={`ib ${panel ? 'on' : ''}`} aria-pressed={panel} onClick={() => setPanel((p) => !p)} title="Oturum çubuğu" aria-label="Oturum çubuğunu aç/kapat"><Ico n="panel" /></button>}
            {([['terminal', 'terminal'], ['diff', 'diff'], ['browser', 'globe'], ['files', 'folder']] as const).filter(([k]) => active || archived || k !== 'diff').map(([k, icon]) => (
              <button key={k} className={`ib ${wide === k ? 'on' : ''}`} aria-pressed={wide === k} onClick={() => setWide(wide === k ? null : k)} title={WIDE_TITLE[k]} aria-label={`${WIDE_TITLE[k]} bölmesini aç/kapat`}><Ico n={icon} /></button>))}
            {active && <button className="ib" aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu(!menu)} title="Diğer" aria-label="Diğer işlemler"><Ico n="more" /></button>}
          </div>
          {menu && <div className="pop" role="menu" style={{ position: 'fixed', top: 40, right: 140, zIndex: 60 }} onKeyDown={(e) => { if (e.key === 'Escape') setMenu(false); }}>
            {active && <button className="it" role="menuitem" disabled={active.state === 'running'} title={active.state === 'running' ? 'Bir tur çalışıyor.' : 'Ajanın kendi arayüzü, aynı ajan oturumuyla'} onClick={() => { setMenu(false); void toTerminal(active); }}><div>Terminalde sürdür</div></button>}
            {active && <button className="it" role="menuitem" disabled={!active.commands.cancel.enabled} title={reasonText(active.commands.cancel.reason)} onClick={() => { setMenu(false); void act('session.cancel', active); }}><div>Oturumu bitir</div></button>}
            {[['Yan sohbet', 'Motorda karşılığı yok'], ['Arka plan görevleri', 'Motorda karşılığı yok'], ['Bilgisayarı uyanık tut', 'Motorda karşılığı yok']].map(([a, b]) => <div key={a} className="it" role="menuitem" aria-disabled="true"><div>{a}<div className="mut">{b}</div></div></div>)}</div>}
        </div></div>
        {listState === 'loading' && <p role="status">Oturumlar yükleniyor…</p>}
        {note && <div role="alert"><p>{note}</p>{listState === 'error' && <button className="btn sm" onClick={() => void refresh()}>Yeniden dene</button>}</div>}
        {archived ? (
          <article aria-label="Geçmiş oturum" className="session">
            <div className="scroll"><div className="msgs">{olderOf(archived.id)}<ChatThread turns={turns[archived.id] ?? []} running={false} /></div></div>
            <Composer {...common} mode="default" usage={archT?.usage ?? null} model={archT?.model ?? ''} value={draft[archived.id] ?? ''} onChange={(v) => setDraft({ ...draft, [archived.id]: v })} onSend={() => void resumeSaved(archived)}
              canSend={!!(draft[archived.id] ?? '').trim() && !busy && !!archT?.resumable} disabled={!archT?.resumable}
              placeholder={archT?.resumable ? 'Kaldığın yerden devam et…' : 'Bu sohbet devam ettirilemez (ajan oturum kimliği yok)'}
              attachments={attach[archived.id] ?? []} setAttachments={(x) => setAttach({ ...attach, [archived.id]: x })} />
          </article>
        ) : !active ? (
          <div className="newchat">
            <div className="mid"><ProjectMenu known={known} current={form.root} onPick={pickRoot} onChoose={chooseRoot} /></div>
            {agent && <p role="status" className="mut" style={{ textAlign: 'center' }}>{agent.text}</p>}
            <Composer {...common} value={form.text} onChange={(v) => setForm({ ...form, text: v })} onSend={() => void start()} canSend={!!form.root && !!form.text.trim() && !!form.model && !busy}
              placeholder={form.root ? 'Bir görev tanımlayın veya bir soru sorun' : 'Önce bir proje klasörü seçin…'}
              model={form.model} onPickModel={(id) => void pickModel(id)} onPickMode={(id) => setForm((f) => ({ ...f, mode: id }))}
              lead={<span style={{ position: 'relative' }} onKeyDown={(e) => { if (e.key === 'Escape') setChipOpen(false); }}>
                <button type="button" className="chip flat" aria-haspopup="menu" aria-expanded={chipOpen} title={form.root || 'Proje klasörü seç'} onClick={() => setChipOpen(!chipOpen)}><Ico n="folder" /> {form.root ? baseName(form.root) : 'Klasör seçilmedi'} <Ico n="down" /></button>
                {chipOpen && <ProjectMenu className="up" known={known} current={form.root} onPick={(r) => { pickRoot(r); setChipOpen(false); }} onChoose={async () => { await chooseRoot(); setChipOpen(false); }} />}</span>}
              attachments={attach[NEW] ?? []} setAttachments={(a) => setAttach({ ...attach, [NEW]: a })} />
          </div>
        ) : (
          <SessionCard key={active.id} s={active} turns={turns[active.id] ?? []} older={olderOf(active.id)} draft={draft[active.id] ?? ''} busy={busy}
            setDraft={(t) => setDraft({ ...draft, [active.id]: t })} onSend={() => void send(active)} act={(c) => void act(c, active)}
            composer={{ ...common, model, attachments: attach[active.id] ?? [], setAttachments: (a) => setAttach({ ...attach, [active.id]: a }),
              onPickMode: active.state === 'running' ? undefined : (id) => void act('session.mode.set', active, { mode: id }) }} />
        )}
      </div>
      {panel && (active || archived) && <SessionPane s={active} usage={active ? tr[active.id]?.usage ?? null : archT?.usage ?? null} turns={active ? turns[active.id] ?? [] : archT?.turns ?? []} root={root} tools={tools} close={() => setPanel(false)} />}
      {wide && <WidePane kind={wide} s={active} turns={active ? turns[active.id] ?? [] : archT?.turns ?? []} root={root} lines={active ? linesOf(turns[active.id] ?? []) : []} pickFolder={pickFolder} close={() => setWide(null)} />}
      {modal === 'voice' && <Modal title="Sesli görev" onClose={() => setModal(null)} foot={<button className="btn" onClick={() => setModal(null)}>Kapat</button>}><Voice /></Modal>}
      {modal === 'shot' && <Modal title="Ekran görüntüsü" onClose={() => setModal(null)} foot={<button className="btn" onClick={() => setModal(null)}>Kapat</button>}><Screenshot /></Modal>}
    </section>
  );
}

/** A session's turns as transcript lines (the terminal pane draws these). */
const linesOf = (turns: Turn[]): string[] => turns.flatMap((t) => [...(t.user !== null ? [`> ${t.user}`] : []), ...transcriptLines(t.result?.events ?? []), ...(t.result?.error ? [`[hata] ${t.result.error}`] : []), '']);

type CommonComposer = Omit<Parameters<typeof Composer>[0], 'onStop' | 'value' | 'onChange' | 'onSend' | 'canSend' | 'disabled' | 'placeholder'>;

/** The project list. The middle of the new-chat page and the chip under the composer both show it and change the same selection. */
function ProjectMenu({ known, current, onPick, onChoose, className = '' }: { known: string[]; current: string; onPick: (r: string) => void; onChoose: () => void; className?: string }) {
  return (
    <div className={`projmenu ${className}`} role="menu" aria-label="Proje klasörü">
      {known.length === 0 && <p className="mut" style={{ padding: '8px 12px' }}>Henüz proje yok. Bir klasör seçerek başla.</p>}
      {known.map((r) => (
        <button key={r} type="button" role="menuitemradio" aria-checked={r === current} className="pm" title={r} onClick={() => onPick(r)}>
          <Ico n="folder" /><span className="grow"><span className="pn">{baseName(r)}</span>{known.filter((o) => baseName(o) === baseName(r)).length > 1 && <span className="pp mut">{r}</span>}</span>{r === current && <Ico n="check" />}</button>))}
      <button type="button" role="menuitem" className="pm add" onClick={onChoose}><Ico n="plus" /><span className="grow"><span className="pn">Klasör seç…</span></span></button>
    </div>
  );
}

function SessionCard({ s, turns, older, draft, setDraft, onSend, act, busy, composer }: {
  s: SessionView; turns: Turn[]; older: React.ReactNode; draft: string; setDraft: (t: string) => void; onSend: () => void; act: (c: 'session.retry' | 'session.interrupt' | 'session.cancel' | 'session.resume') => void;
  busy: boolean; composer: CommonComposer;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'end' }); }, [turns[turns.length - 1], s.state]); // new output scrolls down; older turns put in front do not
  return (
    <article aria-label={`Oturum ${s.agent}`} className="session">
      <div className="scroll"><div className="msgs">
        {turns.length === 0 ? <p className="mut">Bu pencerede bu oturumun geçmişi yok; yalnızca bundan sonrakiler görünür.</p>
          : <>{older}<ChatThread turns={turns} running={s.state === 'running'} /></>}
        {s.state === 'failed' && <div role="alert" className="row" style={{ flexWrap: 'wrap', gap: 8 }}><span>Son tur başarısız oldu{s.last_state ? ` (${s.last_state})` : ''}.</span>
          {(['retry', 'resume'] as const).map((k) => <button key={k} className="btn sm" disabled={!s.commands[k].enabled} title={reasonText(s.commands[k].reason)} onClick={() => act(`session.${k}`)}>{COMMAND_TEXT[k]}</button>)}</div>}
        <div ref={end} />
      </div></div>
      <Composer {...composer} onStop={s.commands.interrupt.enabled ? () => act('session.interrupt') : undefined} value={draft} onChange={setDraft} onSend={onSend} canSend={s.commands.send.enabled && !!draft.trim() && !busy} disabled={!s.commands.send.enabled}
        placeholder={s.commands.send.enabled ? 'Ajana mesaj yaz…' : reasonText(s.commands.send.reason) || 'Şu an mesaj gönderilemez.'} />
    </article>
  );
}
