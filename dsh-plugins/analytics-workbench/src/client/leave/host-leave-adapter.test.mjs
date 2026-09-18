/**
 * T22 / T27 (D41, D46) — the real host leave seam.
 *
 * This drives the **actual** `LayoutController` from the pinned DSH
 * 0.1.6-alpha.2 checkout (`ddefc45f`), not a hand-written fake, so the seam
 * claims in the lane report are checkable rather than asserted:
 *
 *   - `selectPanel(id)` is a synchronous setter with no pre-navigation approval
 *     hook: it validates the live `main` registry, then writes. Nothing in the
 *     contract lets a plugin defer or veto that write.
 *   - `beginNavigation()` returns a signal aborted by the next panel selection,
 *     which is what makes the navigation epoch authoritative for reads.
 *   - The sidebar panel row calls `selectPanel` directly from its own onClick,
 *     so a plugin cannot interpose on a native row click. That is the recorded
 *     PARTIAL seam handed to P12.
 *
 * What the plugin CAN guarantee is covered here: every plugin-owned entry
 * submits one leave intent first, the original navigation happens at most once,
 * a failure stays on the page, and a host-originated switch still advances the
 * epoch so stale reads cannot commit.
 *
 * This is a headless seam test against the real host contract. A full pinned
 * DSH browser boot (real iframe/slot mount, touch and phone widths) is P12.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';
import { createLeaveCoordinator } from './leave-coordinator.mjs';
import { createHostLeaveAdapter, OWNED_ENTRIES } from './host-leave-adapter.mjs';
import { createLibraryBoardClient } from '../library-board-client.mjs';
import { librarySnapshot as snap, libraryPreview as draft, ok, failed, listOf } from '../../../test/helpers/library-board-fixtures.mjs';

const plugin = fileURLToPath(new URL('../../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const pin = JSON.parse(await readFile(join(plugin, 'toolchain.json'), 'utf8'));

function git(args) {
  const bins = ['/usr/bin/git', '/opt/homebrew/bin/git', 'git'];
  let last;
  for (const bin of bins) {
    try {
      return execFileSync(bin, args, { cwd: upstream, encoding: 'utf8' }).trim();
    } catch (error) {
      last = error;
      if (error && error.code !== 'ENOENT') throw error;
    }
  }
  throw last;
}

/** The pinned checkout must be the one the toolchain declares, unmodified. */
assert.equal(git(['rev-parse', 'HEAD']), pin.upstream_sha,
  'the host seam must be exercised against the pinned upstream');
assert.equal(git(['status', '--porcelain', '--untracked-files=no']), '',
  'the pinned upstream must not carry local edits');

const { LayoutController } = await import(pathToFileURL(join(upstream, 'packages/client/ui-layout/lib/types/client/service.js')).href);

/** A real LayoutController over a recording panel-actions seat, as ui-layout builds it. */
function host({ registered = ['cockpit', 'staff'] } = {}) {
  const selections = [];
  let activePanelId = null;
  const controller = new LayoutController({
    selectPanel: id => { activePanelId = id; selections.push(id); },
    toggleSidebar() {}, openRightbar() {}, closeRightbar() {},
  }, id => registered.includes(id));
  return { controller, selections, panel: () => activePanelId };
}

/**
 * The plugin's real wiring: one library client, one coordinator over it, and one
 * host adapter that is the coordinator's single navigation callback. Composition
 * keeps display only (D44).
 */
function wiring(t, { dispatch, host: seam } = {}) {
  const calls = [];
  const library = createLibraryBoardClient(async (channel, operation, payload) => {
    assert.equal(channel, '/shine-mage-board');
    calls.push({ operation, payload });
    return dispatch(operation, payload);
  });
  t.after(() => library.dispose());
  const performed = [];
  const coordinator = createLeaveCoordinator({
    snapshot: () => library.getSnapshot(),
    beginEpoch: kind => library.beginNavigation(kind),
    // The client owns the receipt check: it holds the draft and the key.
    save: () => library.saveForLeave(),
    discard: () => library.discardDraft(),
    navigate: async intent => { performed.push(intent); await adapter.perform(intent); },
  });
  const adapter = createHostLeaveAdapter({ coordinator, layout: seam?.controller });
  t.after(() => adapter.dispose());
  t.after(() => coordinator.dispose());
  return { library, coordinator, adapter, calls, performed };
}

/** An adapter bound to a coordinator, disposed with the test. */
function adapterFor(t, coordinator, layout) {
  const adapter = createHostLeaveAdapter({ coordinator, layout });
  t.after(() => adapter.dispose());
  return adapter;
}

test('the pinned host exposes a synchronous panel setter and a navigation signal, and no approval hook', () => {
  const h = host();
  assert.equal(typeof h.controller.selectPanel, 'function');
  assert.equal(typeof h.controller.beginNavigation, 'function');
  // The contract surface is exactly these methods: nothing named like a
  // pre-navigation approval, veto or intercept exists.
  const surface = Object.getOwnPropertyNames(Object.getPrototypeOf(h.controller)).sort();
  assert.deepEqual(surface, ['beginNavigation', 'closeRightbar', 'constructor', 'dispose', 'openRightbar', 'selectPanel', 'toggleSidebar']);
  for (const name of surface) assert.doesNotMatch(name, /approve|veto|intercept|before|guard|confirm/i);
});

