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
import { readFile } from 'node:fs/promises';
import { hasUnsavedChanges, hasActiveEditContext, unsavedReasons, discardableDraft, layoutChanged, DISCARD_CLEARED_KEYS } from './dirty-predicate.mjs';
import { createLibraryBoardClient } from '../library-board-client.mjs';
import { librarySnapshot as snap, libraryPreview as draft, ok } from '../../../test/helpers/library-board-fixtures.mjs';

/** The frozen contract, loaded rather than restated, so drift fails the suite. */
const frozen = JSON.parse(await readFile(new URL('../../../../../docs/hackathon/free-html-cockpit/fixtures/leave-epoch.fixture.json', import.meta.url), 'utf8'));

const clean = { preview: null, layoutDraft: null, confirmationUncertain: false, editContext: null };
const selection = { editContext: { edit_context_id: 'edit_ctx', block_id: 'note' } };
/** A copy of `saved` whose first block has actually been moved. */
const movedCopy = saved => {
  const moved = structuredClone(saved);
  moved.spec.blocks[0].layout = { ...moved.spec.blocks[0].layout, y: 6 };
  return moved;
};

test('the frozen fixture predicates are the ones implemented', () => {
  const saved = snap();
  // The fixture names the reasons, and each must actually be produced.
  assert.deepEqual([...frozen.predicates.hasUnsavedChanges_true].sort(),
    ['confirmationUncertain', 'layout_changed', 'pending_patch_preview'].sort());
  for (const reason of frozen.predicates.hasUnsavedChanges_true) {
    const state = reason === 'layout_changed' ? { ...clean, saved, layoutDraft: movedCopy(saved) }
      : reason === 'pending_patch_preview' ? { ...clean, preview: draft() }
        : { ...clean, confirmationUncertain: true };
    assert.ok(unsavedReasons(state).includes(reason), `${reason} must count as unsaved`);
  }
  // hasUnsavedChanges_false: none of these may prompt.
  assert.deepEqual([...frozen.predicates.hasUnsavedChanges_false].sort(),
    ['clean_selection', 'open_edit_context_only', 'saved_head_matches_draft'].sort());
  assert.equal(hasUnsavedChanges({ ...clean, ...selection }), false, 'open_edit_context_only is clean');
  assert.equal(hasUnsavedChanges(clean), false, 'clean_selection');
  assert.equal(hasUnsavedChanges({ ...clean, saved, layoutDraft: saved }), false, 'saved_head_matches_draft');
  assert.equal(hasUnsavedChanges(null), false);
  // hasActiveEditContext_independent
  assert.equal(frozen.predicates.hasActiveEditContext_independent, true);
  assert.equal(hasActiveEditContext({ ...clean, ...selection }), true);
  assert.equal(hasActiveEditContext(clean), false);
});

test('an uncertain receipt survives a discard, because it is the only proof of what happened', () => {
  // The module's own rule, asserted against its own constant.
  assert.equal(DISCARD_CLEARED_KEYS.includes('confirmationUncertain'), false,
    'a discard must not erase the evidence that a write may have landed');
  assert.deepEqual([...DISCARD_CLEARED_KEYS], ['preview', 'layoutDraft', 'incoming']);
});

test('a partial snapshot is treated as dirty rather than throwing', () => {
  // `request()` runs the predicate on every entry; a throw here would become an
  // unhandled leave failure instead of a prompt or a stay.
  assert.doesNotThrow(() => layoutChanged({ saved: {}, layoutDraft: { spec: {} } }));
  assert.equal(layoutChanged({ saved: {}, layoutDraft: { spec: {} } }), true);
  assert.equal(layoutChanged({ saved: null, layoutDraft: { spec: {} } }), true);
  assert.equal(layoutChanged({ saved: { spec: {} }, layoutDraft: {} }), true);
  assert.equal(layoutChanged({ layoutDraft: null }), false);
  assert.doesNotThrow(() => unsavedReasons({ saved: {}, layoutDraft: { spec: {} }, preview: null }));
});

test('a just-selected element is a clean context: it does not prompt and is not a draft', () => {
  const saved = snap();
  assert.equal(hasUnsavedChanges({ ...clean, ...selection }), false);
  assert.equal(discardableDraft({ ...clean, ...selection }), false, 'a clean selection is not something to discard');
  assert.equal(discardableDraft({ ...clean, preview: draft() }), true);
  assert.equal(discardableDraft({ ...clean, saved, layoutDraft: movedCopy(saved) }), true);
  assert.equal(discardableDraft({ ...clean, saved, layoutDraft: saved }), false);
});

test('a dirty free-HTML page is unsaved work for the host leave coordinator', () => {
  assert.equal(hasUnsavedChanges({ ...clean, htmlUnsaved: true }), true);
  assert.deepEqual(unsavedReasons({ ...clean, htmlUnsaved: true }), ['html_unsaved']);
  assert.equal(discardableDraft({ ...clean, htmlUnsaved: true }), true);
  assert.equal(hasUnsavedChanges({ ...clean, htmlUnsaved: false }), false);
});

test('a layout draft is only dirty once something actually moved', () => {
  const saved = snap();
  assert.equal(hasUnsavedChanges({ ...clean, saved, layoutDraft: saved }), false, 'an untouched copy is not a change');
  assert.deepEqual(unsavedReasons({ ...clean, saved, layoutDraft: movedCopy(saved) }), ['layout_changed']);
  // Without a saved head there is nothing to compare against: a draft is the
  // only copy of the work, so it counts as unsaved rather than being dropped.
  assert.equal(hasUnsavedChanges({ ...clean, layoutDraft: saved }), true);
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
  assert.equal(instance.hasUnsavedChanges(), false, 'entering layout mode copies the head but changes nothing yet');
  instance.updateLayout('note', { x: 0, y: 6, w: 6, h: 6 });
  assert.deepEqual(instance.unsavedReasons(), ['layout_changed']);
  await instance.cancel();
  assert.equal(instance.hasUnsavedChanges(), false);
  assert.deepEqual(calls, ['get'], 'clearing a local layout draft never writes to the server');
});

test('a layout-only draft cannot be reported as saved, because it has no server receipt', async t => {
  const saved = snap(); saved.spec.blocks.push({ ...structuredClone(saved.spec.blocks[0]), block_id: 'neighbour', layout: { x: 6, y: 0, w: 6, h: 5 } });
  const calls = [];
  const instance = createLibraryBoardClient(async (_channel, operation) => {
    calls.push(operation);
    if (operation === 'get') return ok(saved);
    throw new Error(`unexpected ${operation}`);
  });
  t.after(() => instance.dispose());
  await instance.openBoard(saved.spec.board_id);
  instance.beginLayout();
  instance.updateLayout('note', { x: 0, y: 6, w: 6, h: 6 });
  const receipt = await instance.saveForLeave();
  assert.equal(receipt.ok, false, 'there is nothing a "save and leave" could persist yet');
  assert.equal(receipt.reason, 'layout_unsaved');
  assert.deepEqual(calls, ['get'], 'no write is attempted for an unconfirmed layout');
  assert.ok(instance.getSnapshot().layoutDraft, 'the layout draft is still there to check or discard');

  // With no layout change at all, there is genuinely nothing to save.
  const clean = createLibraryBoardClient(async () => ok(saved));
  t.after(() => clean.dispose());
  await clean.openBoard(saved.spec.board_id);
  assert.deepEqual(await clean.saveForLeave(), { ok: true });
});
