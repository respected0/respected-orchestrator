/** Lines starting with "> " are what the user sent; everything else is the agent's own text, shown as plain data. */
export function toMessages(lines: string[]): { who: 'user' | 'agent'; text: string }[] {
  const out: { who: 'user' | 'agent'; text: string }[] = [];
  for (const l of lines) {
    if (l.startsWith('> ')) { out.push({ who: 'user', text: l.slice(2) }); continue; }
    const last = out[out.length - 1];
    if (last?.who === 'agent') last.text += '\n' + l; else if (l.trim()) out.push({ who: 'agent', text: l });
  }
  return out.map((m) => ({ ...m, text: m.text.trim() })).filter((m) => m.text);
}
