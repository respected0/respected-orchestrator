import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { ROUTES, type EngineState, type RouteId, closeDecision, routeFromHash, screenView } from './shell';
import { Capabilities } from './Capabilities';
import { Team, Usage } from './Beta4Screens';
import { PreviewPanel } from './PreviewPanel';
import { Sessions } from './Sessions';
import { Sidebar } from './Sidebar';
import { Flow, Inbox, Projects, Tasks } from './Boards';
import { Page, WindowControls, NavTools, useWidth } from './ui';
import { General, SettingsModal } from './Settings';
import { SETTINGS_ROUTES } from './Sidebar';
import './concept.css';
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

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try { const t = localStorage.getItem('orch.theme'); if (t === 'light' || t === 'dark') return t; } catch { /* storage unavailable */ }
    return 'dark';
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('orch.theme', theme); } catch { /* storage unavailable */ }
  }, [theme]);
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))] as const;
}

function useSide() {
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem('orch.side-hidden') === '1'; } catch { return false; } });
  const toggle = () => setHidden((h) => { const n = !h; try { localStorage.setItem('orch.side-hidden', n ? '1' : '0'); } catch { /* storage unavailable */ } return n; });
  return [hidden, toggle] as const;
}

function App() {
  const [sideHidden, toggleSide] = useSide();
  const [sideW, setSideW] = useWidth('orch.side-w', 252, 200, 480);
  const engine = useEngine();
  const [theme, toggleTheme] = useTheme();
  const [blocked, setBlocked] = useState<number | null>(null);
  useEffect(() => {
    const un = listen<number>('close-blocked', (e) => setBlocked(e.payload));
    return () => { un.then((f) => f()); };
  }, []);
  const decision = blocked === null ? null : closeDecision('close-window', blocked);
  const [route, setRoute] = useState<RouteId>(routeFromHash(location.hash));
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
      <WindowControls />
      <NavTools hidden={sideHidden} toggle={toggleSide} />
      <div className={`layout ${sideHidden ? 'collapsed' : ''}`} style={sideHidden ? undefined : { gridTemplateColumns: `${sideW}px 1fr` }}>
        <Sidebar route={route} theme={theme} toggleTheme={toggleTheme} width={sideW} setWidth={setSideW} />
        <main id="content" tabIndex={-1} aria-labelledby="title" className="chat">
          <h1 id="title" className="sr-only">{title}</h1>
          {view.kind === 'loading' && <p role="status">{view.text}</p>}
          {view.kind === 'error' && <div role="alert"><p>{view.text}</p><p>{view.hint}</p></div>}
          {view.kind === 'empty' && (route === 'sessions' || SETTINGS_ROUTES.includes(route)) && <Sessions />}
          {view.kind === 'empty' && SETTINGS_ROUTES.includes(route) && (
            <SettingsModal route={route} onClose={() => { location.hash = '#/sessions'; }}>
              {route === 'settings' && <General theme={theme} toggleTheme={toggleTheme} status={badge} />}
              {route === 'tasks' && <Tasks />}
              {route === 'inbox' && <Inbox />}
              {route === 'projects' && <Projects />}
              {route === 'flow' && <Flow />}
              {route === 'team' && <Page title="Ajanlar ve ekipler" sub="Kurulu ajanlar, roller ve devirler"><Team /></Page>}
              {route === 'usage' && <Page title="Bütçe ve başarı" sub="Motorun kayıtlı çalışmalarından"><Usage /></Page>}
              {route === 'capabilities' && <Page title="AI araçları" sub="Bu makinede bulunan MCP sunucuları ve beceriler"><Capabilities /></Page>}
            </SettingsModal>
          )}
        </main>
      </div>
    </>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
