import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Empty, Failed, Loading, Modal, Page } from './ui';
import { ATTENTION_STATES, RUN_STATE, activityView, newestCursor, projectsView, readyAgents, runsView, startedView, stateInfo, taskRequest, when, type ActivityView, type ProjectRow, type RunRow, type TaskForm, type View } from './boardviews';
import { baseName } from './chatmodel';

/** One read-only engine call. A failure to reach the engine is a view, not an exception. */
async function read<T>(cmd: string, payload: Record<string, unknown>, parse: (reply: unknown) => T): Promise<T | { kind: 'error'; text: string; hint: string }> {
  try { return parse(await invoke('read_call', { cmd, payload })); } catch (e) {
    return { kind: 'error', text: 'Motora ulaşılamadı.', hint: (e as { hint?: string })?.hint ?? 'Motorun kurulu ve çalışır olduğunu kontrol edin.' };
  }
}

function useBoard<T extends { kind: string }>(load: () => Promise<T | { kind: 'error'; text: string; hint: string }>, deps: unknown[], pollWhen?: (v: T) => boolean) {
  const [v, setV] = useState<T | { kind: 'error'; text: string; hint: string } | null>(null);
  const reload = useCallback(() => { void load().then(setV); }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setV(null); reload(); }, [reload]);
  const polling = v !== null && v.kind !== 'error' && pollWhen?.(v as T) === true;
  useEffect(() => { if (!polling) return; const t = setInterval(reload, 4000); return () => clearInterval(t); }, [polling, reload]);
  return [v, reload] as const;
}

const Badge = ({ state }: { state: string }) => { const i = stateInfo(state); return <span className={`badge ${i.tone === 'run' ? '' : i.tone}`}>{i.tone === 'run' && <span className="dot run" />} {i.text}</span>; };
const Refresh = ({ onClick }: { onClick: () => void }) => <button className="btn sm" onClick={onClick}>Yenile</button>;

function RunTable({ rows }: { rows: RunRow[] }) {
  return (
    <div className="card"><table><thead><tr><th>Görev</th><th>Ajan</th><th>Durum</th><th>Proje</th><th>Güncellendi</th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={r.run_id}><td><div>{r.task || <span className="mut">(görev metni yok)</span>}</div><div className="mono mut">{r.run_id}</div>{r.error && <div className="mut">{r.error}</div>}</td>
          <td>{r.agent ?? '—'}</td><td><Badge state={r.state} /></td><td className="mut" title={r.project_root ?? ''}>{r.project_root ? baseName(r.project_root) : '—'}</td><td className="mut">{when(r.updated_at ?? r.created_at)}</td></tr>))}</tbody></table></div>
  );
}

const BOX = { border: '1px solid color-mix(in srgb, currentColor 25%, transparent)', borderRadius: 6, padding: 6 };

