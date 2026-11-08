// Pure chat model (no React, no Tauri): everything the chat screen and its side panel show is derived here from what the engine
// returned (session.events, session.models, capability inventory) and from what the person typed. Stream content is untrusted data:
// it only becomes text, a file path label or a number, never an action.
import type { StreamEvent, TurnResult } from './sessionlog';

/** One exchange. `user` is null for a retry (the engine re-ran the last message, the person typed nothing new). */
export type Turn = { n: number | null; user: string | null; result: TurnResult };

export type Item =
  | { t: 'user'; text: string }
  | { t: 'agent'; text: string }
  | { t: 'tool'; tool: string; status: string; detail: string }
  | { t: 'ask'; text: string }
  | { t: 'error'; text: string };

export type Todo = { content: string; status: string };

const MAX_TEXT = 4000;
const cut = (s: string, n = MAX_TEXT): string => (s.length > n ? s.slice(0, n) + '…' : s);
const str = (v: unknown): string => (typeof v === 'string' ? v : typeof v === 'number' ? String(v) : '');
const WRITE_TOOLS = new Set(['edit', 'write', 'patch', 'multiedit']);
const READ_TOOLS = new Set(['read']);

/** Path-like fields tools use in their input; the first string found wins. */
export function pathOf(input: unknown): string {
  if (typeof input !== 'object' || input === null) return '';
  const o = input as Record<string, unknown>;
  return str(o.filePath) || str(o.file_path) || str(o.path) || '';
}

function detailOf(tool: string, input: unknown): string {
  const p = pathOf(input);
  if (p) return cut(p, 200);
  if (typeof input !== 'object' || input === null) return '';
  const o = input as Record<string, unknown>;
  return cut(str(o.pattern) || str(o.command) || str(o.query) || str(o.url) || '', 200);
}

/** Events of every turn, in order, as chat items. The engine's own words only; nothing is invented between them. */
export function itemsOf(turns: Turn[]): Item[] {
  const out: Item[] = [];
  for (const turn of turns) {
    if (turn.user !== null) out.push({ t: 'user', text: turn.user });
    const r = turn.result;
    if (!r) continue;
    for (const e of r.events as StreamEvent[]) {
      if (e.kind === 'message') { const text = str(e.text).trim(); if (text) out.push({ t: 'agent', text: cut(text) }); }
      else if (e.kind === 'tool_call') out.push({ t: 'tool', tool: cut(str(e.tool), 80), status: str(e.status) || '?', detail: detailOf(str(e.tool), e.input) });
      else if (e.kind === 'ask_user') out.push({ t: 'ask', text: 'Ajan bir soru sordu; bu oturumdaki sorular buradan yanıtlanamaz.' });
      else if (e.kind === 'error') out.push({ t: 'error', text: cut(str(e.message) || str(e.text) || 'bilinmeyen hata', 500) });
    }
    if (r.error) out.push({ t: 'error', text: cut(r.error, 500) });
  }
  return out;
}

/** The plan is the agent's own todo list: the last `todowrite` tool call of the session. No such call, no plan. */
export function planOf(turns: Turn[]): Todo[] | null {
  let plan: Todo[] | null = null;
  for (const turn of turns) {
    for (const e of (turn.result?.events ?? []) as StreamEvent[]) {
      const todos = e.kind === 'tool_call' && str(e.tool).toLowerCase() === 'todowrite' ? (e.input as { todos?: unknown } | undefined)?.todos : undefined;
      if (Array.isArray(todos)) {
        const rows = todos.filter((x): x is Record<string, unknown> => typeof x === 'object' && x !== null).map((x) => ({ content: cut(str(x.content), 200), status: str(x.status) || '?' })).filter((x) => x.content);
        if (rows.length) plan = rows;
      }
    }
  }
  return plan;
}

export const compactNumber = (n: number): string => (n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)).replace('.', ',');

/** Files the agent's tools named: changed (edit/write tools, normally denied in chat) and read. Deduplicated, in first-seen order. */
export function filesOf(turns: Turn[]): { changed: string[]; read: string[] } {
  const changed = new Set<string>(), read = new Set<string>();
  for (const turn of turns) {
    for (const e of (turn.result?.events ?? []) as StreamEvent[]) {
      if (e.kind !== 'tool_call') continue;
      const tool = str(e.tool).toLowerCase(), path = pathOf(e.input);
      if (!path) continue;
      if (WRITE_TOOLS.has(tool) && e.status === 'completed') changed.add(cut(path, 300));
      else if (READ_TOOLS.has(tool)) read.add(cut(path, 300));
    }
  }
  return { changed: [...changed], read: [...read] };
}


export function toolCount(turns: Turn[]): number {
  return turns.reduce((n, t) => n + ((t.result?.events ?? []) as StreamEvent[]).filter((e) => e.kind === 'tool_call').length, 0);
}

/** Attached paths travel inside the message text (the engine's session commands take text only); the agent reads them with its own read tool. */
export function withAttachments(text: string, paths: string[]): string {
  return paths.length ? `${text.trimEnd()}\n\nEklenen yollar (okumak için):\n${paths.map((p) => `@${p}`).join('\n')}` : text;
}

/** Attaching the same path twice is one attachment. */
export const addPaths = (cur: string[], picked: string[]): string[] => [...new Set([...cur, ...picked.filter((p) => p.trim())])];

export const baseName = (p: string): string => p.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || p;

export type ModelsView =
  | { kind: 'models'; ids: string[] }
  | { kind: 'empty' }
  | { kind: 'error'; text: string };

/** The engine's `session.models` reply -> a view. Anything not exactly a list of "provider/name" strings is an error, never an empty picker. */
export function modelsView(r: { ok: true; value: unknown } | { ok: false; text: string }): ModelsView {
  if (!r.ok) return { kind: 'error', text: r.text };
  const ids = (r.value as { models?: unknown } | null)?.models;
  if (!Array.isArray(ids) || !ids.every((x) => typeof x === 'string')) return { kind: 'error', text: 'Model listesi beklenen biçimde değil; gösterilmedi.' };
  return ids.length ? { kind: 'models', ids: ids as string[] } : { kind: 'empty' };
}

export type ToolListView =
  | { kind: 'rows'; mcp: string[]; skills: string[] }
  | { kind: 'error'; text: string };

/** The capability inventory reply -> names only. Which of them a chat may use is decided by the engine, not by this list. */
export function toolListView(reply: unknown): ToolListView {
  const r = reply as { ok?: unknown; result?: { capabilities?: unknown }; error?: { message?: string } } | null;
  if (!r || r.ok !== true) return { kind: 'error', text: `Araçlar okunamadı: ${r?.error?.message ?? 'bilinmeyen hata'}` };
  const list = r.result?.capabilities;
  if (!Array.isArray(list)) return { kind: 'error', text: 'Araç listesi beklenen biçimde değil; gösterilmedi.' };
  const names = (kind: string) => [...new Set(list.filter((c): c is { kind: string; name: string } => c?.kind === kind && typeof c.name === 'string').map((c) => c.name))].sort();
  return { kind: 'rows', mcp: names('mcp'), skills: names('skill') };
}
