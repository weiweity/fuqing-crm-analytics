/** Compiled composition seam regression. Real native browser evidence is separate. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';
import { createCockpitComposition } from './cockpit-composition.mjs';
import { createLibraryBoardClient } from './library-board-client.mjs';
import { librarySnapshot, ok, listOf } from '../../test/helpers/library-board-fixtures.mjs';
const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const React = web('react'), { createRoot } = web('react-dom/client'), { act } = React;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const outfile = join(plugin, 'lib/test-cockpit-composition.mjs');
await createRequire(web.resolve('vite/package.json'))('esbuild').build({ absWorkingDir: plugin,
  entryPoints: ['src/client/cockpit-composition.tsx'], outfile, bundle: true, format: 'esm', platform: 'browser',
  target: 'es2022', jsx: 'automatic', loader: { '.css': 'empty' },
  external: ['react', 'react/jsx-runtime', 'react-dom'], logLevel: 'silent' });
const { CockpitCompositionOverlay } = await import(pathToFileURL(outfile).href);

test('compiled overlay measures official slot wrappers, preserves draft/identity, supports keyboard width and restores ownership/focus', async () => {
  const dom = new JSDOM('<div id="frame"><aside><button id="opener">驾驶舱</button></aside><div id="center"><div data-slot="main" style="display:contents"><div data-slot="main.conversation" style="display:contents"><div data-phase="hero"><div><div data-conversation-scroll><div data-composer-seat><textarea></textarea></div></div></div></div></div></div></div><div data-rightbar-col></div><div data-shell-overlay><div id="root"></div></div></div>', { pretendToBeVisual: true, url: 'http://127.0.0.1' });
  const globals = ['window','document','HTMLElement','Element','SVGElement','ShadowRoot','MutationObserver','getComputedStyle','requestAnimationFrame','cancelAnimationFrame','IS_REACT_ACT_ENVIRONMENT'];
  const prior = globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
  for (const key of globals) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
    value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : ['getComputedStyle','requestAnimationFrame','cancelAnimationFrame'].includes(key) ? dom.window[key].bind(dom.window) : dom.window[key] });
  const doc = dom.window.document, center = doc.querySelector('#center'), native = doc.querySelector('[data-phase]'), input = doc.querySelector('textarea');
  let width = 1160, frameWidth = 1440, sidebarToggles = 0;
  doc.querySelector('#frame').getBoundingClientRect = () => ({ left: 0, top: 0, width: frameWidth, height: 900 });
  center.getBoundingClientRect = () => ({ left: 280, top: 0, width, height: 900 });
  const captured = new WeakMap();
  dom.window.HTMLElement.prototype.setPointerCapture = function (id) { captured.set(this,id); };
  dom.window.HTMLElement.prototype.hasPointerCapture = function (id) { return captured.get(this) === id; };
  dom.window.HTMLElement.prototype.releasePointerCapture = function () { captured.delete(this); };
  input.value = '保留原生草稿'; doc.querySelector('#opener').focus();
  const saved = librarySnapshot();
  const composition = createCockpitComposition({ sessions: { list: { getSnapshot: () => ({ ids: [saved.spec.session_id], byId: { [saved.spec.session_id]: { id: saved.spec.session_id, retainedBy: { mainView: 1 } } } }), subscribe: () => () => {} }, retain() { assert.fail('unexpected session switch'); } }, layout: { selectPanel() {}, toggleSidebar() { sidebarToggles++; doc.querySelector('#frame').toggleAttribute('data-sidebar-collapsed'); } } });
  const library = createLibraryBoardClient(async (_c, operation) => operation === 'list' ? ok(listOf(saved)) : ok(saved));
  const root = createRoot(doc.querySelector('#root'));
  const frame = async callback => act(async () => { callback?.(); await new Promise(resolve => dom.window.requestAnimationFrame(() => dom.window.requestAnimationFrame(resolve))); });
  try {
    await act(async () => root.render(React.createElement(CockpitCompositionOverlay, { composition, library,
      themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, usePanelInfo: select => select({ activePanelId: null }) })));
    await frame(() => composition.open(saved.spec.session_id));
    assert.equal(doc.querySelector('[data-composition-mode]').dataset.compositionMode, 'split');
    assert.equal(native.style.getPropertyValue('--sm-cockpit-chat-width'), '440px');
    assert.equal(doc.querySelector('textarea'), input);
    const separator = doc.querySelector('[role=separator]'); separator.focus();
    await act(async () => separator.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowLeft', shiftKey: true, bubbles: true })));
    assert.equal(native.style.getPropertyValue('--sm-cockpit-chat-width'), '504px');
    const pointer = async (type, x, buttons = 1) => act(async () => {
      const event = new dom.window.MouseEvent(type, { clientX: x, button: 0, buttons, bubbles: true });
      Object.defineProperty(event, 'pointerId', { value: 1 }); separator.dispatchEvent(event);
    });
    await pointer('pointerdown', 700);
    for (const [x, expected] of [[687, 517], [668, 536], [642, 562]]) {
      await pointer('pointermove', x); assert.equal(separator.getAttribute('aria-valuenow'), String(expected));
    }
    await pointer('pointerup', 642, 0);
    assert.equal(composition.getSnapshot().width, 562);
    await pointer('pointerdown', 642); await pointer('pointermove', 595);
    assert.equal(separator.getAttribute('aria-valuenow'), '592'); // native center minus canvas and divider
    await act(async () => dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })));
    await pointer('pointerup', 595, 0);
    assert.equal(composition.getSnapshot().width, 562);
    for (const cancellation of ['pointercancel', 'lostpointercapture', 'blur', 'buttons-zero']) {
      await pointer('pointerdown', 642); await pointer('pointermove', 742);
      assert.equal(separator.getAttribute('aria-valuenow'), '462');
      if (cancellation === 'blur') await act(async () => dom.window.dispatchEvent(new dom.window.Event('blur')));
      else await pointer(cancellation === 'buttons-zero' ? 'pointermove' : cancellation, 742, 0);
      assert.equal(composition.getSnapshot().width, 562, cancellation);
      assert.equal(captured.has(separator), false, cancellation);
    }
    // Native rightbar consumes center width; never lease or rewrite its DOM.
    const rightbar = doc.querySelector('[data-rightbar-col]'); rightbar.textContent = '原生文件预览';
    width = 1000;
    await frame(() => dom.window.dispatchEvent(new dom.window.Event('resize')));
    assert.equal(separator.getAttribute('aria-valuenow'), '432');
    assert.equal(rightbar.textContent, '原生文件预览'); assert.equal(rightbar.hasAttribute('style'), false);
    width = 1160;
    await frame(() => dom.window.dispatchEvent(new dom.window.Event('resize')));
    assert.equal(separator.getAttribute('aria-valuenow'), '562');
    input.focus();
    await frame(() => composition.toggleChat());
    assert.equal(native.inert, true); assert.equal(doc.activeElement.dataset.testid, 'composition-toggle-chat');
    await frame(() => composition.revealChat());
    assert.equal(native.inert, false); assert.equal(input.value, '保留原生草稿');
    width = 334; frameWidth = 390;
    await frame(() => dom.window.dispatchEvent(new dom.window.Event('resize')));
    assert.equal(doc.querySelector('[data-composition-mode]').dataset.compositionMode, 'chat');
    assert.ok(doc.querySelector('[data-composition-mode]').hasAttribute('inert'));
    assert.equal(native.inert, true);
    await frame(() => doc.querySelector('[aria-label="收起导航，查看驾驶舱"]').click());
    assert.equal(sidebarToggles, 1);
    assert.equal(doc.querySelector('[data-composition-mode]').hasAttribute('inert'), false);
    assert.equal(native.inert, false); assert.equal(input.value, '保留原生草稿');
    await frame(() => composition.showCanvas());
    assert.equal(doc.querySelector('[data-composition-mode]').dataset.compositionMode, 'canvas');
    doc.querySelector('[data-testid=composition-toggle-chat]').focus();
    await frame(() => composition.close());
    assert.equal(native.hasAttribute('data-sm-cockpit-native'), false);
    assert.equal(doc.querySelector('#frame').hasAttribute('data-sm-cockpit-compact'), false);
    assert.equal(doc.querySelector('[data-sm-cockpit-sidebar]'), null);
    assert.equal(native.style.getPropertyValue('--sm-cockpit-chat-width'), '');
    assert.equal(doc.activeElement.id, 'opener'); assert.equal(input.value, '保留原生草稿');
    await frame(() => composition.open(saved.spec.session_id));
    await act(async () => root.unmount());
    assert.equal(native.hasAttribute('data-sm-cockpit-native'), false); assert.equal(doc.querySelector('textarea'), input);
  } finally {
    await act(async () => root.unmount()); composition.dispose(); library.dispose(); dom.window.close();
    for (const [key, descriptor] of prior) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
  }
});
