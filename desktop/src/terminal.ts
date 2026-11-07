// Terminal render model (B3-03.05). Pure (no React, no Tauri) so it runs under `node --test`.
// The renderer only ever receives plain text lines: escape sequences, control characters and bidi overrides are removed here,
// before anything is drawn, so a program's output can never move the cursor, retitle the window, or hide text.
export const MAX_LINES = 10_000;
export const MAX_LINE_CHARS = 4_096;
export const MAX_PASTE_CHARS = 100_000;
export const MAX_PANES = 4;

type Mode = 'text' | 'esc' | 'csi' | 'osc' | 'str' | 'strEsc' | 'oscEsc' | 'escInter';
// C0 except \t \n (handled), DEL, C1, and the bidirectional controls used for spoofing ("evil\u202etxt.exe").
const PLAIN = /[^\u0000-\u001f\u007f-\u009f\u200e\u200f\u202a-\u202e\u2066-\u2069\u2028\u2029]+/y;
const DROP = /[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u200e\u200f\u202a-\u202e\u2066-\u2069\u2028\u2029]/g;

export type Snapshot = { lines: string[]; partial: string; mode: Mode; dropped: number };

export class TerminalBuffer {
  private lines_: string[] = [];
  private head = 0; // lines before `head` are already dropped; the array is compacted in batches, never per line
  private partial = '';
  private mode: Mode = 'text'; // an escape sequence split across two chunks keeps being swallowed
  dropped = 0;
  private cr = false; // a CR was seen; a following LF makes it a newline, any other char means "overwrite this line"

  write(chunk: string): void {
    PLAIN.lastIndex = 0;
    let i = 0;
    while (i < chunk.length) {
      if (this.mode === 'text' && !this.cr) { // fast path: a run of ordinary characters is appended in one piece
        PLAIN.lastIndex = i;
        const run = PLAIN.exec(chunk);
        if (run) { this.add(run[0]); i += run[0].length; continue; }
      }
      const ch = chunk[i++];
      if (this.mode !== 'text') { this.skip(ch); continue; }
      if (this.cr) {
        this.cr = false;
        if (ch === '\n') { this.newline(); continue; }
        this.partial = ''; // lone CR: cursor returned to column 0, what follows overwrites (progress bars show their last state)
        i--; continue; // handle this character normally now that the line was reset
      }
      if (ch === '\u001b') { this.mode = 'esc'; continue; }
      if (ch === '\r') { this.cr = true; continue; }
      if (ch === '\n') { this.newline(); continue; }
      if (ch === '\b') { this.partial = Array.from(this.partial).slice(0, -1).join(''); continue; }
      if (ch === '\t') { this.add('    '); continue; }
      // any other control character is dropped
    }
  }

  private skip(ch: string): void {
    const c = ch.codePointAt(0)!;
    switch (this.mode) {
      case 'esc':
        if (ch === '[') this.mode = 'csi';
        else if (ch === ']') this.mode = 'osc';
        else if ('PX^_'.includes(ch)) this.mode = 'str'; // DCS, SOS, PM, APC run until ST
        else if (c >= 0x20 && c <= 0x2f) this.mode = 'escInter';
        else this.mode = 'text'; // two-character escape
        break;
      case 'escInter': if (c < 0x20 || c > 0x2f) this.mode = 'text'; break;
      case 'csi': if (c >= 0x40 && c <= 0x7e) this.mode = 'text'; else if (c < 0x20 && c !== 0x1b) this.mode = 'text'; break; // CAN/SUB-like aborts
      case 'osc': if (ch === '\u0007') this.mode = 'text'; else if (ch === '\u001b') this.mode = 'oscEsc'; break;
      case 'oscEsc': this.mode = ch === '\\' ? 'text' : 'osc'; break;
      case 'str': if (ch === '\u001b') this.mode = 'strEsc'; break;
      case 'strEsc': this.mode = ch === '\\' ? 'text' : 'str'; break;
    }
    if (ch === '\u0018' || ch === '\u001a') this.mode = 'text'; // CAN / SUB cancel any sequence
  }

  private add(s: string): void {
    while (this.partial.length + s.length > MAX_LINE_CHARS) { // wrap at the cap: no line is ever longer
      const room = MAX_LINE_CHARS - this.partial.length;
      this.partial += s.slice(0, room); s = s.slice(room);
      this.newline();
    }
    this.partial += s;
  }

