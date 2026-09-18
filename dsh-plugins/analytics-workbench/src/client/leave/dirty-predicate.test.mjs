/**
 * T23 (D42) — the dirty-draft predicate, separated from the edit context.
 *
 * The regression this guards is the existing `library-workspace.tsx` behaviour:
 * a just-selected element is treated as a reason to block leaving, and leaving
 * then calls `cancel_edit` on a clean selection. The fixture
 * (`fixtures/leave-epoch.fixture.json`) names both sides explicitly.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { hasUnsavedChanges, hasActiveEditContext, unsavedReasons, discardableDraft } from './dirty-predicate.mjs';
import { createLibraryBoardClient } from '../library-board-client.mjs';
import { librarySnapshot as snap, libraryPreview as draft, ok, listOf } from '../../../test/helpers/library-board-fixtures.mjs';

const clean = { preview: null, layoutDraft: null, confirmationUncertain: false, editContext: null };
const selection = { editContext: { edit_context_id: 'edit_ctx', block_id: 'note' } };

test('the frozen fixture predicates are the ones implemented', () => {
  // hasUnsavedChanges_true
  assert.deepEqual(unsavedReasons({ ...clean, layoutDraft: snap() }), ['layout_changed']);
  assert.deepEqual(unsavedReasons({ ...clean, preview: draft() }), ['pending_patch_preview']);
  assert.deepEqual(unsavedReasons({ ...clean, confirmationUncertain: true }), ['confirmationUncertain']);
  // hasUnsavedChanges_false
  assert.equal(hasUnsavedChanges({ ...clean, ...selection }), false, 'open_edit_context_only is clean');
  assert.equal(hasUnsavedChanges(clean), false);
  assert.equal(hasUnsavedChanges(null), false);
  // hasActiveEditContext_independent
  assert.equal(hasActiveEditContext({ ...clean, ...selection }), true);
  assert.equal(hasActiveEditContext(clean), false);
});

test('a just-selected element is a clean context: it does not prompt and is not a draft', () => {
  assert.equal(hasUnsavedChanges({ ...clean, ...selection }), false);
  assert.equal(discardableDraft({ ...clean, ...selection }), false, 'a clean selection is not something to discard');
  assert.equal(discardableDraft({ ...clean, preview: draft() }), true);
  assert.equal(discardableDraft({ ...clean, layoutDraft: snap() }), true);
});

test('an uncertain receipt counts as unsaved but is not silently discardable', () => {
  const uncertain = { ...clean, preview: draft(), confirmationUncertain: true };
  assert.deepEqual(unsavedReasons(uncertain), ['pending_patch_preview', 'confirmationUncertain']);
  assert.equal(hasUnsavedChanges(uncertain), true);
});

test('the client exposes the same predicate the coordinator and beforeunload read', async t => {
  const saved = snap(), pending = draft(snap({ version: 2, content: '待确认' }));
  const context = { schema_version: 'board-edit-context/v1', edit_context_id: 'edit_' + 'b'.repeat(32),
    board_id: saved.spec.board_id, base_version: 1, block_id: 'note', session_id: saved.spec.session_id,
    status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {} };
  const calls = [];
  let current = null;
  const instance = createLibraryBoardClient(async (_channel, operation) => {
    calls.push(operation);
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(current);
    if (operation === 'select_edit') { current = context; return ok(context); }
    if (operation === 'preview') return ok(pending);
    if (operation === 'cancel_edit') { current = null; return ok({ edit_context_id: context.edit_context_id, status: 'CANCELLED' }); }
    throw new Error(`unexpected ${operation}`);
  }, { editNative: async () => {} });
  t.after(() => instance.dispose());

  await instance.openBoard(saved.spec.board_id);
  assert.equal(instance.hasUnsavedChanges(), false);
  assert.equal(instance.hasActiveEditContext(), false);

  // Selecting an element creates a clean edit context — not unsaved work.
  await instance.beginEdit('note');
  assert.equal(instance.hasActiveEditContext(), true);
  assert.equal(instance.hasUnsavedChanges(), false, 'a fresh selection must not block leaving');
  assert.equal(instance.unsavedReasons().length, 0);

  // A pending patch is real unsaved work.
  current = { ...context, status: 'PROPOSED', preview_id: pending.preview_id };
  await instance.openPreview(pending.preview_id, context.edit_context_id);
  assert.equal(instance.hasUnsavedChanges(), true);
  assert.deepEqual(instance.unsavedReasons(), ['pending_patch_preview']);

  // Cancelling clears both the draft and the context.
  await instance.cancel();
  assert.equal(instance.hasUnsavedChanges(), false);
  assert.equal(instance.hasActiveEditContext(), false);
  void listOf;
});

test('a local layout change is unsaved work; cancelling it clears the predicate without a server write', async t => {
  const saved = snap(); saved.spec.blocks.push({ ...structuredClone(saved.spec.blocks[0]), block_id: 'neighbour', layout: { x: 6, y: 0, w: 6, h: 5 } });
  const calls = [];
  const instance = createLibraryBoardClient(async (_channel, operation) => {
    calls.push(operation);
    if (operation === 'get') return ok(saved);
    throw new Error(`unexpected ${operation}`);
  });
  t.after(() => instance.dispose());
  await instance.openBoard(saved.spec.board_id);
  assert.equal(instance.hasUnsavedChanges(), false);
  instance.beginLayout();
  assert.equal(instance.hasUnsavedChanges(), false, 'entering layout mode is not itself a change');
  instance.updateLayout('note', { x: 0, y: 6, w: 6, h: 6 });
  assert.deepEqual(instance.unsavedReasons(), ['layout_changed']);
  await instance.cancel();
  assert.equal(instance.hasUnsavedChanges(), false);
  assert.deepEqual(calls, ['get'], 'clearing a local layout draft never writes to the server');
});