/** Start one task run. The form only collects; the engine validates the request, refuses what this caller may not ask for, and starts it. */
function NewTask({ close, started }: { close: () => void; started: () => void }) {
  const [f, setF] = useState<TaskForm>({ root: '', task: '', kind: 'read', worker: '', ownership: '.', acceptance: '' });
  const [agents, setAgents] = useState<string[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { let live = true; invoke('session_call', { cmd: 'agent.describe', payload: {} }).then((r) => { if (live) setAgents(readyAgents(r)); }, () => undefined); return () => { live = false; }; }, []);
  const pick = async () => { try { const p = await invoke<string | null>('pick_folder', { start: null }); if (p) setF((x) => ({ ...x, root: p })); } catch { setNote('Klasör seçici açılamadı.'); } };
  const start = async () => {
    const req = taskRequest(f);
    if (!req.ok) { setNote(req.text); return; }
    setBusy(true);
    const r = await invoke('session_call', { cmd: 'task.start', payload: req.value }).then(startedView, () => startedView(null));
    setBusy(false);
    if (r.ok) { started(); close(); } else setNote(r.text);
  };
  return (
    <Modal title="Yeni görev" onClose={close} foot={<><button className="btn" onClick={close}>Vazgeç</button><button className="btn pri" disabled={busy} onClick={() => void start()}>Başlat</button></>}>
      <div className="col" style={{ display: 'grid', gap: 10 }}>
        <div className="row"><button type="button" className="btn sm" onClick={() => void pick()}>Proje klasörü seç…</button><span className="mut" title={f.root}>{f.root || 'Seçilmedi (Git deposunun kökü olmalı)'}</span></div>
        <label>Görev<textarea style={BOX} rows={4} value={f.task} onChange={(e) => setF({ ...f, task: e.target.value })} placeholder="Ne yapılacağını yazın" /></label>
        <div className="row">
          <label>Tür <select className="seg" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as TaskForm['kind'] })}><option value="read">Yalnız okur</option><option value="write">Dosya değiştirir</option></select></label>
          <label>Ajan <select className="seg" value={f.worker} onChange={(e) => setF({ ...f, worker: e.target.value })}><option value="">Varsayılan</option>{agents.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
        </div>
        <label>Kapsam (her satıra bir yol; ajan yalnız bunlara dokunabilir)<textarea style={BOX} rows={2} value={f.ownership} onChange={(e) => setF({ ...f, ownership: e.target.value })} /></label>
        <label>Kabul komutları (her satıra bir komut; dosya değiştiren görevde zorunlu)<textarea style={BOX} rows={2} value={f.acceptance} onChange={(e) => setF({ ...f, acceptance: e.target.value })} placeholder="python -m pytest -q" /></label>
        <p className="mut">İş ayrı bir çalışma ağacında yürür; gerçek ağaca siz onaylamadan uygulanmaz. Kabul komutları yalnız izin listenizdekilerden olabilir (<span className="mono">mcp_acceptance_allow</span> ayarı).</p>
        {note && <p role="alert">{note}</p>}
      </div>
    </Modal>
  );
}

export function Tasks() {
  const [state, setState] = useState('all');
  const [creating, setCreating] = useState(false);
  const [q, setQ] = useState('');
  const [v, reload] = useBoard<View<RunRow>>(() => read('runs.list', { limit: 100, ...(state !== 'all' ? { states: [state] } : {}), ...(q.trim() ? { query: q.trim() } : {}) }, runsView), [state, q],
    (b) => b.kind === 'rows' && b.rows.some((r) => r.state === 'in_progress' || r.state === 'queued'));
  return (
    <Page title="Görevler" sub="Motorun kayıtlı çalışmaları" actions={<><button className="btn sm" onClick={() => setCreating(true)}>Yeni görev</button><Refresh onClick={reload} /></>}>
      {creating && <NewTask close={() => setCreating(false)} started={reload} />}
      <div className="row" style={{ marginBottom: 12 }}>
        <select className="seg" value={state} onChange={(e) => setState(e.target.value)} aria-label="Duruma göre süz">
          <option value="all">Tüm durumlar</option>{Object.entries(RUN_STATE).map(([k, i]) => <option key={k} value={k}>{i.text}</option>)}</select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Görev, ajan ya da kimlik ara…" aria-label="Görevlerde ara" style={{ flex: 1, maxWidth: 360 }} />
      </div>
      {v === null ? <Loading text="Görevler okunuyor…" />
        : v.kind === 'error' ? <Failed text={v.text} hint={v.hint} retry={reload} />
        : v.rows.length === 0 ? <Empty title={state !== 'all' || q ? 'Bu süzgece uyan görev yok.' : 'Henüz görev yok.'} hint="Yeni görev düğmesiyle, `rorch task start` komutuyla ya da bir AI aracının MCP bağlantısıyla başlatılan görevler burada görünür." />
        : <><RunTable rows={v.rows} />{v.more && <p className="mut">En yeni 100 görev gösteriliyor.</p>}</>}
    </Page>
  );
}

