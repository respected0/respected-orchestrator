// Pure logic of the settings screen (KALAN_ISLER 4.5), testable under `node --test`. The form is drawn from the engine's own schema
// (labels, help, types, limits) and stored values; nothing about a setting is known here. Only what the person changed is sent.

export type Field = { key: string; type: 'enum' | 'string' | 'integer' | 'boolean'; label: string; help?: string; secret?: boolean; enum?: string[]; min?: number; max?: number };
export type Stored = Record<string, unknown>;
/** What is in the form: text for every field but booleans. */
export type Draft = Record<string, string | boolean>;
export type FieldError = { key: string; message: string };

/** The form's starting point: the stored values as the inputs hold them. A secret starts empty (its stored value is never shown or resent). */
export function draftOf(fields: Field[], stored: Stored): Draft {
  const out: Draft = {};
  for (const f of fields) {
    const v = stored[f.key];
    out[f.key] = f.type === 'boolean' ? v === true : f.secret ? '' : v === undefined || v === null ? '' : String(v);
  }
  return out;
}

/** The changed settings as the engine takes them, or the fields that cannot be sent as typed. An untouched field and an empty secret are left out. */
export function changesOf(fields: Field[], stored: Stored, draft: Draft): { changes: Stored; errors: FieldError[] } {
  const changes: Stored = {}, errors: FieldError[] = [];
  const start = draftOf(fields, stored);
  for (const f of fields) {
    const now = draft[f.key];
    if (now === undefined || now === start[f.key]) continue;
    if (f.type === 'boolean') changes[f.key] = now === true;
    else if (f.type === 'integer') {
      const text = String(now).trim();
      if (!/^-?\d+$/.test(text)) errors.push({ key: f.key, message: 'Tam sayı olmalı.' });
      else changes[f.key] = Number(text);
    } else changes[f.key] = String(now);
  }
  return { changes, errors };
}

export type Outcome = { applied?: boolean; declined?: boolean; unchanged?: boolean; errors?: FieldError[] };
/** The shell's answer to a change request, as one line for the person. */
export function outcomeText(o: Outcome): string {
  if (o.applied) return 'Ayarlar kaydedildi.';
  if (o.declined) return 'Onay verilmedi; hiçbir şey değişmedi.';
  if (o.errors?.length) return 'Motor bazı değerleri kabul etmedi; hiçbir şey yazılmadı.';
  return 'Değişen bir ayar yok.';
}
