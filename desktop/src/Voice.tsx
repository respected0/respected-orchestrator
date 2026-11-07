import { useEffect, useId, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { chunks, confirmedText, draftView, errorText, highStakesNote, indicator, level, marks, statusView, suggestions, toBase64, toPcm16,
  type Draft, type Failure, type Phase, type Status } from './voicedraft';

const call = (cmd: string, payload: Record<string, unknown> = {}) => invoke<unknown>(cmd === 'voice.status' ? 'read_call' : 'session_call', { cmd, payload });
const failText = (e: unknown) => errorText((e as { error?: { message?: string } })?.error?.message) || 'Motora ulaşılamadı.';

type Open = { stop: () => void; token: string };

/** Push-to-talk task drafting. The microphone is open only between "Konuş" and "Bitir"/"İptal"; audio goes to the local engine, which keeps it in memory
 *  until the local speech program has produced text and then wipes it. The result is an editable DRAFT; this screen has no button that starts, approves
 *  or applies anything — the accepted text can only be copied. Typing is always available. */
export function Voice() {
  const id = useId();
  const [status, setStatus] = useState<Status | Failure | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [lang, setLang] = useState<'tr' | 'en'>('tr');
  const [vocab, setVocab] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [text, setText] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [meter, setMeter] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const open = useRef<Open | null>(null);

  const refresh = () => call('voice.status').then((r) => setStatus(statusView(r))).catch((e) => setStatus({ kind: 'error', text: failText(e), hint: 'Motoru onarın.' }));
  useEffect(() => { refresh(); return () => { open.current?.stop(); }; }, []);

  const end = (why: string | null) => {
    open.current?.stop();
    open.current = null;
    setMeter(0);
    if (why) { setMessage(why); setPhase('error'); } else setPhase('idle');
  };

  async function talk() {
    setMessage(null); setDraft(null); setAccepted(false); setSeconds(0);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true } });
    } catch (e) {
      const denied = (e as DOMException)?.name === 'NotAllowedError';
      end(denied ? 'Mikrofon izni verilmedi; kayıt başlatılmadı.' : 'Mikrofon bulunamadı. Görevi aşağıya yazarak girebilirsiniz.');
      return;
    }
    const track = stream.getAudioTracks()[0];
    const permission = () => (track.readyState === 'live' && track.enabled && !track.muted ? 'granted' : 'denied');
    let token = '';
    try {
      const started = await call('voice.start', { permission: permission() }) as { ok?: boolean; result?: { token: string }; error?: { message?: string } };
      if (!started.ok || !started.result) throw { error: started.error };
      token = started.result.token;
    } catch (e) {
      stream.getTracks().forEach((t) => t.stop());
      end(failText(e));
      return;
    }
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const node = ctx.createScriptProcessor(4096, 1, 1); // AudioWorklet needs a separate bundled module; this is enough for 16 kHz speech
    const startedAt = Date.now();
    let queue = Promise.resolve();
    let dead = false;
    const stop = () => {
      dead = true;
      node.disconnect(); source.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      void ctx.close();
    };
    open.current = { stop, token };
    track.addEventListener('ended', () => { if (!dead) { call('voice.cancel').catch(() => {}); end('Mikrofon kapandı veya izin geri alındı; ses atıldı.'); } });
    node.onaudioprocess = (ev) => {
      if (dead) return;
      const samples = new Float32Array(ev.inputBuffer.getChannelData(0));
      setMeter(level(samples)); setSeconds(Math.floor((Date.now() - startedAt) / 1000));
      const pcm = toPcm16(samples, ctx.sampleRate);
      for (const part of chunks(pcm)) {
        const b64 = toBase64(part);
        queue = queue.then(() => call('voice.feed', { token, chunk: b64, permission: permission() })).then((r) => {
          const reply = r as { ok?: boolean; error?: { message?: string } };
          if (!reply.ok && !dead) end(errorText(reply.error?.message));
        }).catch((e) => { if (!dead) end(failText(e)); });
      }
    };
    source.connect(node); node.connect(ctx.destination);
    setPhase('recording');
    open.current.stop = stop;
    (open.current as Open & { queue?: () => Promise<void> }).queue = () => queue;
  }

  async function finish() {
    const current = open.current as (Open & { queue?: () => Promise<void> }) | null;
    if (!current) return;
    const { token } = current;
    const wait = current.queue?.();
    current.stop();
    open.current = null;
    setMeter(0); setPhase('transcribing');
    try { await wait; } catch { /* a failed chunk already closed the recording */ }
    try {
      const terms = vocab.split(/[\s,]+/).filter(Boolean).slice(0, 200);
      const view = draftView(await call('voice.stop', { token, language: lang, vocabulary: terms }));
      if (view.kind === 'error') { setMessage(`${view.text} ${view.hint}`); setPhase('error'); return; }
      setDraft(view); setText(view.text); setAccepted(false); setPhase('review');
    } catch (e) {
      setMessage(failText(e)); setPhase('error');
    }
  }

  async function cancel() {
    end(null);
    try { await call('voice.cancel'); } catch { /* the engine also wipes when its connection ends */ }
    setMessage('Kayıt iptal edildi; ses atıldı.');
  }

  const ind = indicator(phase);
  const ready = status?.kind === 'status' ? status : null;
  const out = confirmedText(draft, text, accepted);
  const note = draft ? highStakesNote(draft) : null;
  return (
    <section aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>Sesli görev taslağı</h2>
      <p>Konuşmanız <strong>yalnızca taslak metin</strong> üretir. Ses cihazınızdan çıkmaz, diske yazılmaz ve metin siz okuyup onaylamadan hiçbir yere gitmez; ses hiçbir zaman bir çalıştırma, onay veya uygulama komutu sayılmaz.</p>
      {status?.kind === 'error' && <div role="alert"><p>{status.text}</p><p>{status.hint}</p></div>}
      {ready && !ready.enabled && <p role="status">Sesli taslak ayarlarda kapalı (varsayılan). Açmadıkça mikrofon hiç kullanılmaz. Görevi aşağıya yazabilirsiniz.</p>}
      {ready && ready.enabled && !ready.engineReady && <p role="status">Yerel konuşma tanıma programı ayarlı değil; ses metne çevrilemez. Görevi aşağıya yazabilirsiniz.</p>}
      {ready && ready.enabled && ready.engineReady && !ready.networkIsolated && <p className="path">Not: konuşma tanıma programı sizin seçtiğiniz yerel bir programdır; çevrimdışı olduğu burada doğrulanamaz.</p>}
      <p role="status" aria-live="polite" className="mic" data-open={String(ind.micOpen)}>
        <span aria-hidden="true">{ind.micOpen ? '🔴' : '⚪'}</span> {ind.text}{phase === 'recording' ? ` · ${seconds} sn / ${ready?.maxSeconds ?? 60} sn` : ''}
      </p>
      {phase === 'recording' && <progress max={1} value={meter} aria-label="Ses düzeyi" />}
      <div>
        <label>Dil <select value={lang} onChange={(e) => setLang(e.target.value as 'tr' | 'en')} disabled={phase === 'recording'}><option value="tr">Türkçe</option><option value="en">English</option></select></label>{' '}
        <label>Proje sözcükleri <input value={vocab} onChange={(e) => setVocab(e.target.value)} placeholder="pytest, parse_config" disabled={phase === 'recording'} /></label>
      </div>
      <div>
        {phase !== 'recording'
          ? <button type="button" onClick={talk} disabled={!ready?.enabled || !ready.engineReady || phase === 'transcribing'}>Konuş</button>
          : <><button type="button" onClick={finish}>Bitir</button> <button type="button" onClick={cancel}>İptal (sesi at)</button></>}
      </div>
      {message && <div role="alert"><p>{message}</p></div>}
      {draft && (
        <div>
          <h3>Taslak (okuyup düzeltin)</h3>
          <p aria-label="Taslağın işaretli hali">{marks(draft).map((m, i) => (m.hint ? <mark key={i} title={m.hint}>{m.text}</mark> : <span key={i}>{m.text}</span>))}</p>
          {suggestions(draft).length > 0 && <p>Olası yanlış duyulan sözcükler (uygulanmadı): {suggestions(draft).map((c) => `"${c.heard}" → "${c.replaced_with}"`).join(', ')}</p>}
          {note && <div role="alert"><p>{note}</p></div>}
        </div>
      )}
      <label htmlFor={`${id}-t`}>{draft ? 'Düzenlenebilir metin' : 'Görev metni (yazarak girebilirsiniz)'}</label>
      <textarea id={`${id}-t`} rows={5} maxLength={4000} value={text} onChange={(e) => { setText(e.target.value); setAccepted(false); }} />
      <div>
        <button type="button" onClick={() => setAccepted(true)} disabled={!text.trim()}>{draft ? 'Okudum, bu metni onaylıyorum' : 'Bu metni kullan'}</button>{' '}
        <button type="button" onClick={() => { setDraft(null); setText(''); setAccepted(false); setMessage(null); }}>Taslağı sil</button>
      </div>
      {out && (
        <div role="status">
          <p>Onaylanan metin hazır. Bu ekran hiçbir şeyi başlatmaz; metni kopyalayıp görevi başlattığınız yere yapıştırın.</p>
          <button type="button" onClick={() => { navigator.clipboard?.writeText(out).catch(() => {}); }}>Kopyala</button>
        </div>
      )}
    </section>
  );
}
