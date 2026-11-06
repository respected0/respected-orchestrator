// Client mirror of the engine's event journal: snapshot first, then pull `events.since` pages.
export interface EventRecord { seq: number; op: string; run: string | null; type: string }
export interface Snapshot { last_seq: number; state: Record<string, { seq: number; type: string }>; state_hash: string }
export interface Mirror { lastSeq: number; runs: Record<string, { seq: number; type: string }>; needsResync: boolean }

export const fromSnapshot = (s: Snapshot): Mirror => ({ lastSeq: s.last_seq, runs: structuredClone(s.state), needsResync: false });

/** Duplicates (seq <= lastSeq) are ignored; a hole stops the mirror and asks for a new snapshot instead of guessing. */
export function applyEvents(m: Mirror, events: EventRecord[]): Mirror {
  const next: Mirror = { lastSeq: m.lastSeq, runs: { ...m.runs }, needsResync: m.needsResync };
  for (const e of events) {
    if (next.needsResync || e.seq <= next.lastSeq) continue;
    if (e.seq !== next.lastSeq + 1) { next.needsResync = true; continue; }
    next.lastSeq = e.seq;
    if (e.run) next.runs[e.run] = { seq: e.seq, type: e.type };
  }
  return next;
}
