import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { TerminalPane } from './TerminalPane';
import { bufferOf } from './terminal';
import {
  AGENTS, COMMAND_TEXT, DEFAULT_MODEL, POLL_MS, call, reasonText, shouldPoll, startProblem, stateText, transcriptLines,
  type Relay, type SessionView, type TurnResult,
} from './sessionlog';

const relay: Relay = (cmd, payload) => invoke('session_call', { cmd, payload });

/** Chat sessions with a supported agent CLI. Output is the agent's own text shown as data; this screen has no approve button. */
export function Sessions() {
  const [list, setList] = useState<SessionView[]>([]);
  const [lines, setLines] = useState<Record<string, string[]>>({});
  const [note, setNote] = useState<string | null>(null);
  const [form, setForm] = useState({ root: '', model: DEFAULT_MODEL, text: '' });
  const [draft, setDraft] = useState<Record<string, string>>({});
  const shown = useRef<Record<string, string>>({}); // session -> marker of the turn already appended, so a poll never duplicates it

  const refresh = useCallback(async () => {
    const r = await call<{ sessions: SessionView[] }>(relay, 'sessions.list', {});
    if (r.ok) setList(r.value.sessions); else setNote(r.text);
  }, []);

  const collect = useCallback(async (s: SessionView) => {
    const r = await call<{ state: string; turn: number; result: TurnResult }>(relay, 'session.events', { session_id: s.id });
    if (!r.ok || !r.value.result) return;
    const marker = `${s.id}:${r.value.turn}`; // the engine's turn number: equally-shaped results are still different turns
    if (shown.current[s.id] === marker) return;
    shown.current[s.id] = marker;
    const result = r.value.result;
    setLines((l) => ({ ...l, [s.id]: [...(l[s.id] ?? []), ...transcriptLines(result.events), ...(result.error ? [`[hata] ${result.error}`] : []), ''] }));
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  const running = list.filter(shouldPoll);
  useEffect(() => {
    if (running.length === 0) return;
    const t = setInterval(async () => { await Promise.all(running.map(collect)); await refresh(); }, POLL_MS);
    return () => clearInterval(t);
  }, [running.map((s) => s.id).join(','), collect, refresh]);
  useEffect(() => { list.filter((s) => s.state !== 'running').forEach((s) => void collect(s)); }, [list, collect]);

  const act = async (cmd: Parameters<typeof call>[1], s: SessionView, extra: Record<string, unknown> = {}) => {
    const r = await call<SessionView>(relay, cmd, { session_id: s.id, ...extra });
    setNote(r.ok ? null : r.text);
    await refresh();
  };
  const problem = form.text ? startProblem(form) : null; // no message for an empty message box (e.g. right after a start); the button is off anyway

  return (
    <section aria-labelledby="sessions-h">
      <h2 id="sessions-h">Sohbet oturumları</h2>
      <p>Desteklenen ajan: {AGENTS.join(', ')}. Oturumdaki izin istekleri burada onaylanamaz; onaylar ayrı onay penceresindedir.</p>
      {note && <p role="alert">{note}</p>}
      <form onSubmit={async (e) => {
        e.preventDefault();
        const r = await call<SessionView>(relay, 'session.start', { project_root: form.root.trim(), agent: AGENTS[0], model: form.model.trim(), text: form.text });
        setNote(r.ok ? null : r.text);
        if (r.ok) { setLines((l) => ({ ...l, [r.value.id]: [`> ${form.text}`, ''] })); setForm({ ...form, text: '' }); }
        await refresh();
      }}>
        <label>Proje klasörü <input value={form.root} onChange={(e) => setForm({ ...form, root: e.target.value })} placeholder="C:\Projeler\uygulama" /></label>
        <label>Model <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></label>
        <label>İlk ileti <textarea value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} rows={3} /></label>
        {problem && <p role="status">{problem}</p>}
        <button type="submit" disabled={!form.root || !form.text || problem !== null}>Oturumu başlat</button>
      </form>
      {list.length === 0 && <p role="status">Açık oturum yok.</p>}
      {list.map((s) => <SessionCard key={s.id} s={s} lines={lines[s.id] ?? []} draft={draft[s.id] ?? ''}
        setDraft={(t) => setDraft({ ...draft, [s.id]: t })}
        onSend={async () => { setLines((l) => ({ ...l, [s.id]: [...(l[s.id] ?? []), `> ${draft[s.id]}`, ''] })); const t = draft[s.id]; setDraft({ ...draft, [s.id]: '' }); await act('session.send', s, { text: t }); }}
        act={(c) => act(c, s)} />)}
    </section>
  );
}

function SessionCard({ s, lines, draft, setDraft, onSend, act }: {
  s: SessionView; lines: string[]; draft: string; setDraft: (t: string) => void; onSend: () => void; act: (c: 'session.retry' | 'session.interrupt' | 'session.cancel' | 'session.resume') => void;
}) {
  const buffer = useMemo(() => bufferOf(lines), [lines]);
  const button = (name: 'retry' | 'interrupt' | 'cancel' | 'resume', cmd: Parameters<typeof act>[0]) => (
    <button key={name} disabled={!s.commands[name].enabled} title={reasonText(s.commands[name].reason)} onClick={() => act(cmd)}>{COMMAND_TEXT[name]}</button>
  );
  return (
    <article aria-label={`Oturum ${s.agent}`}>
      <h3>{s.agent} · {s.model} · <span role="status">{stateText(s.state)}</span></h3>
      <TerminalPane id={s.id} agent={`${s.agent} (${s.model})`} buffer={buffer} rows={12} />
      <div>
        {button('interrupt', 'session.interrupt')}{button('retry', 'session.retry')}{button('resume', 'session.resume')}{button('cancel', 'session.cancel')}
      </div>
      <label>İleti <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={2} disabled={!s.commands.send.enabled} /></label>
      <button disabled={!s.commands.send.enabled || !draft.trim()} title={reasonText(s.commands.send.reason)} onClick={onSend}>{COMMAND_TEXT.send}</button>
    </article>
  );
}
