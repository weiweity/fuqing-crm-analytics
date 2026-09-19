/** Compiled React interactions; not a real-browser or visual acceptance claim. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';

const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const React = web('react'), { createRoot } = web('react-dom/client');
const act = React.act ?? web('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const outfile = join(plugin, 'lib/test-cockpit-sidebar.mjs');
await createRequire(web.resolve('vite/package.json'))('esbuild').build({
  absWorkingDir: plugin, entryPoints: ['src/client/CockpitSidebar.tsx'], outfile, bundle: true,
  format: 'esm', platform: 'browser', target: 'es2022', jsx: 'automatic',
  loader: { '.css': 'empty' },
  external: ['react', 'react/jsx-runtime', 'react-dom'], logLevel: 'silent',
});
const { CockpitSidebar } = await import(pathToFileURL(outfile).href);

async function domFixture(t) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318' });
  const globals = ['window', 'document', 'HTMLElement', 'Element', 'SVGElement', 'IS_REACT_ACT_ENVIRONMENT'];
  const before = globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
  for (const key of globals) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
    value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[key] });
  const root = createRoot(dom.window.document.querySelector('#root'));
  t.after(async () => { await act(async () => root.unmount()); dom.window.close();
    for (const [key, descriptor] of before) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; } });
  return {
    doc: dom.window.document,
    render: element => act(async () => root.render(element)),
  };
}

test('closing the sidebar unmounts the context immediately; busy disables board tools', async t => {
  const ui = await domFixture(t);
  const events = { close: 0, layout: 0, rollback: 0 };
  await ui.render(React.createElement(CockpitSidebar, {
    visible: true, busy: true, showBoardTools: true,
    onClose: () => { events.close += 1; },
    onLayout: () => { events.layout += 1; },
    onRollback: () => { events.rollback += 1; },
  }));
  const aside = ui.doc.querySelector('[data-testid="cockpit-sidebar"]');
  assert.ok(aside);
  assert.equal(aside.getAttribute('aria-label'), '编辑产物');
  const layout = ui.doc.querySelector('[data-testid="layout-start"]');
  const rollback = ui.doc.querySelector('[data-testid="library-rollback-previous"]');
  assert.equal(layout.disabled, true);
  assert.equal(rollback.disabled, true);
  layout.click();
  rollback.click();
  assert.deepEqual(events, { close: 0, layout: 0, rollback: 0 });

  await ui.render(React.createElement(CockpitSidebar, {
    visible: true, busy: false, showBoardTools: false,
    onClose: () => { events.close += 1; },
  }));
  assert.ok(ui.doc.querySelector('[data-testid="cockpit-sidebar-close"]'));
  assert.equal(ui.doc.querySelector('[data-testid="layout-start"]'), null);

  await ui.render(React.createElement(CockpitSidebar, {
    visible: false, showBoardTools: false,
    onClose: () => { events.close += 1; },
  }));
  assert.equal(ui.doc.querySelector('[data-testid="cockpit-sidebar"]'), null);

  await ui.render(React.createElement(CockpitSidebar, {
    visible: false, onClose: () => { events.close += 1; },
  }));
  assert.equal(ui.doc.querySelector('[data-testid="cockpit-sidebar"]'), null);
});
