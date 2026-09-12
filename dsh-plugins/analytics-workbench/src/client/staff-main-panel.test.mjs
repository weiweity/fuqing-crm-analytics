/** Staff panellist is a side path into native conversation. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const plugin = resolve(here, '../..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const webReq = createRequire(join(upstream, 'apps/web/package.json'));
const vite = createRequire(webReq.resolve('vite/package.json'));
const esbuild = vite('esbuild');
const React = webReq('react');
const { createRoot } = webReq('react-dom/client');
const act = typeof React.act === 'function' ? React.act : webReq('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');

const panelSource = await readFile(join(here, 'staff-main-panel.tsx'), 'utf8');
const fixtureSource = await readFile(join(here, '../staff/fixture.mjs'), 'utf8');
const indexSource = await readFile(join(here, 'index.tsx'), 'utf8');

test('staff source is a panellist side path and does not invent a second chat', () => {
  assert.match(panelSource, /STAFF_PANEL_ID = 'staff'/);
  assert.match(panelSource, /返回对话/);
  assert.match(panelSource, /goConversation/);
  assert.match(panelSource, /openPlazaRole/);
  assert.match(indexSource, /sessions\.create/);
  assert.match(panelSource, /STAFF_FIXTURE/);
  assert.match(panelSource, /还没有团队对话/);
  assert.match(panelSource, /企业 SOP 仍在飞书/);
  assert.match(fixtureSource, /增长分析师/);
  assert.doesNotMatch(panelSource, /conversation.view/);
  assert.doesNotMatch(panelSource, /BoardWorkbench/);
  assert.match(indexSource, /id: STAFF_PANEL_ID/);
  assert.match(indexSource, /key: STAFF_PANEL_ID/);
  assert.doesNotMatch(indexSource, /name: 'conversation.view'/);
});

async function loadPanel() {
  await mkdir(join(plugin, 'lib'), { recursive: true });
  const outfile = join(plugin, 'lib/test-staff-main-panel.mjs');
  await esbuild.build({
    absWorkingDir: plugin,
    entryPoints: ['src/client/staff-main-panel.tsx'],
    outfile,
    bundle: true,
    format: 'esm',
    platform: 'browser',
    target: 'es2022',
    jsx: 'automatic',
    external: ['react', 'react/jsx-runtime', 'react-dom', 'react-dom/client'],
    logLevel: 'silent',
  });
  return import(pathToFileURL(outfile).href);
}

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318/' });
  if (typeof dom.window.matchMedia !== 'function') {
    dom.window.matchMedia = (query) => ({
      matches: false, media: query, addListener() {}, removeListener() {},
      addEventListener() {}, removeEventListener() {}, dispatchEvent() { return false; },
    });
  }
  const previous = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT };
  previous.browserGlobals = new Map(
    ['getComputedStyle', 'HTMLElement', 'Element', 'SVGElement', 'ShadowRoot', 'HTMLButtonElement', 'HTMLInputElement']
      .map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]),
  );
  for (const key of previous.browserGlobals.keys()) {
    const value = typeof dom.window[key] === 'function' && key === 'getComputedStyle'
      ? dom.window[key].bind(dom.window)
      : dom.window[key];
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  }
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return { dom, previous };
}

function restoreDom(previous) {
  for (const [key, descriptor] of previous.browserGlobals) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
  if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
  if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
  if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
}

test('staff mine tab lists 增长分析师; card click returns to conversation', async () => {
  const { StaffMainPanel } = await loadPanel();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  let back = 0;
  let plaza = 0;
  try {
    await act(() => {
      root.render(React.createElement(StaffMainPanel, {
        goConversation() { back += 1; },
        openPlazaRole() { plaza += 1; },
        themeSource: { subscribe() { return () => {}; }, getSnapshot() { return 'dark'; } },
      }));
    });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-staff-main"]').getAttribute('data-panel'), 'staff');
    assert.ok(dom.window.document.querySelector('[data-testid="sm-staff-card-growth-analyst"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-staff-card-legal"]'), null);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-tab-all"]').click(); });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-staff-card-legal"]'));
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-tab-plaza"]').click(); });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-staff-card-legal"]'));
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-card-legal"]').click(); });
    assert.equal(plaza, 1);
    assert.equal(back, 0);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-tab-team"]').click(); });
    assert.match(dom.window.document.querySelector('[data-testid="sm-staff-team"]').textContent, /还没有团队对话/);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-tab-mine"]').click(); });
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-card-growth-analyst"]').click(); });
    assert.equal(back, 1);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-back"]').click(); });
    assert.equal(back, 2);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('staff search filters mine cards by name and plaza without openPlazaRole returns to conversation', async () => {
  const { StaffMainPanel } = await loadPanel();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  const testUtils = webReq('react-dom/test-utils');
  let back = 0;
  try {
    await act(() => {
      root.render(React.createElement(StaffMainPanel, {
        goConversation() { back += 1; },
        themeSource: { subscribe() { return () => {}; }, getSnapshot() { return 'dark'; } },
      }));
    });
    const input = dom.window.document.querySelector('[data-testid="sm-staff-search"]');
    await act(() => { testUtils.Simulate.change(input, { target: { value: '经营参谋' } }); });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-staff-card-ops-advisor"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-staff-card-growth-analyst"]'), null);
    await act(() => { testUtils.Simulate.change(input, { target: { value: '' } }); });
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-tab-plaza"]').click(); });
    await act(() => { dom.window.document.querySelector('[data-testid="sm-staff-card-legal"]').click(); });
    assert.equal(back, 1);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});
