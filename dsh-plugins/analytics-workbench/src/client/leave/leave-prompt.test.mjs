/**
 * The N14 leave prompt, compiled and driven in a DOM (D40/T21, D44/T25).
 *
 * This is a compiled-React interaction test, not a browser acceptance claim.
 * It proves the three choices exist, that Esc and the visible cancel mean
 * "stay", that a pending save/discard cannot be double-submitted from the UI,
 * and that a failure keeps the prompt recoverable with its reason visible.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';
import { createLeaveCoordinator } from './leave-coordinator.mjs';
import { librarySnapshot as snap, libraryPreview as draft } from '../../../test/helpers/library-board-fixtures.mjs';

const plugin = fileURLToPath(new URL('../../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const React = web('react'), { createRoot } = web('react-dom/client');
const act = React.act ?? web('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const outfile = join(plugin, 'lib/test-leave-prompt.mjs');
await createRequire(web.resolve('vite/package.json'))('esbuild').build({
  absWorkingDir: plugin, entryPoints: ['src/client/leave/leave-prompt.tsx'], outfile, bundle: true,
  format: 'esm', platform: 'browser', target: 'es2022', jsx: 'automatic',
  external: ['react', 'react/jsx-runtime', 'react-dom'], logLevel: 'silent',
});
const { LeavePrompt, LeavePromptOverlay } = await import(pathToFileURL(outfile).href);

async function domFixture(t) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4319', pretendToBeVisual: true });
  const globals = ['window', 'document', 'HTMLElement', 'Element', 'SVGElement', 'ShadowRoot', 'getComputedStyle', 'IS_REACT_ACT_ENVIRONMENT'];
  const before = globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
  for (const key of globals) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
    value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : key === 'getComputedStyle' ? dom.window.getComputedStyle.bind(dom.window) : dom.window[key] });
  const root = createRoot(dom.window.document.querySelector('#root'));
  t.after(async () => {
    // Drain pending work before unmounting, then restore the globals only once
    // nothing is still rendering — otherwise a later test sees a torn-down
    // `window` while React is mid-commit.
    await act(async () => { await Promise.resolve(); });
    await act(async () => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of before) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
  });
  /**
   * The coordinator updates React state synchronously, then finishes its
   * transaction in microtasks. So the *synchronous* trigger runs inside `act`
   * (letting React flush that update), and the async remainder is drained
   * afterwards — awaiting the whole transaction inside `act` would re-enter
   * React's own act queue.
   */
  const flush = async () => { await act(async () => { await Promise.resolve(); }); };
  const trigger = async fn => { await act(async () => { fn(); }); await flush(); };
  return { root, doc: dom.window.document, render: element => act(async () => root.render(element)), flush, trigger,
    escape: () => trigger(() => dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))),
    click: selector => {
      const node = dom.window.document.querySelector(selector);
      assert.ok(node, `missing ${selector}`);
      return trigger(() => node.click());
    } };
}

/**
 * A coordinator over controllable fakes. A successful save/discard clears the
 * draft here, exactly as the real client does: the coordinator re-reads the
 * predicate after resolving, so a fake that left the draft behind would
 * (correctly) be reported as a stay.
 */
function coordinatorFor(state, { save, discard } = {}) {
  const log = [];
  const coordinator = createLeaveCoordinator({
    snapshot: () => state,
    beginEpoch: kind => ({ epoch: 1, kind, signal: new AbortController().signal, abort() {} }),
    save: async () => {
      log.push('save');
      const result = save ?? { ok: true };
      if (result.ok) { state.preview = null; state.layoutDraft = null; }
      return result;
    },
    discard: async () => {
      log.push('discard');
      const result = discard ?? { ok: true };
      if (result.ok) { state.preview = null; state.layoutDraft = null; }
      return result;
    },
    navigate: async intent => { log.push(`navigate:${intent.kind}`); },
  });
  return { coordinator, log };
}

test('the prompt is absent until a leave intent needs it', async t => {
  const ui = await domFixture(t);
  const { coordinator } = coordinatorFor({ preview: null });
  await ui.render(React.createElement(LeavePrompt, { coordinator, pageName: '经营复盘' }));
  assert.equal(ui.doc.querySelector('[data-testid=leave-prompt]'), null);
});

