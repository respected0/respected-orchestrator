import test from 'node:test';
import assert from 'node:assert/strict';
import { changesOf, draftOf, outcomeText, type Field } from '../src/settingsform.ts';

const fields: Field[] = [
  { key: 'worker', type: 'enum', label: 'Çalışan', enum: ['codex', 'claude'] },
  { key: 'timeout', type: 'integer', label: 'Süre', min: 60, max: 3600 },
  { key: 'preview', type: 'boolean', label: 'Önizleme' },
  { key: 'ports', type: 'string', label: 'Portlar' },
  { key: 'token', type: 'string', label: 'Belirteç', secret: true },
];
const stored = { worker: 'codex', timeout: 900, preview: false, ports: '', token: '***set***' };

test('the form starts from the stored values and never shows a secret', () => {
  assert.deepEqual(draftOf(fields, stored), { worker: 'codex', timeout: '900', preview: false, ports: '', token: '' });
  assert.deepEqual(draftOf(fields, {}), { worker: '', timeout: '', preview: false, ports: '', token: '' });
});

test('only what the person changed is sent, typed as the engine expects', () => {
  const draft = draftOf(fields, stored);
  assert.deepEqual(changesOf(fields, stored, draft), { changes: {}, errors: [] });
  assert.deepEqual(changesOf(fields, stored, { ...draft, timeout: ' 120 ', preview: true, ports: '5173', token: 'yeni' }),
    { changes: { timeout: 120, preview: true, ports: '5173', token: 'yeni' }, errors: [] });
  assert.deepEqual(changesOf(fields, stored, { ...draft, ports: '5173' }).changes, { ports: '5173' }); // an untouched secret is not resent
  assert.deepEqual(changesOf(fields, stored, { ...draft, timeout: '12x' }), { changes: {}, errors: [{ key: 'timeout', message: 'Tam sayı olmalı.' }] });
});

test('each answer of the shell has its own sentence', () => {
  assert.equal(new Set([{ applied: true }, { declined: true }, { unchanged: true }, { errors: [{ key: 'a', message: 'b' }] }].map(outcomeText)).size, 4);
});
