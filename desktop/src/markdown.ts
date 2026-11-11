// Minimal Markdown for instruction files: headings, lists, quotes, fenced code, inline code, bold, italic, links and rules.
// Raw HTML is never markup here; it stays text in React, so nothing untrusted can become DOM.
export type Inline =
  | { t: 'text'; v: string }
  | { t: 'code'; v: string }
  | { t: 'strong'; v: string }
  | { t: 'em'; v: string }
  | { t: 'link'; v: string; href: string };

export type Block =
  | { t: 'h'; level: number; text: string }
  | { t: 'p'; inlines: Inline[] }
  | { t: 'list'; ordered: boolean; items: Inline[][] }
  | { t: 'code'; lang: string; text: string }
  | { t: 'quote'; inlines: Inline[] }
  | { t: 'hr' };

const SAFE_LINK = /^(https?:|mailto:)/i;

/** Inline syntax only; an unknown link scheme stays literal text. */
export function inline(text: string): Inline[] {
  const out: Inline[] = [];
  const re = /`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let at = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m.index > at) out.push({ t: 'text', v: text.slice(at, m.index) });
    if (m[1] !== undefined) out.push({ t: 'code', v: m[1] });
    else if (m[2] !== undefined) out.push({ t: 'strong', v: m[2] });
    else if (m[3] !== undefined) out.push({ t: 'em', v: m[3] });
    else out.push(SAFE_LINK.test(m[5]) ? { t: 'link', v: m[4], href: m[5] } : { t: 'text', v: m[0] });
    at = m.index + m[0].length;
  }
  if (at < text.length) out.push({ t: 'text', v: text.slice(at) });
  return out.reduce<Inline[]>((acc, n) => {
    const last = acc[acc.length - 1];
    if (n.t === 'text' && last?.t === 'text') last.v += n.v; else acc.push(n);
    return acc;
  }, []);
}

export function parseMarkdown(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const fence = /^```([\w-]*)\s*$/.exec(line);
    if (fence) {
      const body: string[] = [];
      for (i++; i < lines.length && lines[i].trim() !== '```'; i++) body.push(lines[i]);
      i++;
      blocks.push({ t: 'code', lang: fence[1], text: body.join('\n') });
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) { blocks.push({ t: 'h', level: h[1].length, text: h[2].trim() }); i++; continue; }
    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) { blocks.push({ t: 'hr' }); i++; continue; }
    if (/^\s*>\s?/.test(line)) {
      const body: string[] = [];
      for (; i < lines.length && /^\s*>\s?/.test(lines[i]); i++) body.push(lines[i].replace(/^\s*>\s?/, ''));
      blocks.push({ t: 'quote', inlines: inline(body.join(' ')) });
      continue;
    }
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      const ordered = !bullet;
      const items: Inline[][] = [];
      while (i < lines.length) {
        const m = ordered ? /^\s*\d+[.)]\s+(.*)$/.exec(lines[i]) : /^\s*[-*+]\s+(.*)$/.exec(lines[i]);
        if (!m) break;
        items.push(inline(m[1]));
        i++;
      }
      blocks.push({ t: 'list', ordered, items });
      continue;
    }
    const body: string[] = [];
    for (; i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|\s*>|\s*[-*+]\s|\s*\d+[.)]\s|\s*(---|\*\*\*|___)\s*$)/.test(lines[i]); i++) body.push(lines[i].trim());
    blocks.push({ t: 'p', inlines: inline(body.join(' ')) });
  }
  return blocks;
}
