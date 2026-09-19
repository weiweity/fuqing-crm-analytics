/**
 * Lane K — the cockpit ENTRY seam (`openCockpitPanel`, D44).
 *
 * The entry must behave differently for a dirty vs a clean page:
 *
 *   - dirty:  the entry submits the same `panel` intent as every other
 *     plugin-owned navigation, so the user sees the three choices instead of
 *     the cockpit switching behind unsaved work. Nothing navigates until a
 *     choice resolves; save-then-leave lands on the cockpit exactly once.
 *   - clean:  the entry keeps the original direct switch. It must NOT take a
 *     navigation epoch, because the tool card gesture (`openPreview` then
 *     `openCockpit`) has already started a preview read — an epoch taken here
 *     would supersede that very read (D43) and the preview would never load.
 *
 * The wiring mirrors `index.tsx` verbatim (one library client, one coordinator,
 * the adapter as the single navigation callback, the composition-aware
 * `navigate` branch), which is what the source assertion in
 * `cockpit-main-panel.test.mjs` pins. Driving the real modules keeps those
 * assertions honest: the wiring below fails if the seam semantics drift.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createLeaveCoordinator } from './leave-coordinator.mjs';
import { createHostLeaveAdapter } from './host-leave-adapter.mjs';
import { createLibraryBoardClient } from '../library-board-client.mjs';
import { librarySnapshot as snap, libraryPreview as draft, ok, listOf } from '../../../test/helpers/library-board-fixtures.mjs';

const COCKPIT_PANEL_ID = 'cockpit';

/** A recording host: selections are the evidence of "navigated". */
function host() {
  const selections = [];
  let activePanelId = null;
  const controller = {
    selectPanel: id => { activePanelId = id; selections.push(id); },
    toggleSidebar() {}, openRightbar() {}, closeRightbar() {},
  };
  return { selections, panel: () => activePanelId, controller };
}

/**
 * The index.tsx wiring under test: cockpit is an independent main panel.
 * `navigate` performs the host panel switch. Composition overlay is not the
 * default cockpit entry.
 */
function wiring(t, { dispatch, host: seam } = {}) {
  const library = createLibraryBoardClient(async (_channel, operation) => dispatch(operation));
  t.after(() => library.dispose());
  const performed = [];
  const leaveCoordinator = createLeaveCoordinator({
    snapshot: () => ({ ...library.getSnapshot(), htmlUnsaved: false }),
    beginEpoch: kind => library.beginNavigation(kind),
    save: () => library.saveForLeave(),
    discard: () => library.discardDraft(),
    navigate: intent => {
      performed.push(intent);
      return adapter.perform(intent);
    },
  });
  const adapter = createHostLeaveAdapter({ coordinator: leaveCoordinator, layout: seam.controller });
  t.after(() => adapter.dispose());
  t.after(() => leaveCoordinator.dispose());

  /** Verbatim index.tsx entry: dirty routes through the intent, clean switches. */
  const openCockpitPanel = () => {
    if (!adapter.seamAvailable()) return false;
    if (hasUnsavedChanges()) {
      void adapter.request('panel', { id: COCKPIT_PANEL_ID }).catch(() => {});
      return true;
    }
    seam.controller.selectPanel(COCKPIT_PANEL_ID);
    return true;
  };
  const hasUnsavedChanges = () => library.getSnapshot().preview !== null;
  return { library, coordinator: leaveCoordinator, adapter, host: seam, performed, openCockpitPanel };
}

test('a clean entry switches directly and takes no epoch', async t => {
  const saved = snap(), h = host();
  let previewReads = 0;
  const w = wiring(t, {
    host: h,
    dispatch: operation => {
      if (operation === 'get') return ok(saved);
      if (operation === 'preview') { previewReads += 1; return ok(draft(snap({ version: 2 }))); }
      return ok(listOf(saved));
    },
  });
  await w.library.openBoard(saved.spec.board_id);
  const before = w.library.navigationEpoch();
  assert.equal(w.openCockpitPanel(), true);
  assert.deepEqual(h.selections, ['cockpit'], 'a clean entry switches directly');
  assert.equal(w.library.navigationEpoch(), before, 'a clean entry must not advance the epoch');
  assert.deepEqual(w.performed, [], 'a clean entry submits no leave intent');
  // A preview read issued right after the entry still lands: the epoch the
  // entry did NOT take is the reason this read is not superseded.
  await w.library.openPreview(draft(snap({ version: 2 })).preview_id);
  assert.equal(previewReads, 1, 'a preview read after a clean entry survives');
});

test('a dirty page prompts; the entry switches only after save resolves', async t => {
  const saved = snap(), applied = snap({ version: 2, content: '已保存' }), pending = draft(applied), h = host();
  const w = wiring(t, {
    host: h,
    dispatch: operation => {
      if (operation === 'get') return ok(saved);
      if (operation === 'list') return ok(listOf(applied));
      if (operation === 'preview') return ok(pending);
      if (operation === 'confirm') return ok(applied);
      throw new Error(`unexpected ${operation}`);
    },
  });
  await w.library.openBoard(saved.spec.board_id);
  await w.library.openPreview(pending.preview_id);
  assert.equal(w.openCockpitPanel(), true, 'the entry returns immediately; the prompt owns the switch');
  assert.deepEqual(h.selections, [], 'nothing navigates while the three choices are open');
  await w.coordinator.choose('stay');
  assert.deepEqual(h.selections, [], 'staying never enters the cockpit');
  assert.equal(w.openCockpitPanel(), true);
  await w.coordinator.choose('save_and_leave');
  assert.deepEqual(h.selections, ['cockpit'], 'the entry lands on the cockpit exactly once, after the save');
  assert.deepEqual(w.library.getSnapshot().saved, applied);
});

test('a dirty page after save lands on the standalone cockpit panel', async t => {
  const saved = snap(), applied = snap({ version: 2, content: '已保存' }), pending = draft(applied);
  const w = wiring(t, {
    host: host(),
    dispatch: operation => {
      if (operation === 'get') return ok(saved);
      if (operation === 'list') return ok(listOf(applied));
      if (operation === 'preview') return ok(pending);
      if (operation === 'confirm') return ok(applied);
      throw new Error(`unexpected ${operation}`);
    },
  });
  await w.library.openBoard(saved.spec.board_id);
  await w.library.openPreview(pending.preview_id);
  assert.equal(w.openCockpitPanel(), true);
  await w.coordinator.choose('save_and_leave');
  assert.equal(w.host.panel(), 'cockpit', 'the entry lands on the independent cockpit page');
});

test('a failed save keeps the page and the prompt recoverable', async t => {
  const saved = snap(), pending = draft(snap({ version: 2 })), h = host();
  const w = wiring(t, {
    host: h,
    dispatch: operation => {
      if (operation === 'get') return ok(saved);
      if (operation === 'preview') return ok(pending);
      if (operation === 'confirm') return { ok: false, error: { code: 'VERSION_CONFLICT', message: '看板版本已变化。' } };
      throw new Error(`unexpected ${operation}`);
    },
  });
  await w.library.openBoard(saved.spec.board_id);
  await w.library.openPreview(pending.preview_id);
  w.openCockpitPanel();
  assert.deepEqual(h.selections, []);
  assert.equal(await w.coordinator.choose('save_and_leave'), 'stayed');
  assert.deepEqual(h.selections, [], 'a failed save does not enter the cockpit');
  assert.deepEqual(w.library.getSnapshot().preview, pending, 'the draft survives');
});
