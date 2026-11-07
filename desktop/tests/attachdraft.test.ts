import test from 'node:test';
import assert from 'node:assert/strict';
import { ATTACH_COMMANDS, canAttach, canShare, errorText, listView, previewView, rectFromDrag, stagedView, statusView, toImagePoint, consentText } from '../src/attachdraft.ts';
import { COMMANDS } from '../src/contracts/ipc.ts';

const ok = (result: unknown) => ({ ok: true, result, error: null });
const SHA = 'a'.repeat(64);
const STAGED = { stage_id: 'stg-0123456789abcdef', sha256: SHA, mime: 'image/png', width: 8, height: 4, bytes: 99, metadata_removed_bytes: 12 };
const RUN = 'run-20261108000000-abcdef123456';

test('every attachment command exists in the IPC contract; the renderer lists contain no commit, share or revoke', () => {
  for (const c of ATTACH_COMMANDS) assert.ok((COMMANDS as readonly string[]).includes(c), c);
  for (const c of ['attachment.commit', 'attachment.share', 'attachment.revoke']) assert.ok(!(ATTACH_COMMANDS as readonly string[]).includes(c));
});

test('shapes: anything unexpected is an error view', () => {
  assert.equal(statusView(ok({ enabled: false, max_bytes: 1, max_side: 2 })).kind, 'status');
  assert.equal(statusView(ok({ enabled: 1 })).kind, 'error');
  assert.equal(stagedView(ok(STAGED)).kind, 'staged');
  for (const bad of [{ ...STAGED, stage_id: '../x' }, { ...STAGED, sha256: 'zz' }, { ...STAGED, width: 'a' }]) assert.equal(stagedView(ok(bad)).kind, 'error');
  assert.equal(listView(ok({ attachments: [{ id: 'att-1', width: 1, height: 1, bytes: 1, redacted_regions: 0, expires_at: 1, shared_with_model: false, consent: { state: 'none' } }] })).kind, 'list');
  assert.equal(listView(ok({ attachments: [{ id: 'att-1' }] })).kind, 'error');
});

test('the preview data URL only ever carries png/jpeg base64 from the engine', () => {
  const p = previewView(ok({ ...STAGED, data: 'iVBORw0KGgo=' }));
  assert.equal(p.kind, 'preview');
  assert.match((p as any).url, /^data:image\/png;base64,/);
  for (const bad of [{ ...STAGED, data: 'x' }, { ...STAGED, data: 'a"onerror="x' }, { ...STAGED, mime: 'image/svg+xml', data: 'AAAA' }, { ...STAGED, mime: 'text/html', data: 'AAAA' }]) {
    assert.equal(previewView(ok(bad)).kind, 'error', JSON.stringify(bad).slice(0, 50));
  }
});

test('attaching needs the exact previewed image, the tick and a valid run id', () => {
  const s = stagedView(ok(STAGED)) as any, p = previewView(ok({ ...STAGED, data: 'AAAA' })) as any;
  assert.equal(canAttach(s, p, true, RUN), true);
  assert.equal(canAttach(s, p, false, RUN), false);
  assert.equal(canAttach(s, null, true, RUN), false);
  assert.equal(canAttach(null, p, true, RUN), false);
  assert.equal(canAttach(s, { ...p, sha256: 'b'.repeat(64) }, true, RUN), false);
  assert.equal(canAttach(s, { ...p, stageId: 'stg-ffffffffffffffff' }, true, RUN), false);
  for (const run of ['', 'run-1', '../run-20261108000000-abcdef123456', RUN + '/x']) assert.equal(canAttach(s, p, true, run), false, run);
  assert.equal(canShare(''), false);
  assert.equal(canShare('   '), false);
  assert.equal(canShare('x'.repeat(81)), false);
  assert.equal(canShare(' Acme '), true);
});

test('masks: clamped to the image, stray clicks are not masks, screen points scale to image pixels', () => {
  assert.equal(rectFromDrag(10, 10, 12, 12, 100, 100), null);
  assert.deepEqual(rectFromDrag(50, 60, 10, 20, 100, 100), { x: 10, y: 20, w: 40, h: 40 });
  assert.deepEqual(rectFromDrag(-20, -20, 500, 500, 100, 80), { x: 0, y: 0, w: 100, h: 80 });
  assert.deepEqual(toImagePoint(150, 125, { left: 100, top: 100, width: 100, height: 50 }, 1000, 500), { x: 500, y: 250 });
});

test('native-dialog outcomes and engine codes read as sentences; unknown ones are shown as received', () => {
  assert.match(errorText('Denied'), /Onaylamadınız/);
  assert.match(errorText('Engine("PREVIEW_REQUIRED: the image changed")'), /yeniden önizleyin/);
  assert.match(errorText('WRONG_RUN: x'), /başlamamış/);
  assert.equal(errorText('NEW_CODE: y'), 'NEW_CODE: y');
  assert.match(consentText({ state: 'active', provider: 'Acme' }), /Acme/);
  assert.match(consentText({ state: 'none' }), /paylaşılmıyor/);
});
