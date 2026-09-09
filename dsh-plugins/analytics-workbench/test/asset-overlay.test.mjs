/** Compiled HTTP overlay: discard, stale preview, drag, add/create, undo. Mock transport only. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { createEditor } from '../src/model.mjs';
import { QUERY_TOOL_NAME } from '../src/query-model.mjs';
import { QUERY_CARD_CASES } from './tool-card-harness.mjs';

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
const mockOverlaySource = await readFile(join(root, 'src/client/index.tsx'), 'utf8');
const focusSource = await readFile(join(root, 'src/client/focus.ts'), 'utf8');
const successBlock = QUERY_CARD_CASES.find(row => row.id === 'query-success').block;

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
const analysis = {
  schema_version: 'analytics-saved-analysis/v1',
  analysis_id: 'analysis_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  version: 1,
  title: '渠道后续购买',
  observation_days: 30,
  as_of: '2026-08-31T16:00:00.000000+00:00',
  http_api: 'CONNECTED',
};
const emptyBoard = {
  schema_version: 'analytics-cockpit/v1', http_api: 'CONNECTED', dashboard_id: 'dashboard_1',
  version: 1, preview: false, cards: [],
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

function Shell({ Overlay, Footer, actionsRef, QueryCard, themeSource }) {
  const [snap, setSnap] = React.useState({
    open: true, openTick: 1, confirmClose: false, editor: createEditor(), message: '',
  });
  const actions = {
    close: () => { actionsRef.close += 1; setSnap(state => ({ ...state, open: false, confirmClose: false })); },
    requestClose: () => { actionsRef.requestClose += 1; setSnap(state => ({ ...state, confirmClose: true })); },
    keepEditing: () => { actionsRef.keepEditing += 1; setSnap(state => ({ ...state, confirmClose: false })); },
    discardAndClose: () => { actionsRef.discard += 1; setSnap(state => ({ ...state, open: false, confirmClose: false })); },
    open: () => setSnap(state => ({
      ...state, open: true, confirmClose: false, openTick: (state.openTick || 0) + 1,
    })),
  };
  return React.createElement(React.Fragment, null,
    React.createElement(Footer, { wide: true, useStore: selector => selector(snap), actions }),
    React.createElement(Overlay, {
      themeSource: themeSource ?? { subscribe: () => () => {}, getSnapshot: () => 'dark' },
      useStore: selector => selector(snap),
      actions,
      useSessions: selector => selector({ current: undefined }),
      detachSelection() {},
      restoreSelection() {},
    }),
    QueryCard ? React.createElement(QueryCard, {
      block: successBlock, callId: successBlock.callId, toolName: QUERY_TOOL_NAME,
    }) : null,
  );
}

async function mountShell(fetchImpl, options = {}) {
  let factory;
  const context = {
    window: Object.assign(globalThis.window, { __ModuleLoader__: { load: row => { factory = row; } }, fetch: fetchImpl }),
    document: globalThis.document,
    getComputedStyle: globalThis.window.getComputedStyle.bind(globalThis.window),
    HTMLElement: globalThis.window.HTMLElement,
    Element: globalThis.window.Element,
    ShadowRoot: globalThis.window.ShadowRoot,
    SVGElement: globalThis.window.SVGElement,
    setTimeout, clearTimeout,
    fetch: fetchImpl,
    Event: globalThis.window.Event,
    CustomEvent: globalThis.window.CustomEvent,
    requestAnimationFrame: globalThis.window.requestAnimationFrame,
    cancelAnimationFrame: globalThis.window.cancelAnimationFrame,
  };
  vm.runInNewContext(source, context, { timeout: 2000 });
  const api = factory.factory(name => {
    if (name === 'react') return React;
    if (name === 'react-dom') return webReq('react-dom');
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
  const QueryCard = registrations.find(row => row.options.key === QUERY_TOOL_NAME)?.component;
  assert.ok(Overlay && Footer);
  if (options.withQueryCard) assert.ok(QueryCard);
  globalThis.fetch = fetchImpl;
  const actionsRef = { close: 0, requestClose: 0, keepEditing: 0, discard: 0 };
  const rootEl = globalThis.document.getElementById('root');
  const root = createRoot(rootEl);
  await act(() => {
    root.render(React.createElement(Shell, {
      Overlay, Footer, actionsRef, QueryCard: options.withQueryCard ? QueryCard : null, themeSource: options.themeSource,
    }));
  });
  return { actionsRef, Overlay, QueryCard, unmount: () => act(() => root.unmount()) };
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
  let currentBoard = options.board === undefined ? { ...board } : options.board;
  const analyses = [...(options.analyses ?? [])];
  const analysisDoc = options.analysisDoc ?? null;
  const previewStatus = options.previewStatus ?? 200;
  const saveStatus = options.saveStatus ?? 200;
  const previewOkBeforeConflict = options.previewOkBeforeConflict ?? 0;
  let previewHits = 0;
  const fetchImpl = async (url, init = {}) => {
    const path = String(url);
    const method = init.method ?? 'GET';
    calls.push({ method, path, headers: init.headers ?? {}, body: init.body });
    if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
    if (method === 'GET' && path === '/b0/dashboards') {
      if (!currentBoard) return jsonResponse(200, { items: [] });
      return jsonResponse(200, { items: [{ dashboard_id: currentBoard.dashboard_id, version: currentBoard.version }] });
    }
    if (method === 'POST' && path === '/b0/analyses') {
      const status = options.analysisSaveStatus ?? 201;
      if (status >= 400) {
        return jsonResponse(status, options.analysisSaveError ?? { error: { code: 'UNPROCESSABLE', message: '保存失败。' } });
      }
      const doc = analysisDoc ?? {
        schema_version: 'analytics-saved-analysis/v1',
        analysis_id: 'analysis_saved',
        version: 1,
        title: '渠道后续购买',
        observation_days: 30,
        as_of: '2026-08-31T16:00:00.000000+00:00',
        http_api: 'CONNECTED',
      };
      if (!analyses.some(row => row.analysis_id === doc.analysis_id)) analyses.push(doc);
      return jsonResponse(status, doc);
    }
    if (method === 'GET' && path === '/b0/analyses') return jsonResponse(200, { items: analyses });
    if (method === 'POST' && path === '/b0/dashboards') {
      currentBoard = { ...emptyBoard };
      return jsonResponse(201, currentBoard);
    }
    if (currentBoard && method === 'GET' && path === `/b0/dashboards/${currentBoard.dashboard_id}`) {
      return jsonResponse(200, currentBoard);
    }
    if (currentBoard && method === 'POST' && path === `/b0/dashboards/${currentBoard.dashboard_id}/preview`) {
      previewHits += 1;
      if (previewStatus === 409 && previewHits > previewOkBeforeConflict) {
        return jsonResponse(409, { error: { code: 'CONFLICT', message: '版本已变化。' } });
      }
      const payload = { ...currentBoard, preview: true };
      if (previewGate) return previewGate.promise.then(() => jsonResponse(200, payload));
      return jsonResponse(200, payload);
    }
    if (currentBoard && method === 'POST' && path === `/b0/dashboards/${currentBoard.dashboard_id}/versions`) {
      if (saveStatus >= 400) {
        const payload = saveStatus === 409
          ? { error: { code: 'CONFLICT', message: '版本冲突。' } }
          : (options.saveError ?? { error: { code: 'UNPROCESSABLE', message: '驾驶舱保存失败。' } });
        return jsonResponse(saveStatus, payload);
      }
      currentBoard = { ...currentBoard, version: currentBoard.version + 1, preview: false };
      return jsonResponse(201, currentBoard);
    }
    throw new Error(`unexpected ${method} ${path}`);
  };
  return { calls, fetchImpl, analyses, setPreviewGate(gate) { previewGate = gate; } };
}

test('native resolved mode updates the existing dialog and inherited competition controls', async () => {
  const { previous, dom } = installDom();
  let mode = 'light';
  const listeners = new Set();
  const themeSource = { getSnapshot: () => mode, subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); } };
  const fixture = connectedBoardFetch();
  const mounted = await mountShell(fixture.fetchImpl, { themeSource });
  try {
    await waitFor(() => document.querySelector('[data-testid="analytics-b0-dialog"]'));
    const dialog = document.querySelector('[data-testid="analytics-b0-dialog"]');
    const root = document.querySelector('.sm-overlay-theme');
    assert.equal(root.dataset.smColorScheme, 'light');
    assert.equal(root.style.getPropertyValue('--sm-bg'), '#FEFCFF');
    const competition = [...dialog.querySelectorAll('button')].find(button => button.textContent.includes('认可成板'));
    assert.ok(competition);
    await act(async () => { competition.click(); await delay(20); });
    await waitFor(() => dialog.querySelector('[data-testid="sm-open-board"]'));
    assert.ok(dialog.querySelector('.ant-btn'), 'actual AntD button is rendered');
    for (const next of ['dark', 'light']) {
      await act(() => { mode = next; for (const listener of listeners) listener(); });
      assert.equal(document.querySelector('[data-testid="analytics-b0-dialog"]'), dialog);
      assert.equal(dialog.open, true);
      assert.deepEqual([...document.querySelectorAll('[data-sm-color-scheme]')].map(node => node.dataset.smColorScheme), [next, next]);
    }
    assert.equal(mounted.actionsRef.close, 0);
  } finally {
    await mounted.unmount();
    assert.equal(listeners.size, 0);
    dom.window.close(); restoreDom(previous);
  }
});

test('RoutedOverlay stays on the B0 stub until CONNECTED cockpit probe succeeds', async () => {
  const competitionLive = /127\.0\.0\.1:18082/.test(source);
  const { previous } = installDom();
  const fetchImpl = async () => jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'no assets' } });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-open"]'));
  if (competitionLive) {
    assert.match(globalThis.document.querySelector('[data-testid="analytics-b0-open"]').textContent, /我的驾驶舱/);
    await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]'));
    assert.equal(globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]')?.getAttribute('data-http'), 'CONNECTED');
  } else {
    assert.match(globalThis.document.querySelector('[data-testid="analytics-b0-open"]').getAttribute('aria-label'), /合成样例/);
    await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-title-input"]'));
    assert.equal(globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]')?.getAttribute('data-http'), null);
  }
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

test('HTTP overlay and mock overlay share the native dialog Tab trap', () => {
  assert.match(focusSource, /export function trapDialogTab/);
  assert.match(overlaySource, /onKeyDown=\{trapDialogTab\}/);
  assert.match(mockOverlaySource, /onKeyDown=\{trapDialogTab\}/);
  assert.match(overlaySource, /handleDialogClose/);
  assert.match(overlaySource, /closedby/);
  assert.match(overlaySource, /OverlayErrorBoundary/);
  assert.match(overlaySource, /resetKey=\{openTick\}/);
  assert.match(mockOverlaySource, /key=\{openTick\}/);
  assert.match(mockOverlaySource, /openTick = \(draft.openTick \|\| 0\) \+ 1/);
  assert.match(overlaySource, /B0 同域 \/b0\/dashboards 未接线/);
  assert.match(overlaySource, /data-dsh-native-chrome="1"/);
  assert.match(overlaySource, /gridColumn: '1 \/ -1'/);
});

test('footer open remounts overlay after close on the same page', async () => {
  const { previous } = installDom();
  const { fetchImpl } = connectedBoardFetch();
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]'));
  const dialog = globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]');
  assert.equal(dialog.open, true);
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-b0-close"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]')?.open !== true);
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-b0-open"]').click();
    await delay(30);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]')?.open === true);
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]').open, true);
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

function statusText() {
  return globalThis.document.querySelector('[data-testid="analytics-asset-status"]')?.textContent ?? '';
}

test('undoBoard is a no-op when the saved board has no prior version', async () => {
  const { previous } = installDom();
  const { calls, fetchImpl } = connectedBoardFetch({ board: { ...board, version: 1 } });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-undo"]'));
  const before = calls.filter(row => row.path.endsWith('/preview')).length;
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-cockpit-undo"]').click();
    await delay(20);
  });
  await waitFor(() => statusText().includes('没有可恢复的历史版本。'));
  assert.equal(calls.filter(row => row.path.endsWith('/preview')).length, before);
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'), null);
  mounted.unmount();
  restoreDom(previous);
});

test('undoBoard previews restore_from_version against the current board etag', async () => {
  const { previous } = installDom();
  const { calls, fetchImpl } = connectedBoardFetch();
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-undo"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-cockpit-undo"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  const preview = calls.filter(row => row.method === 'POST' && row.path.endsWith('/preview')).at(-1);
  assert.equal(JSON.parse(preview.body).op, 'undo');
  assert.equal(JSON.parse(preview.body).scope, 'board');
  assert.equal(JSON.parse(preview.body).restore_from_version, 1);
  assert.equal(preview.headers['if-match'], '2');
  assert.match(globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]').textContent, /整板恢复到版本 1/);
  mounted.unmount();
  restoreDom(previous);
});

test('analyses panel add previews analysis_ref then save posts the add intent key', async () => {
  const { previous } = installDom();
  const { calls, fetchImpl } = connectedBoardFetch({ analyses: [analysis] });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-asset-analyses"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-asset-analyses"]').click();
    await delay(10);
  });
  await waitFor(() => globalThis.document.querySelector(`[data-testid="analytics-join-${analysis.analysis_id}"]`));
  await act(async () => {
    globalThis.document.querySelector(`[data-testid="analytics-join-${analysis.analysis_id}"]`).click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  assert.equal(calls.some(row => row.method === 'POST' && row.path === '/b0/dashboards'), false);
  const preview = calls.filter(row => row.method === 'POST' && row.path.endsWith('/preview')).at(-1);
  assert.deepEqual(JSON.parse(preview.body), {
    op: 'add', analysis_ref: { analysis_id: analysis.analysis_id, version: 1 },
  });
  assert.equal(preview.headers['if-match'], '2');
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-cockpit-save"]').click();
    await delay(20);
  });
  await waitFor(() => statusText().includes('已保存固定历史快照。'));
  const saved = calls.find(row => row.method === 'POST' && row.path.endsWith('/versions'));
  assert.equal(saved.headers['idempotency-key'], `add-${analysis.analysis_id}-v1-b2`);
  assert.equal(saved.headers['if-match'], '2');
  assert.equal(JSON.parse(saved.body).op, 'add');
  mounted.unmount();
  restoreDom(previous);
});

test('addAnalysis creates the owner board before previewing add when none exists', async () => {
  const { previous } = installDom();
  const { calls, fetchImpl } = connectedBoardFetch({ board: null, analyses: [analysis] });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-empty"]'));
  assert.equal(calls.some(row => row.method === 'POST' && row.path === '/b0/dashboards'), false);
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-asset-analyses"]').click();
    await delay(10);
  });
  await waitFor(() => globalThis.document.querySelector(`[data-testid="analytics-join-${analysis.analysis_id}"]`));
  await act(async () => {
    globalThis.document.querySelector(`[data-testid="analytics-join-${analysis.analysis_id}"]`).click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  const created = calls.find(row => row.method === 'POST' && row.path === '/b0/dashboards');
  assert.equal(created.headers['idempotency-key'], 'board-owner');
  assert.equal(JSON.parse(created.body).title, '我的驾驶舱');
  const preview = calls.filter(row => row.method === 'POST' && row.path.endsWith('/preview')).at(-1);
  assert.equal(preview.path, '/b0/dashboards/dashboard_1/preview');
  assert.equal(JSON.parse(preview.body).op, 'add');
  assert.equal(preview.headers['if-match'], '1');
  mounted.unmount();
  restoreDom(previous);
});

test('preview 409 re-reads and does not keep a stale pending op', async () => {
  const { previous } = installDom();
  const { calls, fetchImpl } = connectedBoardFetch({ previewStatus: 409, previewOkBeforeConflict: 1 });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-action="copy"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-action="copy"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  const getsBeforeConflict = calls.filter(row => row.method === 'GET' && row.path === '/b0/dashboards').length;
  await act(async () => {
    globalThis.document.querySelector('[data-action="copy"]').click();
    await delay(20);
  });
  await waitFor(() => statusText().includes('版本已变化，已重新读取，请再预览。')
    && !globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  assert.ok(calls.filter(row => row.method === 'GET' && row.path === '/b0/dashboards').length > getsBeforeConflict);
  mounted.unmount();
  restoreDom(previous);
});

test('save 409 re-reads and does not keep the pending preview', async () => {
  const { previous } = installDom();
  const { calls, fetchImpl } = connectedBoardFetch({ saveStatus: 409 });
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-action="copy"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-action="copy"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  const getsBeforeSave = calls.filter(row => row.method === 'GET' && row.path === '/b0/dashboards').length;
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-cockpit-save"]').click();
    await delay(20);
  });
  await waitFor(() => statusText().includes('版本冲突，未覆盖。请读取当前驾驶舱后再试。')
    && !globalThis.document.querySelector('[data-testid="analytics-cockpit-preview"]'));
  assert.ok(calls.filter(row => row.method === 'GET' && row.path === '/b0/dashboards').length > getsBeforeSave);
  mounted.unmount();
  restoreDom(previous);
});

function querySaveStatus() {
  return globalThis.document.querySelector('[data-testid="analytics-query-save-status"]')?.textContent ?? '';
}

function dualBoardFetch(boardA, boardB) {
  const boards = {
    [boardA.dashboard_id]: { ...boardA },
    [boardB.dashboard_id]: { ...boardB },
  };
  let listPrimary = boardA.dashboard_id;
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    const path = String(url);
    const method = init.method ?? 'GET';
    calls.push({ method, path, headers: init.headers ?? {}, body: init.body });
    if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
    if (method === 'GET' && path === '/b0/analyses') return jsonResponse(200, { items: [] });
    if (method === 'GET' && path === '/b0/dashboards') {
      const row = boards[listPrimary];
      return jsonResponse(200, { items: [{ dashboard_id: row.dashboard_id, version: row.version }] });
    }
    const match = path.match(/^\/b0\/dashboards\/([^/]+)(?:\/(preview|versions))?$/);
    if (!match || !boards[match[1]]) throw new Error(`unexpected ${method} ${path}`);
    const id = match[1];
    if (method === 'GET' && !match[2]) return jsonResponse(200, boards[id]);
    if (method === 'POST' && match[2] === 'preview') {
      return jsonResponse(200, { ...boards[id], preview: true });
    }
    if (method === 'POST' && match[2] === 'versions') {
      boards[id] = { ...boards[id], version: boards[id].version + 1, preview: false };
      return jsonResponse(201, boards[id]);
    }
    throw new Error(`unexpected ${method} ${path}`);
  };
  return {
    calls,
    fetchImpl,
    setListPrimary(id) { listPrimary = id; },
  };
}

async function mountDualOverlays(fetchImpl) {
  let factory;
  const context = {
    window: Object.assign(globalThis.window, { __ModuleLoader__: { load: row => { factory = row; } }, fetch: fetchImpl }),
    document: globalThis.document,
    getComputedStyle: globalThis.window.getComputedStyle.bind(globalThis.window),
    HTMLElement: globalThis.window.HTMLElement,
    Element: globalThis.window.Element,
    ShadowRoot: globalThis.window.ShadowRoot,
    SVGElement: globalThis.window.SVGElement,
    setTimeout, clearTimeout,
    fetch: fetchImpl,
    Event: globalThis.window.Event,
    CustomEvent: globalThis.window.CustomEvent,
    requestAnimationFrame: globalThis.window.requestAnimationFrame,
    cancelAnimationFrame: globalThis.window.cancelAnimationFrame,
  };
  vm.runInNewContext(source, context, { timeout: 2000 });
  const api = factory.factory(name => {
    if (name === 'react') return React;
    if (name === 'react-dom') return webReq('react-dom');
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
  assert.ok(Overlay);
  globalThis.fetch = fetchImpl;
  const host = { setCount: null };
  function DualShell() {
    const [count, setCount] = React.useState(1);
    host.setCount = setCount;
    const [snap] = React.useState({
      open: true, confirmClose: false, editor: createEditor(), message: '',
    });
    const actions = {
      close() {}, requestClose() {}, keepEditing() {}, discardAndClose() {}, open() {},
    };
    const nodes = [];
    for (let i = 0; i < count; i++) {
      nodes.push(React.createElement('div', { key: String(i), 'data-overlay-instance': String(i) },
        React.createElement(Overlay, {
          themeSource: { subscribe: () => () => {}, getSnapshot: () => 'dark' },
      useStore: selector => selector(snap),
          actions,
          useSessions: selector => selector({ current: i === 0 ? 'session-a' : 'session-b' }),
          detachSelection() {},
          restoreSelection() {},
        })));
    }
    return React.createElement(React.Fragment, null, ...nodes);
  }
  const rootEl = globalThis.document.getElementById('root');
  const root = createRoot(rootEl);
  await act(() => { root.render(React.createElement(DualShell)); });
  return {
    async addSecond() {
      await act(() => { host.setCount(2); });
    },
    unmount: () => act(() => root.unmount()),
  };
}

function instanceDialog(index) {
  return globalThis.document.querySelector(`[data-overlay-instance="${index}"] [data-testid="analytics-b0-dialog"]`);
}

function boardWrites(calls) {
  return calls.filter(row => row.method === 'POST' && /\/b0\/dashboards\/[^/]+\/(preview|versions)$/.test(row.path));
}

test('save 201 then dashboard 4xx/409 does not POST a second analysis', async () => {
  const { previous } = installDom();
  const analysisDoc = {
    schema_version: 'analytics-saved-analysis/v1',
    analysis_id: 'analysis_keep_first',
    version: 1,
    title: '渠道后续购买',
    observation_days: 30,
    as_of: '2026-08-31T16:00:00.000000+00:00',
    http_api: 'CONNECTED',
  };
  const { calls, fetchImpl } = connectedBoardFetch({ saveStatus: 409, analysisDoc });
  const mounted = await mountShell(fetchImpl, { withQueryCard: true });
  await waitFor(() => globalThis.document.querySelector('[data-http="CONNECTED"]'));
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-query-save-button"]'));
  const save = globalThis.document.querySelector('[data-testid="analytics-query-save-button"]');
  const join = globalThis.document.querySelector('[data-testid="analytics-query-join-button"]');
  await act(async () => { save.click(); await delay(20); });
  await waitFor(() => querySaveStatus().includes('已保存当前口径'));
  assert.equal(save.disabled, true);
  await act(async () => { join.click(); await delay(20); });
  await waitFor(() => querySaveStatus().includes('分析已保存；加入驾驶舱失败'));
  await act(async () => { save.click(); join.click(); await delay(20); });
  const analysisPosts = calls.filter(row => row.method === 'POST' && row.path === '/b0/analyses');
  assert.equal(analysisPosts.length, 1);
  const listed = await fetchImpl('/b0/analyses');
  const payload = await listed.json();
  assert.equal(payload.items.length, 1);
  assert.equal(payload.items[0].analysis_id, analysisDoc.analysis_id);
  mounted.unmount();
  restoreDom(previous);
});

test('two overlay instances keep preview save undo on their own dashboard_id', async () => {
  const { previous } = installDom();
  const boardA = { ...board, dashboard_id: 'dashboard_session_a', version: 4 };
  const boardB = { ...board, dashboard_id: 'dashboard_session_b', version: 7 };
  const { calls, fetchImpl, setListPrimary } = dualBoardFetch(boardA, boardB);
  const mounted = await mountDualOverlays(fetchImpl);
  await waitFor(() => instanceDialog(0)?.getAttribute('data-http') === 'CONNECTED'
    && instanceDialog(0)?.getAttribute('data-dashboard-id') === boardA.dashboard_id);
  setListPrimary(boardB.dashboard_id);
  await mounted.addSecond();
  await waitFor(() => instanceDialog(1)?.getAttribute('data-http') === 'CONNECTED'
    && instanceDialog(1)?.getAttribute('data-dashboard-id') === boardB.dashboard_id);
  assert.equal(instanceDialog(0).getAttribute('data-dashboard-id'), boardA.dashboard_id);

  const beforeA = boardWrites(calls).length;
  await act(async () => {
    instanceDialog(0).querySelector('[data-testid="analytics-cockpit-undo"]').click();
    await delay(20);
  });
  await waitFor(() => boardWrites(calls).length > beforeA);
  const undoA = boardWrites(calls).at(-1);
  assert.equal(undoA.path, `/b0/dashboards/${boardA.dashboard_id}/preview`);
  assert.equal(undoA.headers['if-match'], String(boardA.version));
  assert.equal(JSON.parse(undoA.body).op, 'undo');

  await act(async () => {
    instanceDialog(0).querySelector('[data-testid="analytics-cockpit-save"]').click();
    await delay(20);
  });
  await waitFor(() => boardWrites(calls).some(row => row.path === `/b0/dashboards/${boardA.dashboard_id}/versions`));
  const saveA = boardWrites(calls).find(row => row.path === `/b0/dashboards/${boardA.dashboard_id}/versions`);
  assert.equal(saveA.headers['if-match'], String(boardA.version));
  assert.equal(boardWrites(calls).some(row => row.path.includes(boardB.dashboard_id)), false);

  const beforeB = boardWrites(calls).length;
  await act(async () => {
    instanceDialog(1).querySelector('[data-action="copy"]').click();
    await delay(20);
  });
  await waitFor(() => boardWrites(calls).length > beforeB);
  const previewB = boardWrites(calls).at(-1);
  assert.equal(previewB.path, `/b0/dashboards/${boardB.dashboard_id}/preview`);
  assert.equal(previewB.headers['if-match'], String(boardB.version));

  await act(async () => {
    instanceDialog(1).querySelector('[data-testid="analytics-cockpit-save"]').click();
    await delay(20);
  });
  await waitFor(() => boardWrites(calls).some(row => row.path === `/b0/dashboards/${boardB.dashboard_id}/versions`));
  const aWrites = boardWrites(calls).filter(row => row.path.includes(`/b0/dashboards/${boardA.dashboard_id}/`));
  const bWrites = boardWrites(calls).filter(row => row.path.includes(`/b0/dashboards/${boardB.dashboard_id}/`));
  assert.ok(aWrites.length >= 2);
  assert.ok(bWrites.length >= 2);
  assert.equal(aWrites.every(row => !row.path.includes(boardB.dashboard_id)), true);
  assert.equal(bWrites.every(row => !row.path.includes(boardA.dashboard_id)), true);
  mounted.unmount();
  restoreDom(previous);
});

test('analyses panel sets data-panel=analyses, omits undo, and does not claim overlay hung', async () => {
  const { previous } = installDom();
  const { fetchImpl } = connectedBoardFetch();
  const mounted = await mountShell(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-cockpit-undo"]'));
  const dialog = globalThis.document.querySelector('[data-testid="analytics-b0-dialog"]');
  assert.equal(dialog.getAttribute('data-competition-panel'), 'board');
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-asset-analyses"]').click();
    await delay(10);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-saved-analysis-view"]'));
  assert.equal(dialog.getAttribute('data-competition-panel'), 'analyses');
  assert.ok(globalThis.document.querySelector('[data-panel="analyses"]'));
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-cockpit-undo"]'), null);
  const text = globalThis.document.documentElement?.textContent ?? '';
  assert.doesNotMatch(text, /overlay hung/i);
  assert.doesNotMatch(text, /hung/i);
  assert.doesNotMatch(text, /卡死/);
  mounted.unmount();
  restoreDom(previous);
});
