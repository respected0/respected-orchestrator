import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebglAddon } from '@xterm/addon-webgl';
import '@xterm/xterm/css/xterm.css';
import { PROJECT_ID } from './sessionlog';
import { setConvStore } from './sessionstore';
import { clampSize, fromBase64, keysToBase64, refusalText, terminalFor, type TerminalNote, type TerminalView } from './terminalio';

type Reply<T> = { ok: boolean; result: T; error: { code?: string; message?: string; reason?: string } | null };
const ask = <T,>(cmd: string, payload: Record<string, unknown>): Promise<Reply<T>> => invoke('session_call', { cmd, payload: { project_id: PROJECT_ID, ...payload } });

/** The agent's own terminal interface for one project folder (ADR-035). The terminal lives in its own process: closing this pane, the
 *  app or the engine does not end it; "Terminali kapat" does. */
export function AgentTerminals({ root }: { root: string }) {
  const [list, setList] = useState<TerminalView[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (cmd: string, payload: Record<string, unknown>) => {
    try {
      const r = await ask<unknown>(cmd, payload);
      setNote(r.ok ? null : refusalText(r.error));
      const l = await ask<{ terminals: TerminalView[] }>('terminal.list', {});
      if (l.ok) setList(l.result.terminals);
    } catch { setNote('Motora ulaşılamadı.'); }
  }, []);
  useEffect(() => { void run('terminal.list', {}); }, [run, root]);
  const current = list ? terminalFor(list, root) : null;
  const act = async (cmd: string, payload: Record<string, unknown>) => { setBusy(true); await run(cmd, payload); setBusy(false); };
  return (
    <div className="agentterm">
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        {current ? <>
          <span className="grow mut">{current.agent}{current.alive === false ? ` · bitti (çıkış kodu ${current.exit ?? '?'})` : ''}</span>
          {current.conversation && <button type="button" className="btn sm" disabled={busy} title="Terminali kapatır ve bu oturumun sohbetini açar; sohbet dökümü terminalde yapılanları içermez, ajan kendi oturumunda hatırlar."
            onClick={() => { const back = current.conversation; void act('terminal.kill', { terminal_id: current.id }).then(() => { if (back) setConvStore({ sel: back }); }); }}>Sohbete dön</button>}
          <button type="button" className="btn sm" disabled={busy} onClick={() => void act('terminal.kill', { terminal_id: current.id })}>Terminali kapat</button></>
          : <button type="button" className="btn sm" disabled={busy || list === null} onClick={() => void act('terminal.start', { project_root: root, cols: 120, rows: 30 })}>Ajan terminali aç</button>}
      </div>
      {note && <p role="alert">{note}</p>}
      {current ? <Screen key={current.id} id={current.id} onEnd={() => void run('terminal.list', {})} />
        : <p className="mut">Ajan kendi terminal arayüzüyle bu klasörde açılır ve kendi izin kipiyle çalışır: dosyaları doğrudan değiştirebilir ve komut çalıştırabilir. Terminal, uygulama kapansa da siz kapatana kadar yaşar.</p>}
    </div>
  );
}

/** One terminal on screen. Everything drawn is the program's own bytes, handed to the terminal emulator and to nothing else. */
function Screen({ id, onEnd }: { id: string; onEnd: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const term = new Terminal({ fontFamily: '"Cascadia Mono", Consolas, monospace', fontSize: 13, scrollback: 5000 });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(el);
    // The app's CSP (style-src 'self') blocks the style elements the default renderer adds; the WebGL renderer draws on a canvas and needs none.
    try { term.loadAddon(new WebglAddon()); } catch { term.write('Bu bilgisayarda WebGL açılamadı; terminal doğru çizilemeyebilir.\r\n'); }
    let on = true;
    const send = (cmd: string, payload: Record<string, unknown>) => { void ask(cmd, { terminal_id: id, ...payload }).catch(() => undefined); };
    const typed = term.onData((d) => send('terminal.input', { data: keysToBase64(d) }));
    const resized = term.onResize(({ cols, rows }) => send('terminal.resize', clampSize(cols, rows)));
    const watch = new ResizeObserver(() => { if (on) fit.fit(); });
    watch.observe(el);
    const off = listen<TerminalNote>('terminal-event', ({ payload: n }) => {
      if (!on || n.data.terminal_id !== id) return;
      if (n.event === 'terminal.data') term.write(fromBase64(n.data.data));
      else if (n.event === 'terminal.exit') { term.write(`\r\n[program bitti, çıkış kodu ${n.data.exit}]\r\n`); onEnd(); }
    });
    // listen first, then attach: the output the terminal kept arrives right after the attach and must not be missed
    void off.then(() => invoke('terminal_attach', { projectId: PROJECT_ID, terminalId: id })).then(
      () => { if (on) { fit.fit(); send('terminal.resize', clampSize(term.cols, term.rows)); term.focus(); } },
      () => { if (on) term.write('Terminale bağlanılamadı.\r\n'); });
    return () => {
      on = false;
      watch.disconnect(); typed.dispose(); resized.dispose();
      void off.then((stop) => stop());
      void invoke('terminal_detach', { terminalId: id });
      term.dispose();
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  return <div ref={box} className="xtermbox" />;
}
