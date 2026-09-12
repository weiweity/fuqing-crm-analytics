/** Cockpit main is the BoardSpec interpreter shell, not BoardWorkbench HTTP. */
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

const panelSource = await readFile(join(here, 'cockpit-main-panel.tsx'), 'utf8');
const indexSource = await readFile(join(here, 'index.tsx'), 'utf8');

test('cockpit main source mounts BoardSpecCanvas and keeps 返回对话', () => {
  assert.match(panelSource, /from '\.\/board-spec-canvas\.tsx'/);
  assert.match(panelSource, /goConversation=\{/);
  assert.match(panelSource, /sm-cockpit-empty/);
  assert.match(panelSource, /data-testid="sm-cockpit-main"/);
  assert.match(panelSource, /data-panel=\{COCKPIT_PANEL_ID\}/);
  assert.doesNotMatch(panelSource, /BoardWorkbench/);
  assert.doesNotMatch(panelSource, /competitionHttp/);
  assert.doesNotMatch(panelSource, /createHttpBoardTransport/);
  assert.match(indexSource, /CockpitMainPanel/);
  assert.match(indexSource, /id: COCKPIT_PANEL_ID/);
  assert.match(indexSource, /key: COCKPIT_PANEL_ID/);
  assert.match(indexSource, /boardLive/);
  assert.match(indexSource, /proposeGenerate/);
  assert.match(indexSource, /生成飞书文档/);
  assert.match(indexSource, /生成多维表/);
  assert.match(indexSource, /specWithLink/);
  assert.match(indexSource, /\/api\/v1\/analytics\/board-spec\/ask/);
  assert.match(panelSource, /catalogFromGsvItems/);
  assert.doesNotMatch(panelSource, /factsFromGsvResult/);
  assert.match(panelSource, /setFactsCatalog/);
  assert.match(indexSource, /confirmGenerate/);
  assert.match(indexSource, /refreshBoard/);
  assert.match(panelSource, /确认生成这份驾驶舱/);
  assert.match(indexSource, /applyGenerate/);
  assert.match(indexSource, /from '\.\.\/board-spec\/demo-board\.mjs'/);
  assert.match(indexSource, /createWorkbenchStore\(DEMO_BOARD\)\.create\(\)/);
  assert.match(indexSource, /seedBoard\.spec/);
  assert.match(indexSource, /seedBoard\.facts/);
  assert.doesNotMatch(indexSource, /onClick=\{\(\) => props\.actions\.openGenerate\(\)\}/);
  assert.match(indexSource, /const opened = props\.openCockpit\?\.\(\);/);
  assert.match(indexSource, /if \(opened\) props\.actions\.close\(\);/);
  assert.match(indexSource, /if \(!opened\) props\.actions\.open\(\);/);
  assert.doesNotMatch(indexSource, /else props\.actions\.open\(\);/);
  assert.doesNotMatch(indexSource, /name: 'conversation.view'/);
});

async function loadPanel() {
  await mkdir(join(plugin, 'lib'), { recursive: true });
  const outfile = join(plugin, 'lib/test-cockpit-main-panel.mjs');
  await esbuild.build({
    absWorkingDir: plugin,
    entryPoints: ['src/client/cockpit-main-panel.tsx'],
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
      matches: false,
      media: query,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent() { return false; },
    });
  }
  const previous = {
    window: globalThis.window,
    document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT,
  };
  previous.browserGlobals = new Map(
    ['getComputedStyle', 'HTMLElement', 'Element', 'SVGElement', 'ShadowRoot', 'HTMLButtonElement']
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

test('cockpit main is empty until GENERATE_BOARD, then paints METRIC 400', async () => {
  const { CockpitMainPanel } = await loadPanel();
  const { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } = await import('../board-spec/fixture.mjs');
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  let back = 0;
  let slice = { boardSpec: null, boardFacts: null, boardError: '' };
  const themeSource = { subscribe() { return () => {}; }, getSnapshot() { return 'dark'; } };
  try {
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() { back += 1; },
        themeSource,
      }));
    });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-cockpit-empty"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-canvas"]'), null);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-cockpit-back"]').click(); });
    assert.equal(back, 1);
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() { back += 1; },
        themeSource,
        useStore(selector) { return selector(slice); },
      }));
    });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-cockpit-empty"]'));
    slice = {
      boardSpec: null,
      boardFacts: null,
      boardError: '',
      pendingGenerate: { spec: BOARD_SPEC_FIXTURE, facts: BOARD_SPEC_FACTS },
    };
    let confirmed = false;
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() { back += 1; },
        themeSource,
        useStore(selector) { return selector(slice); },
        actions: {
          confirmGenerate() {
            confirmed = true;
            slice = { boardSpec: BOARD_SPEC_FIXTURE, boardFacts: BOARD_SPEC_FACTS, boardError: '', pendingGenerate: null };
          },
          cancelGenerate() { slice = { ...slice, pendingGenerate: null }; },
        },
      }));
    });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-generate-modal"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-canvas"]'), null);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-generate-confirm"]').click(); });
    assert.equal(confirmed, true);
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() { back += 1; },
        themeSource,
        useStore(selector) { return selector(slice); },
      }));
    });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-canvas"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-metric-headline"]').textContent, '400');
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('the seeded demo board paints its synthetic channels in the cockpit', async () => {
  const { CockpitMainPanel } = await loadPanel();
  const { DEMO_BOARD_FACTS, DEMO_BOARD_SPEC } = await import('../board-spec/demo-board.mjs');
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  const slice = {
    boardSpec: DEMO_BOARD_SPEC, boardFacts: DEMO_BOARD_FACTS, boardError: '', pendingGenerate: null,
  };
  const themeSource = { subscribe() { return () => {}; }, getSnapshot() { return 'dark'; } };
  try {
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() {},
        themeSource,
        useStore(selector) { return selector(slice); },
      }));
    });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-cockpit-empty"]'), null);
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-canvas"]'));
    const headlines = [...dom.window.document.querySelectorAll('[data-testid="sm-board-spec-metric-headline"]')]
      .map(node => node.textContent);
    assert.deepEqual(headlines, ['180', '96', '124']);
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-line"]'));
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-bar"]'));
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-table"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-unbound"]'), null);
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-evidence"]').textContent, /SYNTHETIC/);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('cockpit refresh catalogs GSV by result_id so GENERATE bindings stay live', async () => {
  const { CockpitMainPanel } = await loadPanel();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  const spec = {
    board_id: 'board_retail_gsv_result_c0_gsv_20260831',
    version: 1,
    blocks: [{
      block_id: 'm1', kind: 'METRIC', title: '零售 GSV', metric_ref: 'retail_gsv',
      source_result_id: 'result_c0_gsv_20260831',
    }],
  };
  const slice = { boardSpec: spec, boardFacts: null, boardError: '', pendingGenerate: null, boardEpoch: 1 };
  const themeSource = { subscribe() { return () => {}; }, getSnapshot() { return 'dark'; } };
  let catalog = null;
  let settle;
  const settled = new Promise((resolve) => { settle = resolve; });
  try {
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() {},
        themeSource,
        useStore(selector) { return selector(slice); },
        actions: {
          setFactsCatalog(next) { catalog = next; settle(); },
          refreshBoard() {},
        },
        askTransport: {
          resultsPath: '/api/v1/analytics/results',
          async fetchImpl() {
            return {
              ok: true,
              async json() {
                return {
                  items: [{
                    result_id: 'result_c0_gsv_20260831',
                    facts: { current: { gsv: 410 }, comparison: { gsv: 305 }, difference: 105 },
                  }],
                };
              },
            };
          },
        },
      }));
    });
    await act(async () => { await settled; });
    assert.equal(catalog.r1, undefined);
    assert.equal(catalog.result_c0_gsv_20260831.current_gsv, 410);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('cockpit board live subscribe paints pending then cancel drops it without writing', async () => {
  const { CockpitMainPanel } = await loadPanel();
  const { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } = await import('../board-spec/fixture.mjs');
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  let slice = {
    boardSpec: null, boardFacts: null, boardError: '',
    pendingGenerate: { spec: BOARD_SPEC_FIXTURE, facts: BOARD_SPEC_FACTS },
  };
  const listeners = new Set();
  const board = {
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    getSnapshot() { return slice; },
    actions: {
      cancelGenerate() {
        slice = { ...slice, pendingGenerate: null };
        for (const listener of listeners) listener();
      },
    },
  };
  const themeSource = { subscribe() { return () => {}; }, getSnapshot() { return 'dark'; } };
  try {
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() {},
        themeSource,
        board,
      }));
    });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-generate-modal"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-canvas"]'), null);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-generate-cancel"]').click(); });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-generate-modal"]'), null);
    assert.ok(dom.window.document.querySelector('[data-testid="sm-cockpit-empty"]'));
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('cockpit results fetch failure or empty catalog keeps generate-time facts', async () => {
  const { CockpitMainPanel } = await loadPanel();
  const { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } = await import('../board-spec/fixture.mjs');
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  const slice = {
    boardSpec: BOARD_SPEC_FIXTURE, boardFacts: BOARD_SPEC_FACTS, boardError: '', pendingGenerate: null, boardEpoch: 1,
  };
  const themeSource = { subscribe() { return () => {}; }, getSnapshot() { return 'dark'; } };
  let catalogSet = 0;
  let refreshed = 0;
  try {
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() {},
        themeSource,
        useStore(selector) { return selector(slice); },
        actions: {
          setFactsCatalog() { catalogSet += 1; },
          refreshBoard() { refreshed += 1; },
        },
        askTransport: {
          resultsPath: '/api/v1/analytics/results',
          async fetchImpl() { throw new Error('offline'); },
        },
      }));
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
    assert.equal(catalogSet, 0);
    assert.ok(refreshed >= 1);
    await act(() => {
      root.render(React.createElement(CockpitMainPanel, {
        goConversation() {},
        themeSource,
        useStore(selector) { return selector({ ...slice, boardEpoch: 2 }); },
        actions: {
          setFactsCatalog() { catalogSet += 1; },
          refreshBoard() { refreshed += 1; },
        },
        askTransport: {
          resultsPath: '/api/v1/analytics/results',
          async fetchImpl() {
            return { ok: true, async json() { return { items: [{ result_id: 'x' }] }; } };
          },
        },
      }));
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)); });
    assert.equal(catalogSet, 0);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});