  private newline(): void {
    this.lines_.push(this.partial); // `partial` only ever holds visible characters (see PLAIN)
    this.partial = '';
    if (this.lines_.length - this.head > MAX_LINES) { this.head++; this.dropped++; }
    if (this.head >= MAX_LINES) { this.lines_.splice(0, this.head); this.head = 0; }
  }

  get length(): number { return this.lines_.length - this.head + (this.partial ? 1 : 0); }

  /** A slice for drawing; never the whole buffer. */
  window(start: number, count: number): string[] {
    const out = this.lines_.slice(this.head + start, this.head + start + count);
    if (this.partial && out.length < count && this.head + start + out.length >= this.lines_.length) out.push(this.partial);
    return out;
  }

  snapshot(): Snapshot { return { lines: this.lines_.slice(this.head), partial: this.partial, mode: this.mode, dropped: this.dropped }; }

  static restore(s: Snapshot): TerminalBuffer {
    const b = new TerminalBuffer();
    b.lines_ = s.lines.slice(-MAX_LINES); b.partial = s.partial; b.mode = s.mode; b.dropped = s.dropped;
    return b;
  }
}

export type PastePlan = { ok: true; text: string; lines: number; needsConfirm: boolean } | { ok: false; reason: string };

/** What a paste becomes before it may reach a terminal. A newline can run a command, so multi-line text needs an explicit yes, and never auto-submits. */
export function planPaste(raw: string): PastePlan {
  if (typeof raw !== 'string' || raw.length === 0) return { ok: false, reason: 'Yapıştırılacak metin yok.' };
  if (raw.length > MAX_PASTE_CHARS) return { ok: false, reason: 'Metin çok büyük; yapıştırılmadı.' };
  // Removing every ESC also removes the bracketed-paste end marker (ESC[201~), so pasted text cannot break out of paste mode.
  const text = raw.replace(/\r\n?/g, '\n').replace(DROP, '').replace(/\n+$/, '');
  const lines = text.split('\n').length;
  return { ok: true, text, lines, needsConfirm: lines > 1 || text.length > 1_000 };
}

export type PtyStatus = 'verified' | 'source' | 'advertised_missing' | 'unsupported' | string;
export type Pane = { id: string; agent: string };
export type Layout = { panes: Pane[]; splitOptIn: boolean };
export type OpenResult = { ok: true; layout: Layout } | { ok: false; reason: string };

export const EMPTY_LAYOUT: Layout = { panes: [], splitOptIn: false };

/** A pane starts only for an agent whose PTY mode the engine has verified; everything else stays closed with the reason. */
export function openPane(layout: Layout, agent: string, ptyStatus: PtyStatus | undefined, id: string): OpenResult {
  if (ptyStatus !== 'verified') return { ok: false, reason: paneSupportText(agent, ptyStatus) };
  if (layout.panes.some((p) => p.id === id)) return { ok: false, reason: 'Bu bölme zaten açık.' };
  if (layout.panes.length >= 1 && !layout.splitOptIn) return { ok: false, reason: 'Birden çok bölme için önce bölünmüş görünümü açın.' };
  if (layout.panes.length >= MAX_PANES) return { ok: false, reason: `En fazla ${MAX_PANES} bölme açılabilir.` };
  return { ok: true, layout: { ...layout, panes: [...layout.panes, { id, agent }] } };
}

export function closePane(layout: Layout, id: string): Layout {
  return { ...layout, panes: layout.panes.filter((p) => p.id !== id) };
}

export function setSplit(layout: Layout, on: boolean): Layout {
  return on ? { ...layout, splitOptIn: true } : { splitOptIn: false, panes: layout.panes.slice(0, 1) };
}

export function gridFor(n: number): { rows: number; cols: number } {
  return n <= 1 ? { rows: 1, cols: 1 } : n === 2 ? { rows: 1, cols: 2 } : { rows: 2, cols: 2 };
}

export function paneSupportText(agent: string, ptyStatus: PtyStatus | undefined): string {
  if (ptyStatus === 'verified') return `${agent}: terminal bölmesi desteklenir.`;
  if (ptyStatus === 'unsupported' || ptyStatus === undefined) return `${agent}: terminal bölmesi bu sürümde desteklenmiyor (kontrollü PTY aracısı henüz yok); başlatılmaz.`;
  return `${agent}: terminal modu doğrulanmadı (${ptyStatus}); başlatılmaz.`;
}
