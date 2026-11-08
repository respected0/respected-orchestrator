// Small syntax colouring for the file viewer (no dependency). One line at a time: a multi-line comment or string is coloured only on the lines
// where it starts and ends cleanly. shortcut: line-local rules, upgrade to a real tokenizer only if the viewer ever needs exact colouring.
export type Kind = 'comment' | 'string' | 'number' | 'keyword' | 'plain';
export type Tok = { k: Kind; v: string };

const HASH = new Set(['py', 'sh', 'bash', 'zsh', 'yml', 'yaml', 'toml', 'rb', 'ps1', 'ini', 'cfg', 'conf', 'gitignore', 'editorconfig', 'gitattributes', 'env']);
const SLASH = new Set(['js', 'jsx', 'ts', 'tsx', 'mjs', 'cjs', 'rs', 'go', 'java', 'c', 'h', 'cpp', 'cs', 'css', 'scss', 'kt', 'swift', 'php', 'iss']);
const MARKUP = new Set(['html', 'htm', 'xml', 'svg', 'vue']);
const KEYWORDS = new Set(('const let var function return if else elif for while do break continue switch case default import from export class extends def fn pub use mod struct impl enum trait match async await try catch except finally throw raise new this self ' +
  'true false null None undefined void type interface in of as with lambda yield not and or is static public private protected package where mut ref loop crate').split(' '));

export const extOf = (path: string): string => { const n = path.split(/[\\/]/).pop() ?? ''; const i = n.lastIndexOf('.'); return (i > 0 ? n.slice(i + 1) : n.replace(/^\./, '')).toLowerCase(); };

export function highlightLine(line: string, ext: string): Tok[] {
  const parts = [String.raw`"(?:\\.|[^"\\])*"`, String.raw`'(?:\\.|[^'\\])*'`, '`(?:\\\\.|[^`\\\\])*`'];
  const comment = HASH.has(ext) ? '#.*' : SLASH.has(ext) ? String.raw`//.*|/\*.*?\*/` : MARKUP.has(ext) ? '<!--.*?-->' : '';
  const re = new RegExp(`(${[comment, ...parts].filter(Boolean).join('|')})|(\\b\\d+(?:\\.\\d+)?\\b)|(${MARKUP.has(ext) ? '</?[A-Za-z][\\w-]*|' : ''}\\b[A-Za-z_][A-Za-z_0-9]*\\b)`, 'g');
  const out: Tok[] = [];
  let at = 0;
  for (let m = re.exec(line); m; m = re.exec(line)) {
    if (m.index > at) out.push({ k: 'plain', v: line.slice(at, m.index) });
    const [v, lit, num, word] = m;
    if (lit !== undefined) out.push({ k: comment && new RegExp(`^(?:${comment})$`).test(lit) ? 'comment' : 'string', v });
    else if (num !== undefined) out.push({ k: 'number', v });
    else out.push({ k: word && (KEYWORDS.has(word) || word.startsWith('<')) ? 'keyword' : 'plain', v });
    at = m.index + v.length;
    if (v.length === 0) re.lastIndex++;
  }
  if (at < line.length) out.push({ k: 'plain', v: line.slice(at) });
  return out;
}
