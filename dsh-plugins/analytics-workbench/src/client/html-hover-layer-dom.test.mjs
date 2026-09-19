/** Compiled React interactions; not a real-browser or visual acceptance claim. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';
import { HOVER_CLASS } from './html-hover-layer.mjs';

const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const React = web('react'), { createRoot } = web('react-dom/client');
const act = React.act ?? web('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const outfile = join(plugin, 'lib/test-html-hover-layer-dom.mjs');
await createRequire(web.resolve('vite/package.json'))('esbuild').build({
  absWorkingDir: plugin, entryPoints: ['src/client/HtmlHoverLayer.tsx'], outfile, bundle: true,
  format: 'esm', platform: 'browser', target: 'es2022', jsx: 'automatic',
  loader: { '.css': 'empty' },
  external: ['react', 'react/jsx-runtime', 'react-dom'], logLevel: 'silent',
});
const { HtmlHoverLayer } = await import(pathToFileURL(outfile).href);

async function domFixture(t) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: 'http://127.0.0.1:4318', pretendToBeVisual: true,
  });
  const globals = ['window', 'document', 'HTMLElement', 'Element', 'SVGElement', 'MutationObserver', 'IS_REACT_ACT_ENVIRONMENT'];
  const before = globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
  for (const key of globals) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
    value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : key === 'MutationObserver' ? dom.window.MutationObserver : dom.window[key] });
  const root = createRoot(dom.window.document.querySelector('#root'));
  t.after(async () => { await act(async () => root.unmount()); dom.window.close();
    for (const [key, descriptor] of before) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; } });
  return { doc: dom.window.document, window: dom.window, render: element => act(async () => root.render(element)) };
}

test('HtmlHoverLayer re-attaches after the iframe node is replaced and does nothing when editMode is off', async t => {
  const ui = await domFixture(t);
  const frameDoc = new JSDOM('<!doctype html><html><body><h2 data-shine-node="title-1">标题</h2></body></html>').window.document;
  function Host({ editMode }) {
    const box = React.useRef(null);
    return React.createElement('div', { ref: box, 'data-testid': 'hover-host' },
      React.createElement(HtmlHoverLayer, { iframeRef: box, editMode }));
  }
  await ui.render(React.createElement(Host, { editMode: false }));
  assert.equal(ui.doc.querySelector('[data-testid="html-hover-layer"]'), null);
  await ui.render(React.createElement(Host, { editMode: true }));
  assert.ok(ui.doc.querySelector('[data-testid="html-hover-layer"]'));
  const host = ui.doc.querySelector('[data-testid="hover-host"]');
  const iframe = ui.doc.createElement('iframe');
  Object.defineProperty(iframe, 'contentDocument', { configurable: true, get() { return frameDoc; } });
  await act(async () => { host.appendChild(iframe); });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  const node = frameDoc.querySelector('[data-shine-node="title-1"]');
  node.dispatchEvent(new ui.window.Event('mouseenter'));
  assert.equal(node.classList.contains(HOVER_CLASS), true);
  node.dispatchEvent(new ui.window.Event('mouseleave'));
  assert.equal(node.classList.contains(HOVER_CLASS), false);
  await ui.render(React.createElement(Host, { editMode: false }));
  node.dispatchEvent(new ui.window.Event('mouseenter'));
  assert.equal(node.classList.contains(HOVER_CLASS), false);
  assert.equal(ui.doc.querySelector('[data-testid="html-hover-layer"]'), null);
});