test('a panel selection aborts the previous navigation signal — the epoch can rely on it', () => {
  const h = host();
  const pending = h.controller.beginNavigation();
  assert.equal(pending.aborted, false);
  h.controller.selectPanel('cockpit');
  assert.equal(pending.aborted, true, 'selecting a panel supersedes an in-flight navigation');
  assert.deepEqual(h.selections, ['cockpit']);
});

test('an unregistered panel throws and preserves the current selection', () => {
  const h = host();
  h.controller.selectPanel('cockpit');
  assert.throws(() => h.controller.selectPanel('nope'), /main panel "nope" is not registered/);
  assert.equal(h.panel(), 'cockpit', 'a refused selection leaves the current panel intact');
  assert.deepEqual(h.selections, ['cockpit']);
});

test('a clean cockpit returns to the conversation once, through the real setter', async t => {
  const saved = snap(), h = host();
  const { library, adapter } = wiring(t, { host: h, dispatch: operation => operation === 'get' ? ok(saved) : ok(listOf(saved)) });
  await library.openBoard(saved.spec.board_id);
  assert.equal(adapter.seamAvailable(), true);
  assert.equal(await adapter.request('conversation'), 'navigated');
  assert.deepEqual(h.selections, [null], 'the original navigation happened exactly once');
});

test('a real draft prompts, and only save-then-leave reaches the host setter', async t => {
  const saved = snap(), applied = snap({ version: 2, content: '已保存' }), pending = draft(applied);
  const h = host();
  const { library, coordinator, adapter, calls } = wiring(t, {
    host: h,
    dispatch: operation => {
      if (operation === 'get') return ok(saved);
      if (operation === 'list') return ok(listOf(applied));
      if (operation === 'preview') return ok(pending);
      if (operation === 'confirm') return ok(applied);
      throw new Error(`unexpected ${operation}`);
    },
  });
  await library.openBoard(saved.spec.board_id);
  await library.openPreview(pending.preview_id);
  assert.equal(await adapter.request('conversation'), 'prompt');
  assert.deepEqual(h.selections, [], 'nothing navigates while the prompt is open');
  assert.equal(await coordinator.choose('stay'), 'stayed');
  assert.deepEqual(h.selections, [], 'staying never touches the host setter');

  assert.equal(await adapter.request('conversation'), 'prompt');
  assert.equal(await coordinator.choose('save_and_leave'), 'navigated');
  assert.deepEqual(h.selections, [null], 'the original navigation happens exactly once after the save');
  assert.deepEqual(calls.filter(call => call.operation === 'confirm').map(call => call.payload.key), ['board-confirm:preview_test']);
  assert.deepEqual(library.getSnapshot().saved, applied);
});

test('a failed save leaves the cockpit mounted and the host setter untouched', async t => {
  const saved = snap(), pending = draft(snap({ version: 2 })), h = host();
  const { library, coordinator, adapter } = wiring(t, {
    host: h,
    dispatch: operation => {
      if (operation === 'get') return ok(saved);
      if (operation === 'preview') return ok(pending);
      if (operation === 'confirm') return failed('TRANSPORT_ERROR');
      throw new Error(`unexpected ${operation}`);
    },
  });
  await library.openBoard(saved.spec.board_id);
  await library.openPreview(pending.preview_id);
  assert.equal(await adapter.request('close'), 'prompt');
  assert.equal(await coordinator.choose('save_and_leave'), 'stayed');
  assert.deepEqual(h.selections, [], 'a failed save does not unload the library state');
  assert.deepEqual(library.getSnapshot().preview, pending, 'the draft survives the failed save');
  assert.equal(library.getSnapshot().confirmationUncertain, true);
});

test('a version conflict leaves the cockpit mounted and the draft readable', async t => {
  const saved = snap(), pending = draft(snap({ version: 2 })), h = host();
  const { library, coordinator, adapter } = wiring(t, {
    host: h,
    dispatch: operation => {
      if (operation === 'get') return ok(saved);
      if (operation === 'preview') return ok(pending);
      if (operation === 'confirm') return { ok: false, error: { code: 'VERSION_CONFLICT', message: '看板版本已变化，请重新读取后预览；原版本未被覆盖。' } };
      throw new Error(`unexpected ${operation}`);
    },
  });
  await library.openBoard(saved.spec.board_id);
  await library.openPreview(pending.preview_id);
  assert.equal(await adapter.request('conversation'), 'prompt');
  assert.equal(await coordinator.choose('save_and_leave'), 'stayed');
  assert.deepEqual(h.selections, []);
  assert.deepEqual(library.getSnapshot().preview, pending);
});