test('a dirty page shows all three choices, the page name and the reasons', async t => {
  const ui = await domFixture(t);
  const saved = snap();
  const moved = structuredClone(saved);
  moved.spec.blocks[0].layout = { ...moved.spec.blocks[0].layout, y: 6 };
  const { coordinator } = coordinatorFor({ preview: draft(), layoutDraft: moved, saved });
  await ui.render(React.createElement(LeavePrompt, { coordinator, pageName: '经营复盘' }));
  await ui.trigger(() => { void coordinator.request({ kind: 'conversation' }); });
  const prompt = ui.doc.querySelector('[data-testid=leave-prompt]');
  assert.ok(prompt, 'the prompt is shown');
  assert.match(prompt.textContent, /经营复盘/, 'the confirmation names the page being left');
  for (const id of ['leave-save', 'leave-discard', 'leave-stay']) assert.ok(ui.doc.querySelector(`[data-testid=${id}]`), id);
  const reasons = ui.doc.querySelector('[data-testid=leave-reasons]').textContent;
  assert.match(reasons, /布局有尚未保存的调整/);
  assert.match(reasons, /有一份尚未确认的修改草稿/);
});

for (const [selector, expected] of [['[data-testid=leave-save]', 'save'], ['[data-testid=leave-discard]', 'discard']]) {
  test(`${selector} performs ${expected} then navigates once`, async t => {
    const ui = await domFixture(t);
    const { coordinator, log } = coordinatorFor({ preview: draft() });
    await ui.render(React.createElement(LeavePrompt, { coordinator }));
    await ui.trigger(() => { void coordinator.request({ kind: 'library', id: 'board_other' }); });
    await ui.click(selector);
    assert.deepEqual(log, [expected, 'navigate:library'], `${selector} must ${expected} then navigate once`);
    assert.equal(ui.doc.querySelector('[data-testid=leave-prompt]'), null, 'the prompt closes after resolving');
  });
}

test('stay performs neither save nor discard, and does not navigate', async t => {
  const ui = await domFixture(t);
  const { coordinator, log } = coordinatorFor({ preview: draft() });
  await ui.render(React.createElement(LeavePrompt, { coordinator }));
  await ui.trigger(() => { void coordinator.request({ kind: 'library', id: 'board_other' }); });
  await ui.click('[data-testid=leave-stay]');
  assert.deepEqual(log, [], 'staying performs neither save nor discard, and does not navigate');
  assert.equal(ui.doc.querySelector('[data-testid=leave-prompt]'), null);
});

test('Esc means stay: it never saves and never discards', async t => {
  const ui = await domFixture(t);
  const { coordinator, log } = coordinatorFor({ preview: draft() });
  await ui.render(React.createElement(LeavePrompt, { coordinator }));
  await ui.trigger(() => { void coordinator.request({ kind: 'close' }); });
  await ui.escape();
  assert.deepEqual(log, [], 'Esc is not a save and not a discard');
  assert.equal(ui.doc.querySelector('[data-testid=leave-prompt]'), null);
});

test('a failed save keeps the prompt open with the failure message and the reason', async t => {
  const ui = await domFixture(t);
  const { coordinator } = coordinatorFor({ preview: draft() }, { save: { ok: false, reason: 'conflict' } });
  await ui.render(React.createElement(LeavePrompt, { coordinator }));
  await ui.trigger(() => { void coordinator.request({ kind: 'conversation' }); });
  await ui.click('[data-testid=leave-save]');
  const prompt = ui.doc.querySelector('[data-testid=leave-prompt]');
  assert.ok(prompt, 'a failed save leaves the prompt recoverable rather than navigating');
  assert.match(prompt.textContent, /保存冲突/, 'the failure is explained');
  assert.match(ui.doc.querySelector('[data-testid=leave-reasons]').textContent, /尚未确认的修改草稿/, 'the draft is still there');
  assert.ok(ui.doc.querySelector('[data-testid=leave-save]'), 'the user can retry');
});

