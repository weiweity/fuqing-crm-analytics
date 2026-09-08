/** Compiled HTTP overlay: discard, stale preview, drag commit. Mock transport only. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { createEditor } from '../src/model.mjs';

const root = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(root, '../../.context/dsh-b0/upstream'));
const webReq = createRequire(join(upstream, 'apps/web/package.json'));
const React = webReq('react');
const { createRoot } = webReq('react-dom/client');
const act = typeof React.act === 'function' ? React.act : webReq('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const stores = await import(pathToFileURL(join(upstream, 'packages/client/store/lib/index.js')).href);
const source = await readFile(join(root, 'lib/client.js'), 'utf8');
const overlaySource = await readFile(join(root, 'src/client/asset-overlay.tsx'), 'utf8');

const card = {
  card_id: 'card_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  source_status: 'OK',
  analysis_ref: { analysis_id: 'analysis_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', version: 1 },
  layout: { x: 0, y: 0, w: 6, h: 4 },
  display_overrides: { title: '30 日快照' },
  snapshot: {
    run_id: 'run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    as_of: '2026-08-31T16:00:00.000000+00:00',
    resolved_filters: { channel_ids: ['A'] },
  },
  facts: { observation_days: 30, totals: { channel_mature_cohort_count: 2, channel_repeat_count: 1 } },
};
const board = {
  schema_version: 'analytics-cockpit/v1', http_api: 'CONNECTED', dashboard_id: 'dashboard_1',
  version: 2, preview: false, cards: [card],
};

function jsonResponse(status, payload) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => payload,
    headers: { get: () => null },
  };
}

function patchDialog(window) {
  const proto = window.HTMLDialogElement?.prototype;
  if (!proto) return;
  proto.showModal = function showModal() {
    this.open = true;
    this.setAttribute('open', '');
  };
  proto.close = function close() {
    this.open = false;
    this.removeAttribute('open');
    this.dispatchEvent(new window.Event('close'));
  };
}

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',
    { url: 'http://127.0.0.1:4318/' });
  patchDialog(dom.window);
  dom.window.requestAnimationFrame = cb => dom.window.setTimeout(() => cb(Date.now()), 0);
  dom.window.cancelAnimationFrame = id => dom.window.clearTimeout(id);
  if (typeof dom.window.PointerEvent !== 'function') {
    dom.window.PointerEvent = class PointerEvent extends dom.window.MouseEvent {};
  }
  const previous = {
    window: globalThis.window, document: globalThis.document, fetch: globalThis.fetch,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT,
  };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return { dom, previous };
}

function restoreDom(previous) {
  if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
  if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
  if (previous.fetch === undefined) delete globalThis.fetch; else globalThis.fetch = previous.fetch;
  if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
}

function Shell({ Overlay, Footer, actionsRef }) {
  const [snap, setSnap] = React.useState({
    open: true, confirmClose: false, editor: createEditor(), message: '',
  });
  const actions = {
    close: () => { actionsRef.close += 1; setSnap(state => ({ ...state, open: false, confirmClose: false })); },
    requestClose: () => { actionsRef.requestClose += 1; setSnap(state => ({ ...state, confirmClose: true })); },
    keepEditing: () => { actionsRef.keepEditing += 1; setSnap(state => ({ ...state, confirmClose: false })); },
    discardAndClose: () => { actionsRef.discard += 1; setSnap(state => ({ ...state, open: false, confirmClose: false })); },
    open: () => setSnap(state => ({ ...state, open: true, confirmClose: false })),
  };
  return React.createElement(React.Fragment, null,
    React.createElement(Footer, { wide: true, useStore: selector => selector(snap), actions }),
    React.createElement(Overlay, {
      useStore: selector => selector(snap),
      actions,
      useSessions: selector => selector({ current: undefined }),
      detachSelection() {},
      restoreSelection() {},
    }),
  );
}

async function mountShell(fetchImpl) {
  let factory;
  const context = {
    window: Object.assign(globalThis.window, { __ModuleLoader__: { load: row => { factory = row; } }, fetch: fetchImpl }),
    document: globalThis.document,
    fetch: fetchImpl,
    Event: globalThis.window.Event,
    CustomEvent: globalThis.window.CustomEvent,
    requestAnimationFrame: globalThis.window.requestAnimationFrame,
    cancelAnimationFrame: globalThis.window.cancelAnimationFrame,
  };
  vm.runInNewContext(source, context, { timeout: 2000 });
  const api = factory.factory(name => {
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return webReq('react/jsx-runtime');
    if (name === '@deepseek-ai/dsh-client-store') return stores;
    throw new Error(`unexpected ${name}`);
  });
  const registrations = [];
  api.apply({ effect: () => {}, sessions: {
    list: { getSnapshot: () => ({ current: undefined, ids: [] }), subscribe: () => () => {} },
    open() {}, clear() {},
  }, slots: { inject: (_, fn) => fn(), register: (options, component) => {
    registrations.push({ options, component }); return () => {};
  } } });
  const Overlay = registrations.find(row => row.options.name === 'shell.overlay')?.component;
  const Footer = registrations.find(row => row.options.name === 'sidebar.footer.action')?.component;
  assert.ok(Overlay && Footer);
  globalThis.fetch = fetchImpl;
  const actionsRef = { close: 0, requestClose: 0, keepEditing: 0, discard: 0 };
  const rootEl = globalThis.document.getElementById('root');
  const root = createRoot(rootEl);
  await act(() => {
    root.render(React.createElement(Shell, { Overlay, Footer, actionsRef }));
  });
  return { actionsRef, unmount: () => act(() => root.unmount()) };
}

async function waitFor(check) {
  for (let i = 0; i < 50; i++) {
    if (check()) return;
    await act(async () => { await delay(15); });
  }
  throw new Error('asset-overlay wait timeout');
}

function connectedBoardFetch(options = {}) {
  const calls = [];
  let previewGate = options.previewGate ?? null;
  const fetchImpl = async (url, init = {}) => {
    const path = String(url);
    const method = init.method ?? 'GET';
    calls.push({ method, path, headers: init.headers ?? {}, body: init.body });
    if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
    if (method === 'GET' && path === '/b0/dashboards') {
      return jsonResponse(200, { items: [{ dashboard_id: 'dashboard_1', version: 2 }] });
    }
    if (method === 'GET' && path === '/b0/analyses') return jsonResponse(200, { items: [] });
    if (method === 'GET' && path === '/b0/dashboards/dashboard_1') return jsonResponse(200, board);
    if (method === 'POST' && path === '/b0/dashboards/dashboard_1/preview') {
      const payload = { ...board, preview: true, version: 2 };
      if (previewGate) return previewGate.promise.then(() => jsonResponse(200, payload));
      return jsonResponse(200, payload);
    }
    throw new Error(`unexpected ${method} ${path}`);
  };
  return { calls, fetchImpl, setPreviewGate(gate) { previewGate = gate; } };
}

test('RoutedOverlay stays on the B0 stub until CONNECTED cockpit probe succeeds', async () => {
  const { previous } = installDom();
  const fetchImpl = async () => jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'no assets' } });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-open"]'));
  assert.match(globalThis.document.querySelector('[data-testid="analytics-b0-open"]').textContent, /B0/);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-title-input"]'));
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]')?.getAttribute('data-http'), null);
  mounted.unmount();
  restoreDom(previous);

  const connected = installDom();
  const { fetchImpl: okFetch } = connectedBoardFetch();
  const httpMounted = await mountShell(okFetch);
  await waitFor(() => globalThis.document.querySelector('[data-http="CONNECTED"]'));
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-b0-title-input"]'), null);
  assert.match(globalThis.document.querySelector('[data-testid="analytics-b0-open"]').textContent, /我的驾驶舱/);
  assert.doesNotMatch(globalThis.document.querySelector('[data-testid="analytics-b0-open"]').textContent, /B0/);
  httpMounted.unmount();
  restoreDom(connected.previous);
});

test('dirty overlay close asks to discard and does not keep the preview after discard', async () => {
  const { previous } = installDom();
  const { fetchImpl } = connectedBoardFetch();
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-action="copy"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-action="copy"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-b0-close"]').click();
    await delay(10);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-close-confirm"]'));
  await act(async () => {
    [...globalThis.document.querySelectorAll('button')].find(row => row.textContent === '继续编辑').click();
    await delay(10);
  });
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-b0-close-confirm"]'), null);
  assert.ok(globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-b0-close"]').click();
    await delay(10);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-asset-discard"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-asset-discard"]').click();
    await delay(10);
  });
  assert.equal(mounted.actionsRef.discard, 1);
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'), null);
  mounted.unmount();
  restoreDom(previous);
});

test('stale preview response is ignored after a newer refresh generation', async () => {
  const { previous } = installDom();
  let release;
  const previewGate = { promise: new Promise(resolve => { release = resolve; }) };
  const { calls, fetchImpl } = connectedBoardFetch({ previewGate });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-action="copy"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-action="copy"]').click();
    await delay(10);
  });
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'), null);
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-asset-refresh"]').click();
    await delay(20);
  });
  release();
  await act(async () => { await delay(30); });
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'), null);
  assert.ok(calls.some(row => row.method === 'POST' && row.path.endsWith('/preview')));
  mounted.unmount();
  restoreDom(previous);
});

test('layout drag commits on pointerup and does not preview on pointermove', async () => {
  assert.match(overlaySource, /window\.addEventListener\('pointerup', finish\)/);
  assert.match(overlaySource, /window\.addEventListener\('pointermove', move\)/);
  assert.doesNotMatch(overlaySource, /onPointerMove=\{/);
  const { previous } = installDom();
  const { calls, fetchImpl } = connectedBoardFetch();
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-card-id]'));
  await act(async () => {
    globalThis.document.querySelector('[data-card-id]').click();
    await delay(10);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-layout-drag"]'));
  const drag = globalThis.document.querySelector('[data-testid="analytics-layout-drag"]');
  const before = calls.filter(row => row.path.endsWith('/preview')).length;
  await act(() => {
    drag.dispatchEvent(new globalThis.window.PointerEvent('pointerdown', { bubbles: true, clientX: 0, clientY: 0 }));
  });
  await act(() => {
    globalThis.window.dispatchEvent(new globalThis.window.PointerEvent('pointermove', { bubbles: true, clientX: 96, clientY: 0 }));
  });
  assert.equal(calls.filter(row => row.path.endsWith('/preview')).length, before);
  await act(async () => {
    globalThis.window.dispatchEvent(new globalThis.window.PointerEvent('pointerup', { bubbles: true, clientX: 96, clientY: 0 }));
    await delay(20);
  });
  await waitFor(() => calls.filter(row => row.path.endsWith('/preview')).length === before + 1);
  const preview = calls.filter(row => row.path.endsWith('/preview')).at(-1);
  assert.equal(JSON.parse(preview.body).op, 'layout');
  assert.equal(JSON.parse(preview.body).layout.x, 2);
  mounted.unmount();
  restoreDom(previous);
});
