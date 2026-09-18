/**
 * T26 (D45) — one cancel/receipt helper for the three entries.
 *
 * Editing cancel, preview cancel and discard-then-navigate used to maintain
 * three copies of the same branch. They now share one receipt check and one
 * local cleanup. The invariant that matters: a receipt that is missing,
 * mismatched, conflicting or failed must keep the current content and a
 * recoverable prompt.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { verifyCancelReceipt, cancelledPatch, cancelTarget, cancelDraft, CANCEL_MESSAGES } from './cancel-receipt.mjs';
import { createLibraryBoardClient } from '../library-board-client.mjs';
import { librarySnapshot as snap, libraryPreview as draft, ok, failed, listOf } from '../../../test/helpers/library-board-fixtures.mjs';

test('a cancel receipt is only accepted when it names the exact thing cancelled', () => {
  assert.deepEqual(verifyCancelReceipt({ status: 'CANCELLED', preview_id: 'p1' }, 'preview_id', 'p1'), { ok: true, value: { status: 'CANCELLED', preview_id: 'p1' } });
  assert.deepEqual(verifyCancelReceipt({ status: 'CANCELLED', preview_id: 'p2' }, 'preview_id', 'p1'), { ok: false, reason: 'mismatched_receipt' });
  assert.deepEqual(verifyCancelReceipt({ status: 'PENDING', preview_id: 'p1' }, 'preview_id', 'p1'), { ok: false, reason: 'missing_receipt' });
  assert.deepEqual(verifyCancelReceipt(null, 'preview_id', 'p1'), { ok: false, reason: 'missing_receipt' });
  assert.deepEqual(verifyCancelReceipt('CANCELLED', 'preview_id', 'p1'), { ok: false, reason: 'missing_receipt' });
  // An edit context is answered on its own id field.
  assert.equal(verifyCancelReceipt({ status: 'CANCELLED', edit_context_id: 'e1' }, 'edit_context_id', 'e1').ok, true);
  assert.equal(verifyCancelReceipt({ status: 'CANCELLED', edit_context_id: 'e2' }, 'edit_context_id', 'e1').ok, false);
});

test('the target precedence is the one the workspace shows', () => {
  const edit = { edit_context_id: 'e1' };
  assert.deepEqual(cancelTarget({ editContext: edit, preview: { preview_id: 'p1' } }), { kind: 'edit', id: 'e1', idField: 'edit_context_id' });
  assert.deepEqual(cancelTarget({ layoutDraft: snap() }), { kind: 'layout', id: null, idField: null });
  assert.deepEqual(cancelTarget({ preview: { preview_id: 'p1' } }), { kind: 'preview', id: 'p1', idField: 'preview_id' });
  assert.equal(cancelTarget({}), null);
});

test('leaving never targets a clean selection, but the workspace cancel still does', () => {
  // D42: a bare edit context is not an obstacle to leaving, so the leave path
  // must not cancel it. The workspace's own Cancel button still may.
  const clean = { editContext: { edit_context_id: 'e1' }, preview: null, confirmationUncertain: false };
  assert.equal(cancelTarget(clean, { forLeave: true }), null, 'a clean selection is not a leave target');
  assert.deepEqual(cancelTarget(clean), { kind: 'edit', id: 'e1', idField: 'edit_context_id' });
  // An edit context that owns a pending patch is real unsaved work either way.
  const dirty = { editContext: { edit_context_id: 'e1' }, preview: { preview_id: 'p1' }, confirmationUncertain: false };
  assert.deepEqual(cancelTarget(dirty, { forLeave: true }), { kind: 'edit', id: 'e1', idField: 'edit_context_id' });
});

test('a layout target clears locally and never posts a cancel', async () => {
  const emitted = [];
  const posted = [];
  const result = await cancelDraft({ kind: 'layout', id: null, idField: null, emit: p => emitted.push(p),
    request: async (op, payload) => { posted.push([op, payload]); return ok({ preview_id: null, status: 'CANCELLED' }); } });
  assert.equal(result, null);
  assert.deepEqual(posted, [], 'a layout draft has no server object, so no request may be sent');
  assert.deepEqual(emitted, [{ layoutDraft: null, incoming: null, message: CANCEL_MESSAGES.layout }]);
});

test('each kind clears exactly its own local state', () => {
  assert.deepEqual(cancelledPatch('edit'), { editContext: null, preview: null, confirmationUncertain: false, incoming: null });
  assert.deepEqual(cancelledPatch('preview'), { preview: null, incoming: null, confirmationUncertain: false });
  assert.deepEqual(cancelledPatch('layout'), { layoutDraft: null, incoming: null });
  assert.throws(() => cancelledPatch('nope'), /未知的取消类型/);
});

test('a failed request clears nothing and reports the retained message', async () => {
  const emitted = [];
  await assert.rejects(
    () => cancelDraft({ kind: 'preview', id: 'p1', idField: 'preview_id', emit: p => emitted.push(p),
      request: async () => failed('TRANSPORT_ERROR') }),
    error => error.message === CANCEL_MESSAGES.retained);
  assert.deepEqual(emitted, [], 'no local state is cleared when the receipt is missing');
});

test('all three entries share one receipt semantics through the client', async t => {
  const saved = snap();
  const pending = draft(snap({ version: 2, content: '待确认' }));
  const context = { schema_version: 'board-edit-context/v1', edit_context_id: 'edit_' + 'c'.repeat(32),
    board_id: saved.spec.board_id, base_version: 1, block_id: 'note', session_id: saved.spec.session_id,
    status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {} };
  let current = null, cancelReply = failed();
  const instance = createLibraryBoardClient(async (_channel, operation) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'list') return ok(listOf(saved));
    if (operation === 'current_edit') return ok(current);
    if (operation === 'select_edit') { current = context; return ok(context); }
    if (operation === 'preview') return ok(pending);
    if (operation === 'cancel_edit') { if (cancelReply.ok) current = null; return cancelReply; }
    if (operation === 'cancel') return cancelReply;
    throw new Error(`unexpected ${operation}`);
  }, { editNative: async () => {} });
  t.after(() => instance.dispose());

  await instance.openBoard(saved.spec.board_id);
  await instance.beginEdit('note');
  // 1. Editing cancel: a missing receipt keeps the selection.
  await instance.cancel();
  assert.equal(instance.getSnapshot().editContext?.edit_context_id, context.edit_context_id);
  assert.match(instance.getSnapshot().message, /保留当前草稿/);
  cancelReply = ok({ edit_context_id: 'wrong', status: 'CANCELLED' });
  await instance.cancel();
  assert.equal(instance.getSnapshot().editContext?.edit_context_id, context.edit_context_id, 'a mismatched receipt clears nothing');
  cancelReply = ok({ edit_context_id: context.edit_context_id, status: 'CANCELLED' });
  await instance.cancel();
  assert.equal(instance.getSnapshot().editContext, null);
  assert.match(instance.getSnapshot().message, /已取消组件编辑/);

  // 2. Preview cancel: same rule, same message shape.
  cancelReply = failed();
  current = { ...context, status: 'PROPOSED', preview_id: pending.preview_id };
  await instance.openPreview(pending.preview_id, context.edit_context_id);
  assert.equal(instance.hasUnsavedChanges(), true);
  const discard = await instance.discardDraft();
  assert.equal(discard.ok, false, 'a failed discard reports instead of throwing');
  assert.equal(instance.getSnapshot().preview?.preview_id, pending.preview_id, 'the draft survives a failed discard');
  assert.equal(instance.hasUnsavedChanges(), true);

  // 3. Discard-then-navigate uses the same helper and the same failure rule.
  const other = snap({ boardId: 'board_other' });
  const navigator = createLibraryBoardClient(async (_channel, operation, payload) => {
    if (operation === 'get') return ok(payload.board_id === 'board_other' ? other : saved);
    if (operation === 'preview') return ok(pending);
    if (operation === 'cancel') return cancelReply;
    throw new Error(`unexpected ${operation}`);
  });
  t.after(() => navigator.dispose());
  await navigator.openPreview(pending.preview_id);
  await navigator.openBoard('board_other');
  await navigator.discardAndNavigate();
  assert.equal(navigator.getSnapshot().saved, null, 'a failed cancel does not navigate');
  assert.equal(navigator.getSnapshot().preview?.preview_id, pending.preview_id);
  cancelReply = ok({ preview_id: pending.preview_id, status: 'CANCELLED' });
  await navigator.discardAndNavigate();
  assert.deepEqual(navigator.getSnapshot().saved, other);
  assert.equal(navigator.getSnapshot().preview, null);
});

test('discarding for a leave never cancels a clean selection (D42)', async t => {
  const saved = snap();
  const context = { schema_version: 'board-edit-context/v1', edit_context_id: 'edit_' + 'e'.repeat(32),
    board_id: saved.spec.board_id, base_version: 1, block_id: 'note', session_id: saved.spec.session_id,
    status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {} };
  const ops = [];
  const instance = createLibraryBoardClient(async (_channel, operation) => {
    ops.push(operation);
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(context);
    if (operation === 'cancel_edit') return ok({ edit_context_id: context.edit_context_id, status: 'CANCELLED' });
    throw new Error(`unexpected ${operation}`);
  }, { editNative: async () => {} });
  t.after(() => instance.dispose());
  await instance.openBoard(saved.spec.board_id);
  await instance.beginEdit('note');
  assert.equal(instance.hasUnsavedChanges(), false, 'a fresh selection is clean');
  ops.length = 0;
  const dropped = await instance.discardDraft();
  assert.deepEqual(dropped, { ok: true }, 'there is nothing to discard');
  assert.deepEqual(ops, [], 'leaving must not call cancel_edit on a clean selection');
  assert.equal(instance.hasActiveEditContext(), true, 'the selection survives, to resume editing');
});

test('a version conflict on cancel is explained as an already-applied draft, not a plain failure', async t => {
  const saved = snap(), pending = draft(snap({ version: 2 }));
  const instance = createLibraryBoardClient(async (_channel, operation) => {
    if (operation === 'get') return ok(saved);
    if (operation === 'preview') return ok(pending);
    if (operation === 'cancel') return { ok: false, error: { code: 'VERSION_CONFLICT', message: '看板版本已变化，请重新读取后预览；原版本未被覆盖。' } };
    throw new Error(`unexpected ${operation}`);
  });
  t.after(() => instance.dispose());
  await instance.openBoard(saved.spec.board_id);
  await instance.openPreview(pending.preview_id);
  const result = await instance.discardDraft();
  assert.equal(result.ok, false);
  assert.match(result.message, /草稿已保存.*不能通过取消撤销.*核对保存结果/);
  assert.doesNotMatch(result.message, /原版本未被覆盖/, 'the unrelated conflict wording must not leak through');
  assert.equal(instance.getSnapshot().preview?.preview_id, pending.preview_id);
});
