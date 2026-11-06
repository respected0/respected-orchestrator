import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { invoke } from '@tauri-apps/api/core';

type EngineState =
  | { phase: 'loading' }
  | { phase: 'ready'; version: string; healthy: boolean }
  | { phase: 'problem'; kind: string; hint: string };

function App() {
  const [engine, setEngine] = useState<EngineState>({ phase: 'loading' });
  useEffect(() => {
    invoke<{ version: string; healthy: boolean }>('engine_status')
      .then((s) => setEngine({ phase: 'ready', ...s }))
      .catch((e: { error?: { kind?: string }; hint?: string }) =>
        setEngine({ phase: 'problem', kind: e?.error?.kind ?? 'Unknown', hint: e?.hint ?? 'Run repair.' }));
  }, []);
  return (
    <main>
      <h1>Respected Orchestrator</h1>
      {engine.phase === 'loading' && <p role="status">Motor aranıyor…</p>}
      {engine.phase === 'ready' && <p role="status">Motor {engine.version} — {engine.healthy ? 'sağlıklı' : 'sorunlu'}</p>}
      {engine.phase === 'problem' && <p role="alert">Motora bağlanılamadı ({engine.kind}). {engine.hint}</p>}
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