test('a failed discard keeps the prompt open and the draft intact', async t => {
  const ui = await domFixture(t);
  const { coordinator } = coordinatorFor({ preview: draft() }, { discard: { ok: false, message: '未取得取消回执，保留当前草稿。' } });
  await ui.render(React.createElement(LeavePrompt, { coordinator }));
  await ui.trigger(() => { void coordinator.request({ kind: 'library', id: 'board_other' }); });
  await ui.click('[data-testid=leave-discard]');
  assert.ok(ui.doc.querySelector('[data-testid=leave-prompt]'));
  assert.match(ui.doc.querySelector('[data-testid=leave-message]').textContent, /保留当前草稿/);
});

test('a pending action disables every choice, so a double click cannot submit twice', async t => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const ui = await domFixture(t);
  const state = { preview: draft(), layoutDraft: null };
  const log = [];
  const coordinator = createLeaveCoordinator({
    snapshot: () => state,
    beginEpoch: kind => ({ epoch: 1, kind, signal: new AbortController().signal, abort() {} }),
    save: async () => { log.push('save'); await gate; state.preview = null; return { ok: true }; },
    discard: async () => { log.push('discard'); state.preview = null; return { ok: true }; },
    navigate: async intent => { log.push(`navigate:${intent.kind}`); },
  });
  await ui.render(React.createElement(LeavePrompt, { coordinator }));
  await ui.trigger(() => { void coordinator.request({ kind: 'library', id: 'board_other' }); });
  await ui.click('[data-testid=leave-save]');
  const saving = coordinator.getSnapshot().status;
  assert.equal(saving, 'saving');
  for (const id of ['leave-save', 'leave-discard', 'leave-stay']) {
    assert.equal(ui.doc.querySelector(`[data-testid=${id}]`).disabled, true, `${id} is disabled while the save is pending`);
  }
  assert.match(ui.doc.querySelector('[data-testid=leave-save]').textContent, /正在保存/);
  release();
  await ui.flush();
  assert.deepEqual(log, ['save', 'navigate:library'], 'the save and the navigation each happened once');
});

test('the overlay seat names the page from the library snapshot', async t => {
  const ui = await domFixture(t);
  const saved = snap();
  const { coordinator } = coordinatorFor({ preview: draft() });
  const library = { getSnapshot: () => ({ preview: null, layoutDraft: null, saved }), subscribe: () => () => {} };
  await ui.render(React.createElement(LeavePromptOverlay, { coordinator, library }));
  assert.equal(ui.doc.querySelector('[data-testid=leave-prompt]'), null, 'idle renders nothing');
  await ui.trigger(() => { void coordinator.request({ kind: 'conversation' }); });
  assert.match(ui.doc.querySelector('[data-testid=leave-prompt]').textContent, /合成经营看板/,
    'the page name comes from the current snapshot');
});

test('an un-vetoable host panel switch still advances the navigation epoch', async t => {
  const ui = await domFixture(t);
  const saved = snap();
  let epoch = 0;
  const state = { preview: null };
  const coordinator = createLeaveCoordinator({
    snapshot: () => state,
    beginEpoch: kind => { epoch += 1; return { epoch, kind, signal: new AbortController().signal, abort() {} }; },
    save: async () => ({ ok: true }),
    discard: async () => ({ ok: true }),
    navigate: async () => {},
  });
  const library = { getSnapshot: () => ({ preview: null, layoutDraft: null, saved }), subscribe: () => () => {} };
  // The host reports the selection change; the plugin can observe but not veto.
  const panel = { current: null };
  const usePanelInfo = select => select({ activePanelId: panel.current });
  const render = () => ui.render(React.createElement(LeavePromptOverlay, { coordinator, library, usePanelInfo }));
  await render();
  const before = epoch;
  panel.current = 'cockpit';
  await render();
  await ui.flush();
  assert.ok(epoch > before, 'observing the host switch advanced the epoch');
  assert.equal(coordinator.getSnapshot().status, 'idle', 'a clean page is not prompted by an observed switch');
});