test('every owned entry is covered, and a repeated click navigates at most once', async t => {
  const saved = snap(), other = snap({ boardId: 'board_other' }), h = host();
  const { library, adapter, performed } = wiring(t, { host: h, dispatch: () => ok(other) });
  await library.openBoard(saved.spec.board_id);
  for (const entry of OWNED_ENTRIES) {
    assert.equal(await adapter.request(entry), 'navigated', `${entry} must pass through when clean`);
  }
  assert.equal(performed.length, OWNED_ENTRIES.length, 'one navigation per entry, never two');
});

test('a host-originated panel switch advances the epoch and nothing else', async t => {
  // The host already committed this switch; the plugin can only observe. It
  // must NOT submit a leave intent, which would re-issue a navigation for the
  // panel the user just left.
  const saved = snap(), h = host();
  const { library, coordinator } = wiring(t, { host: h, dispatch: () => ok(saved) });
  const before = library.navigationEpoch();
  h.controller.selectPanel('cockpit');
  await adapterFor(t, coordinator).observe('cockpit', null);
  assert.ok(library.navigationEpoch() > before, 'the epoch advanced');
  assert.deepEqual(h.selections, ['cockpit'], 'the host switch is not repeated by the plugin');
  assert.equal(coordinator.getSnapshot().status, 'idle', 'an observed switch never opens the leave prompt');
});

test('an observed switch takes the epoch even while a leave intent is in flight', async t => {
  const saved = snap(), h = host();
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const library = createLibraryBoardClient(async (_c, operation) => operation === 'get' ? ok(saved) : ok(listOf(saved)));
  t.after(() => library.dispose());
  const coordinator = createLeaveCoordinator({
    snapshot: () => library.getSnapshot(),
    beginEpoch: kind => library.beginNavigation(kind),
    save: async () => { await gate; return { ok: true }; },
    discard: async () => ({ ok: true }),
    navigate: async () => {},
  });
  t.after(() => coordinator.dispose());
  await library.openBoard(saved.spec.board_id);
  await library.openPreview(draft(snap({ version: 2 })).preview_id).catch(() => {});
  const adapter = createHostLeaveAdapter({ coordinator, layout: h.controller });
  t.after(() => adapter.dispose());
  const before = library.navigationEpoch();
  await adapter.observe('conversation', 'cockpit');
  assert.ok(library.navigationEpoch() > before,
    'a host switch must advance the epoch even when no leave intent is pending');
  void release;
});

test('perform() actually performs the intent instead of silently no-opping', async t => {
  const h = host();
  const { adapter } = wiring(t, { host: h, dispatch: () => ok(snap()) });
  for (const kind of ['session', 'close', 'conversation']) {
    h.selections.length = 0;
    await adapter.perform({ kind, id: 'asset_x', sessionId: 's2' });
    assert.deepEqual(h.selections, [null], `${kind} must return to the conversation`);
  }
  h.selections.length = 0;
  await adapter.perform({ kind: 'panel', id: 'staff' });
  assert.deepEqual(h.selections, ['staff'], 'a panel switch with an id must select that panel');
  h.selections.length = 0;
  await adapter.perform({ kind: 'panel' });
  assert.deepEqual(h.selections, [null], 'a panel switch without an id returns to the conversation');
  h.selections.length = 0;
  await adapter.perform({ kind: 'library', id: 'asset_x' });
  assert.deepEqual(h.selections, ['cockpit'], 'a library switch keeps the cockpit selected');
});

test('perform() refuses rather than reporting a navigation that never happened', async t => {
  const { adapter } = wiring(t, { dispatch: () => ok(snap()) });
  await assert.rejects(() => adapter.perform({ kind: 'close' }), /宿主导航入口不可用/);
});

test('the native sidebar row cannot be vetoed — the recorded seam limit', async () => {
  // ui-sidebar's PanelRow wires `selectPanel` straight into its onClick. Prove
  // it from the pinned source so the PARTIAL note in the lane report is
  // evidence-backed rather than a claim.
  const row = await readFile(join(upstream, 'packages/client/ui-sidebar/src/client/SidebarRoot.tsx'), 'utf8');
  assert.match(row, /onClick=\{\(\) => \{ selectPanel\(id\) \}\}/,
    'the panel row calls selectPanel directly: no pre-navigation hook exists for a plugin to use');
  const sidebarApply = await readFile(join(upstream, 'packages/client/ui-sidebar/src/client/index.ts'), 'utf8');
  assert.match(sidebarApply, /selectPanel: \(id\) => \{ ctx\.layout\.selectPanel\(id\) \}/,
    'the sidebar passes the host setter straight through');
  const layoutService = await readFile(join(upstream, 'packages/client/ui-layout/src/client/service.ts'), 'utf8');
  assert.match(layoutService, /selectPanel\(panelId: MainPanelId \| null\): void \{/,
    'selectPanel is a synchronous setter');
  assert.doesNotMatch(layoutService, /async selectPanel/, 'there is no await point to interpose on');
  assert.doesNotMatch(layoutService, /onBefore|beforeNavigate|canNavigate|requestLeave/,
    'the pinned host contract has no pre-navigation approval hook');
});
