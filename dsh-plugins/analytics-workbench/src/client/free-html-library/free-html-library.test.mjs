/** Compiled React interactions; not a real-browser visual acceptance claim. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';
import { createFreeHtmlLibraryStore } from './store.mjs';
import { createMockPageAdapters } from './mock-adapters.mjs';
import { createHostPageStore } from './create-host-page-store.mjs';
import { AGENT_PACKAGE, createIsolatedFetch } from './p12-http-fakes.mjs';

const plugin = fileURLToPath(new URL('../../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const React = web('react'), { createRoot } = web('react-dom/client');
const act = React.act ?? web('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const outfile = join(plugin, 'lib/test-free-html-library.mjs');
await createRequire(web.resolve('vite/package.json'))('esbuild').build({
  absWorkingDir: plugin, entryPoints: ['src/client/free-html-library/FreeHtmlLibraryApp.tsx'], outfile, bundle: true,
  format: 'esm', platform: 'browser', target: 'es2022', jsx: 'automatic',
  external: ['react', 'react/jsx-runtime', 'react-dom'], logLevel: 'silent',
});
const { FreeHtmlLibraryApp } = await import(pathToFileURL(outfile).href);

async function domFixture(t) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318', pretendToBeVisual: true });
  const globals = ['window', 'document', 'HTMLElement', 'Element', 'SVGElement', 'ShadowRoot', 'getComputedStyle', 'IS_REACT_ACT_ENVIRONMENT'];
  const before = globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
  for (const key of globals) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
    value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : key === 'getComputedStyle' ? dom.window.getComputedStyle.bind(dom.window) : dom.window[key] });
  const root = createRoot(dom.window.document.querySelector('#root'));
  t.after(async () => { await act(async () => root.unmount()); dom.window.close();
    for (const [key, descriptor] of before) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; } });
  return {
    root, doc: dom.window.document,
    render: element => act(async () => root.render(element)),
    click: selector => act(async () => { const button = dom.window.document.querySelector(selector); assert.ok(button, selector); button.click(); }),
    type: (selector, value) => act(async () => {
      const field = dom.window.document.querySelector(selector);
      field.value = value;
      field.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    }),
  };
}

const theme = { subscribe: () => () => {}, getSnapshot: () => 'dark' };

test('home uses NL input as the only visual anchor and keeps native chat', async t => {
  const ui = await domFixture(t);
  const store = createFreeHtmlLibraryStore();
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {} }));
  assert.ok(ui.doc.querySelector('[data-testid="fhl-prompt"]'));
  assert.ok(ui.doc.querySelector('[data-testid="fhl-native-chat"]'));
  assert.match(ui.doc.querySelector('[data-testid="fhl-empty"]').textContent, /生成后页面会保存在这里/);
  assert.equal(ui.doc.querySelector('[data-testid="fhl-home"] .sm-fhl-recent li'), null);
  assert.equal(ui.doc.querySelectorAll('[data-testid="fhl-examples"] button').length, 3);
  assert.doesNotMatch(ui.doc.body.textContent, /第二聊天|新 Agent|Router/);
});

test('generate to preview stays free HTML; browse does not show selection chrome', async t => {
  const ui = await domFixture(t);
  const store = createFreeHtmlLibraryStore();
  let native = 0;
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() { native += 1; } }));
  await ui.click('[data-testid="fhl-examples"] button');
  await ui.click('[data-testid="fhl-generate"]');
  assert.ok(ui.doc.querySelector('[data-testid="fhl-iframe"]'));
  assert.match(ui.doc.querySelector('[data-testid="fhl-iframe"]').getAttribute('srcdoc') || ui.doc.querySelector('[data-testid="fhl-iframe"]').srcdoc, /data-shine-node|<!doctype html>/i);
  assert.equal(ui.doc.querySelector('[data-testid="fhl-selection-chrome"]'), null);
  assert.match(ui.doc.querySelector('[data-testid="fhl-binding"]').textContent, /示例数据/);
  assert.equal(ui.doc.querySelector('[data-testid="fhl-iframe"]').style.pointerEvents, 'auto');
  assert.equal(ui.doc.querySelector('[data-testid="fhl-iframe"]').getAttribute('sandbox'), 'allow-scripts');
  await ui.click('[data-testid="fhl-toggle-mode"]');
  assert.equal(ui.doc.querySelector('[data-testid="fhl-selection-chrome"]'), null);
  assert.equal(ui.doc.querySelector('[data-testid="fhl-iframe"]').style.pointerEvents, 'none');
  await ui.click('[data-testid="fhl-hit-n_title"]');
  assert.match(store.getSnapshot().selection?.label ?? '', /静态元素|精确|标题/);
  await act(async () => { store.selectLocatable({ kind: 'static_element', node_id: 'n_title', mapping: 'valid' }); });
  await act(async () => { store.selectLocatable({ kind: 'dynamic_region', node_id: 'r_chart', mapping: 'valid' }); });
  await act(async () => { store.selectWholePage(); });
  assert.match(store.getSnapshot().selection?.label ?? '', /整页/);
  await act(async () => { store.selectLocatable({ kind: 'static_element', node_id: 'n_missing', mapping: 'stale' }); });
  assert.equal(store.getSnapshot().selection?.stale, true);
  await ui.click('[data-testid="fhl-native-chat"]');
  assert.equal(native, 1);
});

test('D6 confirm is in patch region; cancel and exit-edit do not save', async t => {
  const ui = await domFixture(t);
  const store = createFreeHtmlLibraryStore();
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {} }));
  await act(async () => { store.setPrompt('页'); await store.generate(); });
  const version = store.getSnapshot().current.version;
  await ui.click('[data-testid="fhl-toggle-mode"]');
  await ui.click('[data-testid="fhl-hit-n_title"]');
  await ui.click('[data-testid="fhl-open-ai"]');
  await ui.click('[data-testid="fhl-patch-preview"]');
  assert.ok(ui.doc.querySelector('[data-testid="fhl-patch"]'));
  await ui.click('[data-testid="fhl-cancel-patch"]');
  assert.equal(store.getSnapshot().current.version, version);
  await ui.click('[data-testid="fhl-hit-n_title"]');
  await ui.click('[data-testid="fhl-open-ai"]');
  await ui.click('[data-testid="fhl-patch-preview"]');
  await ui.click('[data-testid="fhl-confirm-patch"]');
  assert.equal(store.getSnapshot().current.version, version + 1);
  await ui.click('[data-testid="fhl-toggle-mode"]');
  assert.equal(store.getSnapshot().current.version, version + 1);
});

test('status spine stays visible for sample/stale and 1280 collapses rail', async t => {
  const ui = await domFixture(t);
  const adapters = createMockPageAdapters({ pages: [{
    page_id: 'page_stale', session_id: 'native_session_fixture', title: '过期页', version: 2,
    binding_state: 'BOUND_STALE', binding_manifest: { bindings: [], result_refs: ['result_fixture_1'] },
    package: createMockPageAdapters().samplePackage(), savedPackage: createMockPageAdapters().samplePackage(),
    dirty: false, updated_at: 1, history: [{ version: 2, title: '过期页', at: 1 }],
  }] });
  const store = createFreeHtmlLibraryStore({ adapters, viewportWidth: 1280 });
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {}, viewportWidth: 1280 }));
  assert.equal(ui.doc.querySelector('[data-testid="fhl-root"]').getAttribute('data-rail'), 'collapsed');
  assert.equal(ui.doc.querySelector('[data-testid="fhl-rail"]'), null);
  await act(async () => { store.openPage('page_stale'); });
  assert.match(ui.doc.querySelector('[data-testid="fhl-binding"]').textContent, /过期/);
  assert.ok(ui.doc.querySelector('[data-testid="fhl-status-spine"]'));
});

test('optional DESIGN.md click does not claim the guide was followed', async t => {
  const ui = await domFixture(t);
  const store = createFreeHtmlLibraryStore();
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {} }));
  await ui.click('[data-testid="fhl-add-design"]');
  assert.equal(store.getSnapshot().designGuide.loaded, false);
  assert.match(store.getSnapshot().designGuide.error, /未读到 DESIGN.md/);
  assert.match(ui.doc.querySelector('[data-testid="fhl-optional-hint"]').textContent, /未读到 DESIGN.md/);
});

test('dirty native-chat leave shows three choices and stay keeps the page', async t => {
  const ui = await domFixture(t);
  let native = 0;
  const store = createFreeHtmlLibraryStore();
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() { native += 1; } }));
  await act(async () => { store.setPrompt('页'); await store.generate(); });
  await act(async () => { store.markLocalDraft({ ...store.getSnapshot().current.package, html: '<p>draft</p>' }); });
  await ui.click('[data-testid="fhl-native-chat"]');
  assert.equal(native, 0);
  assert.ok(ui.doc.querySelector('[data-testid="fhl-leave-prompt"]'));
  await ui.click('[data-testid="fhl-leave-stay"]');
  assert.equal(store.getSnapshot().view, 'workspace');
  assert.equal(native, 0);
  await ui.click('[data-testid="fhl-native-chat"]');
  await ui.click('[data-testid="fhl-leave-save"]');
  assert.equal(native, 1);
  assert.equal(store.getSnapshot().pendingLeaveIntent, null);
});

test('live adapters mount Lane B preview host instead of a raw srcdoc iframe', async t => {
  const ui = await domFixture(t);
  const isolated = createIsolatedFetch({ token: 'library-page-isolated-test-token-32chars' });
  const store = createHostPageStore({
    nativeGenerate: async () => AGENT_PACKAGE,
    documentsHttp: { base: 'http://127.0.0.1:18091', token: 'library-page-isolated-test-token-32chars', fetchImpl: isolated.fetchImpl },
    resultHttp: { base: 'http://127.0.0.1:18091', token: 'library-page-isolated-test-token-32chars', fetchImpl: isolated.fetchImpl },
  });
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {} }));
  await act(async () => { store.setPrompt('页'); await store.generate(); });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  assert.ok(ui.doc.querySelector('[data-testid="fhl-live-preview"]'));
  assert.ok(ui.doc.querySelector('[data-testid="fp-preview-host"]'));
  const frame = ui.doc.querySelector('[data-testid="fhl-iframe"]');
  assert.ok(frame);
  assert.equal(frame.getAttribute('sandbox'), 'allow-scripts');
  assert.equal(frame.hasAttribute('srcdoc') || Boolean(frame.srcdoc), true);
});

test('when the host owns conversation leave, dirty native-chat does not open a second prompt', async t => {
  const ui = await domFixture(t);
  let native = 0;
  const store = createFreeHtmlLibraryStore();
  await ui.render(React.createElement(FreeHtmlLibraryApp, {
    store, themeSource: theme, hostOwnsConversationLeave: true,
    goConversation() { native += 1; },
  }));
  await act(async () => { store.setPrompt('页'); await store.generate(); });
  await act(async () => { store.markLocalDraft({ ...store.getSnapshot().current.package, html: '<p>draft</p>' }); });
  await ui.click('[data-testid="fhl-native-chat"]');
  assert.equal(native, 1);
  assert.equal(ui.doc.querySelector('[data-testid="fhl-leave-prompt"]'), null);
});

test('editMode hover layer is visual-only and keeps iframe pointer events', async t => {
  const ui = await domFixture(t);
  const store = createFreeHtmlLibraryStore();
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {} }));
  await act(async () => { store.setPrompt('页'); await store.generate(); });
  assert.ok(ui.doc.querySelector('[data-testid="fhl-iframe"]'));
  assert.equal(ui.doc.querySelector('[data-testid="html-hover-layer"]'), null);
  assert.equal(ui.doc.querySelector('[data-testid="fhl-preview"]').getAttribute('data-edit-mode'), '0');
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {}, editMode: true }));
  assert.ok(ui.doc.querySelector('[data-testid="html-hover-layer"]'));
  assert.equal(ui.doc.querySelector('[data-testid="fhl-preview"]').getAttribute('data-edit-mode'), '1');
  assert.equal(ui.doc.querySelector('[data-testid="fhl-hit-layer"]'), null);
  const iframe = ui.doc.querySelector('[data-testid="fhl-iframe"]');
  assert.doesNotMatch(iframe.getAttribute('srcdoc') || iframe.srcdoc || '', /cockpit-hover-style|cockpit-hover-runtime/);
  assert.equal(iframe.style.pointerEvents, 'auto');
  assert.equal(store.getSnapshot().selection, null);
  const frameDoc = iframe.contentDocument;
  const node = frameDoc?.querySelector('[data-shine-node="n_title"]');
  if (node) {
    node.dispatchEvent(new ui.doc.defaultView.Event('mouseenter'));
    assert.equal(node.classList.contains('shine-node-hover'), true);
    node.dispatchEvent(new ui.doc.defaultView.Event('mouseleave'));
    assert.equal(node.classList.contains('shine-node-hover'), false);
    node.dispatchEvent(new ui.doc.defaultView.Event('click', { bubbles: true }));
    assert.equal(store.getSnapshot().selection, null);
  }
});

test('permission failure surfaces host recovery copy', async t => {
  const ui = await domFixture(t);
  const store = createFreeHtmlLibraryStore({ adapters: createMockPageAdapters({ fail: { generate: 'FORBIDDEN' } }) });
  await ui.render(React.createElement(FreeHtmlLibraryApp, { store, themeSource: theme, goConversation() {} }));
  await act(async () => { store.setPrompt('仍保留'); });
  await ui.click('[data-testid="fhl-generate"]');
  assert.equal(store.getSnapshot().prompt, '仍保留');
  assert.match(ui.doc.body.textContent, /FORBIDDEN|生成失败|权限|会话|保留/);
});
