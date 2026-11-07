import { useEffect, useId, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { budgetBadge, budgetWhy, warningText, compatText, historyLine, memberStatus, nextStepText, noteText, rateText, riskText, roleText, suggestView, teamView, tokenText, usageView,
  visibleSuggestions, type Bucket, type ReadCommand, type SuggestView, type TeamView, type UsageView, type Failure } from './beta4';

const DISMISS_KEY = 'orch.suggestions.dismissed';
const loadDismissed = (): Set<string> => { try { return new Set(JSON.parse(localStorage.getItem(DISMISS_KEY) ?? '[]')); } catch { return new Set(); } };
const saveDismissed = (s: Set<string>) => { try { localStorage.setItem(DISMISS_KEY, JSON.stringify([...s])); } catch { /* a viewer convenience only */ } };

type Loading = { kind: 'loading' };
function useRead<T>(cmd: ReadCommand, payload: Record<string, unknown> | null, parse: (reply: unknown) => T | Failure) {
  const [view, setView] = useState<T | Failure | Loading>({ kind: 'loading' });
  const load = () => {
    if (payload === null) return;
    setView({ kind: 'loading' });
    invoke('read_call', { cmd, payload })
      .then((reply) => setView(parse(reply)))
      .catch((e: { hint?: string }) => setView({ kind: 'error', text: 'Motora ulaşılamadı.', hint: e?.hint ?? 'Yenile düğmesiyle tekrar deneyin.' }));
  };
  useEffect(load, [JSON.stringify(payload)]);
  return [view, load] as const;
}

function ErrorBox({ view, reload }: { view: Failure; reload: () => void }) {
  return <div role="alert"><p>{view.text}</p><p>{view.hint}</p><button onClick={reload}>Yenile</button></div>;
}

/** Read-only team overview: who is on the team, whether each can run now, and what was handed over, from the engine's event store. */
export function Team() {
  const id = useId();
  const [view, load] = useRead<TeamView>('team.view', {}, teamView);
  if (view.kind === 'loading') return <p role="status">Takım okunuyor…</p>;
  if (view.kind === 'error') return <ErrorBox view={view} reload={load} />;
  return (
    <section aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{view.team.name}</h2>
      <p>Bu ekran <strong>yalnızca okunur</strong>: hiçbir devir başlatmaz, onaylamaz veya uygulamaz. Geçmiş motorun olay deposundan okunur; yenileyerek güncelleyin.</p>
      {view.rejected > 0 && <div role="alert"><p>{view.rejected} kayıt imzası doğrulanamadığı için gösterilmedi.</p></div>}
      <button type="button" onClick={load}>Yenile</button>
      {view.members.length === 0 ? <p>Takımda henüz profil yok.</p> : (
        <table>
          <caption className="sr-only">Takım üyeleri</caption>
          <thead><tr><th scope="col">Ad</th><th scope="col">Rol</th><th scope="col">Araç / model</th><th scope="col">Yetkiler</th><th scope="col">Durum</th></tr></thead>
          <tbody>
            {view.members.map((m) => {
              const s = memberStatus(m);
              return (
                <tr key={m.id}>
                  <th scope="row">{m.name}<div className="path">sürüm {m.rev}</div></th>
                  <td>{roleText(m.role)}</td>
                  <td>{m.tool ?? 'varsayılan'}{m.profile ? ` / ${m.profile}` : ''}</td>
                  <td>{m.capabilities.join(', ')}</td>
                  <td data-state={String(s.usable)}>{s.text}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <h3>Devir geçmişi</h3>
      {view.history.length === 0 ? <p>Henüz devir yok.</p> : (
        <ol className="history">{view.history.map((h) => <li key={h.seq}>{historyLine(h)}{h.run ? <span className="path"> · {h.run}</span> : null}</li>)}</ol>
      )}
    </section>
  );
}

/** Suggestions for a task. Asking is a click; the screen has no button that enables, installs, trusts or runs anything. */
export function Suggestions() {
  const id = useId();
  const [task, setTask] = useState('');
  const [asked, setAsked] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<Set<string>>(loadDismissed);
  const [view, load] = useRead<SuggestView>('capabilities.recommend', asked === null ? null : { task: asked }, suggestView);
  const dismiss = (sid: string) => { const next = new Set(dismissed).add(sid); setDismissed(next); saveDismissed(next); };
  return (
    <section aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="sr-only">Yetenek önerileri</h2>
      <p>Önerilen her şey <strong>yalnızca bir öneridir</strong>: hiçbir şey kurulmaz veya etkinleştirilmez, ağdan bir şey indirilmez. Etkinleştirme ayrı bir plan ve sizin onayınızla olur.</p>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); if (task.trim()) setAsked(task.trim()); }}>
        <label>Görev <input type="text" value={task} maxLength={2000} onChange={(e) => setTask(e.target.value)} aria-label="Görev açıklaması" size={60} /></label>
        <button type="submit" disabled={!task.trim()}>Öner</button>
        <button type="button" onClick={() => setDismissed(new Set())}>Gizlenenleri göster</button>
      </form>
      {asked === null ? <p>Bir görev yazıp “Öner”e basın.</p> : view.kind === 'loading' ? <p role="status">Yetenekler okunuyor…</p> : view.kind === 'error' ? <ErrorBox view={view} reload={load} /> : (
        <>
          {view.notes.map((n, i) => <p key={i} role="status">{noteText(n)}</p>)}
          {visibleSuggestions(view.items, dismissed).length > 0 && (
            <ul className="suggestions">
              {visibleSuggestions(view.items, dismissed).map((s) => (
                <li key={s.id}>
                  <strong>{s.name}</strong> · {s.kind === 'mcp' ? 'MCP' : 'Beceri'} · {compatText(s.compatibility)} · {s.installed === true ? 'kurulu' : s.installed === false ? 'kurulu değil' : 'kurulum bilinmiyor'} · güven: {s.trusted ? 'onaylı' : 'yok'}
                  <div>Neden: {s.matched.join(', ')} · {s.compatibility_reasons.join('; ')}</div>
                  {s.risks.length > 0 && <div>Riskler: {s.risks.map(riskText).join(', ')}</div>}
                  {s.description && <div className="path">{s.description}</div>}
                  <div>{nextStepText(s)}</div>
                  <button type="button" onClick={() => dismiss(s.id)}>Görmezden gel</button>
                </li>
              ))}
            </ul>
          )}
          {view.excluded.length > 0 && <details><summary>Uymayanlar ({view.excluded.length})</summary><ul>{view.excluded.map((e) => <li key={e.id}>{e.name}: {e.why.join('; ')}</li>)}</ul></details>}
        </>
      )}
    </section>
  );
}

const Row = ({ b }: { b: Bucket }) => (
  <tr><th scope="row">{b.name}</th><td>{b.runs}</td><td>{b.accepted}</td><td>{rateText(b)}</td><td>{tokenText(b)}</td><td>{b.quota_stops}</td></tr>
);
const Table = ({ title, rows }: { title: string; rows: Bucket[] }) => rows.length === 0 ? null : (
  <table>
    <caption>{title}</caption>
    <thead><tr><th scope="col">Ad</th><th scope="col">Çalıştırma</th><th scope="col">Kabul</th><th scope="col">Kabul oranı</th><th scope="col">Bildirilen token</th><th scope="col">Kota durması</th></tr></thead>
    <tbody>{rows.map((b) => <Row key={b.name} b={b} />)}</tbody>
  </table>
);

/** Local budget/success view. Reported, estimated and unknown values are kept apart; the budget is green only when everything reported. */
export function Usage() {
  const id = useId();
  const [view, load] = useRead<UsageView>('analytics.summary', {}, usageView);
  if (view.kind === 'loading') return <p role="status">Kullanım okunuyor…</p>;
  if (view.kind === 'error') return <ErrorBox view={view} reload={load} />;
  if (view.kind === 'disabled') return <section><p role="status">Kullanım verisi toplama kapalı: {view.reason}</p></section>;
  const badge = budgetBadge(view.budget.status);
  return (
    <section aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="sr-only">Bütçe ve başarı</h2>
      <p>Yalnızca bu bilgisayardaki imzalı çalıştırma kayıtlarından okunur; hiçbir yere gönderilmez. Bildirilen, tahmini ve bilinmeyen değerler ayrı tutulur.</p>
      <p role="status" className="badge" data-tone={badge.tone}>{badge.text} — {budgetWhy(view.budget.status, view.budget.why, view.budget.limit)}{view.budget.limit ? ` (sınır ${view.budget.limit})` : ''}</p>
      <p>Tahmini maliyet: {view.estimate.status === 'not_computed' ? 'hesaplanmadı (fiyat kataloğu yok); maliyet bilinmiyor, sıfır değil.' : view.estimate.status}</p>
      {view.warnings.map((w, i) => <div role="alert" key={i}><p>{warningText(w)}</p></div>)}
      <p>Son {view.windowRuns} çalıştırma · genel: kabul {rateText(view.totals)} · token {tokenText(view.totals)}</p>
      <button type="button" onClick={load}>Yenile</button>
      <Table title="Ajan başına" rows={view.byAgent} />
      <Table title="Proje başına" rows={view.byProject} />
    </section>
  );
}