export function Inbox() {
  const [v, reload] = useBoard<View<RunRow>>(() => read('runs.list', { limit: 100, states: [...ATTENTION_STATES] }, runsView), []);
  return (
    <Page title="Gelen kutusu" sub="Dikkat isteyen görevler" actions={<Refresh onClick={reload} />}>
      {v === null ? <Loading text="Okunuyor…" />
        : v.kind === 'error' ? <Failed text={v.text} hint={v.hint} retry={reload} />
        : v.rows.length === 0 ? <Empty title="Dikkat isteyen bir şey yok." hint="Başarısız olan, yarıda kalan ya da kaydı bozuk görevler burada listelenir. Uygulama onayları ayrı onay penceresinde sorulur." />
        : <RunTable rows={v.rows} />}
    </Page>
  );
}

export function Projects() {
  const [v, reload] = useBoard<View<ProjectRow>>(() => read('projects.list', { limit: 100 }, projectsView), [], (b) => b.kind === 'rows' && b.rows.some((p) => p.alive));
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Page title="Projeler" sub="Çok aşamalı çalışmalar" actions={<Refresh onClick={reload} />}>
      {v === null ? <Loading text="Projeler okunuyor…" />
        : v.kind === 'error' ? <Failed text={v.text} hint={v.hint} retry={reload} />
        : v.rows.length === 0 ? <Empty title="Henüz proje yok." hint="Bir plan onaylanıp başlatıldığında proje burada görünür." />
        : v.rows.map((p) => (
          <div key={p.project_id} className="card"><button type="button" className="h" style={{ width: '100%', textAlign: 'left' }} aria-expanded={open === p.project_id} onClick={() => setOpen(open === p.project_id ? null : p.project_id)}>
            <span className="grow">{p.goal || <span className="mut">(hedef yok)</span>}</span><Badge state={p.state === 'running' ? 'in_progress' : p.state} />{p.alive && <span className="badge">canlı</span>}</button>
            {p.error && <div className="b" role="alert">{p.error}</div>}
            {open === p.project_id && <div className="b"><div className="mono mut">{p.project_id} · {when(p.created_at)}</div>
              {p.stages.length === 0 ? <p className="mut">Aşama bilgisi yok.</p> : <table><thead><tr><th>Aşama</th><th>Durum</th><th>Önce</th><th>Deneme</th></tr></thead>
                <tbody>{p.stages.map((g) => <tr key={g.name}><td>{g.name}</td><td>{g.status ?? '—'}</td><td className="mut">{g.after.join(', ') || '—'}</td><td>{g.attempts}</td></tr>)}</tbody></table>}</div>}
          </div>))}
    </Page>
  );
}

const PAGE = 100;
export function Flow() {
  const [v, reload] = useBoard<ActivityView>(async () => {
    const first = await read('activity.list', { cursor: 0, limit: PAGE }, activityView);
    if (first.kind === 'error' || !first.more) return first;
    return read('activity.list', { cursor: newestCursor(first.lastSeq, PAGE), limit: PAGE }, activityView);
  }, []);
  return (
    <Page title="Etkinlik" sub="Motorun olay günlüğü, en yeniler üstte" actions={<><Refresh onClick={reload} /></>}>
      {v === null ? <Loading text="Etkinlik okunuyor…" />
        : v.kind === 'error' ? <Failed text={v.text} hint={v.hint} retry={reload} />
        : v.rows.length === 0 ? <Empty title="Henüz kayıtlı olay yok." hint="Bir görev ya da proje çalışınca olaylar burada akar." />
        : <div className="card"><table><thead><tr><th>Zaman</th><th>Olay</th><th>İşlem</th><th>Çalışma</th></tr></thead>
          <tbody>{[...v.rows].reverse().map((e) => <tr key={e.seq}><td className="mut">{when(e.ts)}</td><td><span className="mono">{e.type}</span></td><td className="mut">{e.op}</td><td className="mono mut">{e.run ?? '—'}</td></tr>)}</tbody></table></div>}
    </Page>
  );
}
