import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';

/** Opens one local page in a separate, unprivileged window. Off unless the user enabled it (and listed the port) in the engine settings;
 * every rule is enforced by the shell, so this form only shows what the shell answered. */
export function PreviewPanel() {
  const [url, setUrl] = useState('');
  const [answer, setAnswer] = useState<{ ok: boolean; text: string } | null>(null);
  const open = () => {
    setAnswer(null);
    invoke<string>('preview_open', { url: url.trim() })
      .then((opened) => setAnswer({ ok: true, text: `Açıldı: ${opened}` }))
      .catch((e: unknown) => setAnswer({ ok: false, text: typeof e === 'string' ? e : 'Önizleme açılamadı.' }));
  };
  return (
    <section aria-labelledby="preview-h">
      <h2 id="preview-h">Yerel önizleme</h2>
      <p>
        Varsayılan olarak <strong>kapalıdır</strong>. Açıksa yalnızca ayarlarda listelediğiniz portlardaki <code>http://127.0.0.1:port</code> sayfaları, ayrı ve yetkisiz
        bir pencerede gösterilir. Sayfa güvenilmeyen içerik sayılır: uygulamaya komut gönderemez, çerezleri ve depolamayı paylaşmaz, başka adrese geçemez ve on dakika sonra kapanır. Sayfanın kendi ağ istekleri (sıradan bir tarayıcı sekmesi gibi) engellenmez; yalnızca güvendiğiniz sayfaları açın.
      </p>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); open(); }}>
        <label>Adres <input type="text" aria-label="Önizleme adresi" value={url} placeholder="http://127.0.0.1:5173/" onChange={(e) => setUrl(e.target.value)} /></label>
        <button type="submit">Önizlemeyi aç</button>
      </form>
      {answer && <p role={answer.ok ? 'status' : 'alert'}>{answer.text}</p>}
    </section>
  );
}
