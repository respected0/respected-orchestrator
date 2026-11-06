import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { ROUTES, type EngineState, type RouteId, closeDecision, nextRoute, routeFromHash, screenView } from './shell';
import './style.css';

function useEngine(): EngineState {
  const [engine, setEngine] = useState<EngineState>({ phase: 'loading' });
  useEffect(() => {
    invoke<{ version: string; healthy: boolean }>('engine_status')
      .then((s) => setEngine({ phase: 'ready', ...s }))
      .catch((e: { error?: { kind?: string }; hint?: string }) =>
        setEngine({ phase: 'problem', kind: e?.error?.kind ?? 'Unknown', hint: e?.hint ?? 'Onarımı çalıştırın.' }));
  }, []);
  return engine;
}

function App() {
  const engine = useEngine();
  const [blocked, setBlocked] = useState<number | null>(null);
  useEffect(() => {
    const un = listen<number>('close-blocked', (e) => setBlocked(e.payload));
    return () => { un.then((f) => f()); };
  }, []);
  const decision = blocked === null ? null : closeDecision('close-window', blocked);
  const [route, setRoute] = useState<RouteId>(routeFromHash(location.hash));
  const links = useRef<Record<string, HTMLAnchorElement | null>>({});
  useEffect(() => {
    const on = () => setRoute(routeFromHash(location.hash));
    addEventListener('hashchange', on);
    return () => removeEventListener('hashchange', on);
  }, []);
  const view = screenView(route, engine);
  const title = ROUTES.find((r) => r.id === route)!.label;
  const badge = engine.phase === 'ready' ? `Motor ${engine.version}` : engine.phase === 'loading' ? 'Motor aranıyor…' : 'Motor yok';
  return (
    <>
      {decision && !decision.allow && (
        <div role="alertdialog" aria-modal="true" aria-labelledby="close-msg" className="modal">
          <p id="close-msg">{decision.message}</p>
          <button autoFocus onClick={() => setBlocked(null)}>{decision.cancel}</button>
          <button onClick={() => invoke('confirm_close')}>{decision.confirm}</button>
        </div>
      )}
      <a className="skip" href="#content">İçeriğe geç</a>
      <header>
        <strong>Respected Orchestrator</strong>
        <span role="status">{badge}</span>
      </header>
      <div className="layout">
        <nav aria-label="Ana gezinme">
          {ROUTES.map((r) => (
            <a
              key={r.id}
              href={`#/${r.id}`}
              ref={(el) => { links.current[r.id] = el; }}
              aria-current={r.id === route ? 'page' : undefined}
              onKeyDown={(e) => {
                const n = nextRoute(r.id, e.key);
                if (n) { e.preventDefault(); links.current[n]?.focus(); }
              }}
            >
              {r.label}
            </a>
          ))}
        </nav>
        <main id="content" tabIndex={-1} aria-labelledby="title">
          <h1 id="title">{title}</h1>
          {view.kind === 'loading' && <p role="status">{view.text}</p>}
          {view.kind === 'error' && <div role="alert"><p>{view.text}</p><p>{view.hint}</p></div>}
          {view.kind === 'empty' && <p>{view.text}</p>}
        </main>
      </div>
    </>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
