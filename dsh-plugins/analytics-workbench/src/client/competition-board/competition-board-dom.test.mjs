/** Compiled view DOM: endorsement, board grid, actions. Uses pinned React; mock transport only. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { readFileSync } from 'node:fs';
import { createFixtureBoardTransport, createHttpBoardTransport } from './transport.mjs';
import { createFixtureAudienceTransport, createHttpAudienceTransport } from '../competition-actions/transport.mjs';
import { AUDIENCE_SUCCESS } from '../competition-actions/c0-fixtures.mjs';
import { resetInflightForTests } from './selection.mjs';
import { BOARD_SUCCESS, RESULT_EMPTY, RESULT_SUCCESS } from './c0-fixtures.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const plugin = resolve(here, '../../..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const webReq = createRequire(join(upstream, 'apps/web/package.json'));
const React = webReq('react');
const { renderToStaticMarkup } = webReq('react-dom/server');
const { createRoot } = webReq('react-dom/client');
const act = typeof React.act === 'function' ? React.act : webReq('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const { CockpitView } = await import(pathToFileURL(join(plugin, 'lib/views/cockpit-view.js')).href);

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318/' });
  if (typeof dom.window.PointerEvent !== 'function') {
    dom.window.PointerEvent = class PointerEvent extends dom.window.MouseEvent {};
  }
  const previous = { window: globalThis.window, document: globalThis.document, sessionStorage: globalThis.sessionStorage,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT };
  previous.browserGlobals = new Map(['getComputedStyle', 'HTMLElement', 'Element', 'SVGElement', 'ShadowRoot'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const key of previous.browserGlobals.keys()) Object.defineProperty(globalThis, key, { configurable: true, writable: true, value: typeof dom.window[key] === 'function' && key === 'getComputedStyle' ? dom.window[key].bind(dom.window) : dom.window[key] });
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.sessionStorage = dom.window.sessionStorage;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return { dom, previous };
}

function restoreDom(previous) {
  for (const [key, descriptor] of previous.browserGlobals) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; }
  if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
  if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
  if (previous.sessionStorage === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previous.sessionStorage;
  if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
}

test('compiled board renders persisted computed GSV and data-driven chart preferences after reopen', async () => {
  const result = JSON.parse(readFileSync(join(plugin, 'tests/competition-computed/result.json'), 'utf8'));
  const { previous, dom } = installDom();
  resetInflightForTests();
  const transport = createFixtureBoardTransport();
  transport.listEndorseableResults = async () => ({ ok: true, status: 200, body: [result] });
  const withComputed = () => {
    const board = transport.getSavedBoard();
    board.blocks = board.blocks.map(block => ({ ...block, result, result_id: result.result_id, source_status: 'OK' }));
    return board;
  };
  transport.listBoards = async () => ({ ok: true, status: 200, body: [withComputed()] });
  transport.loadBoard = async () => ({ ok: true, status: 200, body: withComputed() });
  let root;
  const mount = async () => {
    root = createRoot(globalThis.document.getElementById('root'));
    await act(async () => { root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport })); await delay(20); });
    assert.match(globalThis.document.querySelector('[data-testid="sm-result-list"]').textContent, /本期 410 \/ 对比 305/);
    await act(() => globalThis.document.querySelector('[data-testid="sm-open-board"]').click());
    await waitFor(() => globalThis.document.querySelector('article[data-block-id] select'));
  };
  try {
    for (const type of ['BAR', 'LINE', 'METRIC']) {
      await mount();
      const select = globalThis.document.querySelector('article[data-block-id] select');
      await act(async () => { select.value = type; select.dispatchEvent(new dom.window.Event('change', { bubbles: true })); await delay(20); });
      await act(async () => { globalThis.document.querySelector('[data-testid="sm-board-save"]').click(); await delay(20); });
      await act(() => root.unmount()); root = null;
      await mount();
      const block = globalThis.document.querySelector('article[data-block-id]');
      assert.match(block.textContent, /本期 GSV410/);
      assert.match(block.textContent, /对比期 GSV305/);
      assert.match(block.textContent, /34.43%/);
      assert.match(block.textContent, /销售范围 全部/);
      const savedEvidence = block.querySelector('[data-testid="sm-saved-board-evidence"]');
      assert.equal(savedEvidence.open, false);
      assert.match(savedEvidence.textContent, /2025-08-01–2025-08-31/);
      assert.match(savedEvidence.textContent, /历史范围 全部/);
      assert.match(savedEvidence.textContent, new RegExp(result.evidence_digest.slice(0, 8)));
      assert.equal(block.querySelector('[data-testid="sm-chart-no-series"]'), null);
      if (type === 'BAR') {
        const bars = [...block.querySelectorAll('.sm-chart-bar-track > div')];
        assert.equal(bars.length, 2);
        assert.ok(Math.abs(parseFloat(bars[0].style.width) - 305 / 410 * 100) < 0.001);
        assert.equal(bars[1].style.width, '100%');
      } else if (type === 'LINE') {
        assert.ok(block.querySelector('[data-testid="sm-computed-line"] polyline'));
        assert.match(block.textContent, /非每日趋势/);
      } else assert.match(block.querySelector('[data-testid="sm-computed-metric"]').textContent, /410/);
      await act(() => root.unmount()); root = null;
    }
  } finally {
    if (root) await act(() => root.unmount());
    dom.window.close(); restoreDom(previous); resetInflightForTests();
  }
});

async function waitFor(check) {
  for (let i = 0; i < 40; i++) {
    if (check()) return;
    await act(async () => { await delay(15); });
  }
  throw new Error('competition-board DOM wait timeout');
}

test('compiled board reports disconnected service and a failed saved-board read instead of an empty success', async () => {
  for (const scenario of ['disconnected', 'board-list-failed', 'board-read-failed']) {
    const { previous, dom } = installDom();
    resetInflightForTests();
    const transport = createHttpBoardTransport({ fetchImpl: async path => {
      if (scenario === 'disconnected') throw new TypeError('Failed to fetch');
      if (path.endsWith('/results')) return { status: 200, json: async () => ({ items: [] }) };
      if (scenario === 'board-read-failed' && path.endsWith('/boards')) {
        return { status: 200, json: async () => ({ items: [{ board_id: 'unavailable-board' }] }) };
      }
      return { status: 502, json: async () => { throw new SyntaxError('not JSON'); } };
    } });
    const root = createRoot(document.getElementById('root'));
    try {
      await act(() => root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport })));
      await waitFor(() => document.querySelector('[data-testid="sm-error-state"]'));
      const error = document.querySelector('[data-testid="sm-error-state"]');
      assert.match(error.textContent, scenario === 'disconnected' ? /无法连接看板服务/ : /HTTP 502/);
      assert.doesNotMatch(document.body.textContent, /还没有可认可的结果/);
      assert.equal(document.querySelector('[data-testid="sm-confirm-boards"]').disabled, true);
      assert.equal(document.querySelector('[data-testid="sm-board-error-details"]').open, false);
    } finally {
      await act(() => root.unmount());
      dom.window.close(); restoreDom(previous); resetInflightForTests();
    }
  }
});

test('T04 compiled DOM preserves GSV 0.25 and formats only the raw ratio as 25%', async () => {
  const result = JSON.parse(readFileSync(join(plugin, 'tests/competition-computed/result.json'), 'utf8'));
  result.facts.current.gsv = 0.25;
  result.facts.comparison.gsv = 0.2;
  result.facts.difference = 0.05;
  result.facts.change_ratio = 0.25;
  const { previous, dom } = installDom();
  resetInflightForTests();
  const transport = createFixtureBoardTransport();
  const board = transport.getSavedBoard();
  board.blocks = board.blocks.map(block => ({ ...block, result, result_id: result.result_id, source_status: 'OK' }));
  transport.listEndorseableResults = async () => ({ ok: true, status: 200, body: [result] });
  transport.listBoards = async () => ({ ok: true, status: 200, body: [board] });
  transport.loadBoard = async () => ({ ok: true, status: 200, body: board });
  const root = createRoot(document.getElementById('root'));
  try {
    await act(async () => { root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport })); await delay(20); });
    await act(() => document.querySelector('[data-testid="sm-open-board"]').click());
    await waitFor(() => document.querySelector('article[data-block-id]'));
    const row = label => document.querySelector(`article [data-field="${label}"] td`).textContent;
    assert.equal(row('本期 GSV'), '0.25');
    assert.equal(row('对比期 GSV'), '0.2');
    assert.equal(row('GSV 变动额'), '0.05');
    assert.equal(row('GSV 变动比例'), '25.00%');
  } finally {
    await act(() => root.unmount());
    dom.window.close(); restoreDom(previous); resetInflightForTests();
  }
});

test('chart preference enables save and survives component reopen, bound to the changed block', async () => {
  resetInflightForTests();
  const { previous, dom } = installDom();
  const transport = createFixtureBoardTransport();
  transport.listBoards = async () => ({ ok: true, status: 200, body: [transport.getSavedBoard()] });
  let root;
  const mount = async () => {
    root = createRoot(globalThis.document.getElementById('root'));
    await act(async () => {
      root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport }));
      await delay(20);
    });
    await waitFor(() => globalThis.document.querySelector('[data-testid="sm-result-list"] li'));
    await act(() => globalThis.document.querySelector('[data-testid="sm-open-board"]').click());
    await waitFor(() => globalThis.document.querySelector('article[data-block-id] select'));
  };
  try {
    await mount();
    const id = transport.getSavedBoard().block_ids.at(-1);
    const firstId = transport.getSavedBoard().block_ids[0];
    const firstPlugin = transport.getSavedBoard().blocks[0].plugin;
    for (const plugin of ['LINE', 'METRIC', 'EVIDENCE', 'TABLE', 'BAR']) {
      const selector = `article[data-block-id="${id}"] select`;
      await act(async () => {
        const select = globalThis.document.querySelector(selector);
        select.value = plugin;
        select.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
        await delay(20);
      });
      const save = globalThis.document.querySelector('[data-testid="sm-board-save"]');
      assert.equal(save.disabled, false, 'chart change must create a saveable preview');
      assert.equal(transport.getPendingPatch().block_id, id);
      const chartAttempt = transport.getPendingPatch().attempt_id;
      await act(async () => {
        globalThis.document.querySelector('[data-testid="sm-competition-board"]').dispatchEvent(
          new dom.window.KeyboardEvent('keydown', { key: 'ArrowDown', altKey: true, bubbles: true }));
        await delay(20);
      });
      assert.equal(transport.getPendingPatch().attempt_id, chartAttempt,
        'layout interaction must not replace an unsaved chart preference');
      if (['LINE', 'BAR', 'METRIC'].includes(plugin)) {
        const block = globalThis.document.querySelector(`article[data-block-id="${id}"]`);
        assert.match(block.querySelector('[data-testid="sm-chart-no-series"]').textContent, /暂无可绘制的数值序列/);
        assert.equal(block.querySelector('polyline, .sm-chart-bar-track'), null);
      }
      await act(async () => { save.click(); await delay(20); });
      assert.equal(transport.getSavedBoard().blocks.find(block => block.block_id === id).plugin, plugin);
      if (firstId !== id) assert.equal(transport.getSavedBoard().blocks[0].plugin, firstPlugin);
      await act(() => root.unmount());
      await mount();
      assert.equal(globalThis.document.querySelector(selector).value, plugin);
      assert.equal(globalThis.document.querySelector('[data-testid="sm-board-save"]').disabled, true);
    }
    const selector = `article[data-block-id="${id}"] select`;
    const choose = async plugin => act(async () => {
      const select = globalThis.document.querySelector(selector);
      select.value = plugin;
      select.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
      await delay(20);
    });
    await choose('LINE');
    await act(() => root.unmount());
    await mount();
    const resume = [...globalThis.document.querySelectorAll('button')].find(button => button.textContent === '继续编辑草稿');
    assert.ok(resume, 'unfinished preview must be offered after reopening');
    await act(async () => { resume.click(); await delay(20); });
    assert.equal(globalThis.document.querySelector(selector).value, 'LINE', 'resume must reload the actual preview');
    await act(async () => { globalThis.document.querySelector('[data-testid="sm-board-save"]').click(); await delay(20); });
    await choose('EVIDENCE');
    await act(() => root.unmount());
    await mount();
    const discard = [...globalThis.document.querySelectorAll('button')].find(button => button.textContent === '放弃浏览器草稿');
    await act(() => discard.click());
    assert.equal(globalThis.document.querySelector(selector).value, 'LINE', 'discard must retain the saved chart');
    await choose('TABLE');
    assert.equal(transport.getPendingPatch().chart_type, 'TABLE', 'discard must release the old in-flight target');
  } finally {
    if (root) await act(() => root.unmount());
    dom.window.close(); restoreDom(previous); resetInflightForTests();
  }
});

test('compiled B0 cockpit view still renders empty/denied without competition surface', () => {
  const empty = renderToStaticMarkup(React.createElement(CockpitView, { list: [], sessionId: null }));
  assert.match(empty, /data-testid="analytics-cockpit-view"/);
  assert.match(empty, /data-kind="empty"/);
  assert.match(empty, /data-http="NOT_CONNECTED"/);
  const denied = renderToStaticMarkup(React.createElement(CockpitView, {
    error: { status: 403, code: 'FORBIDDEN', message: 'SENSITIVE_FIXTURE' },
  }));
  assert.match(denied, /当前身份不可见/);
  assert.doesNotMatch(denied, /SENSITIVE_FIXTURE/);
});

test('compiled competition board surface explains manual editing without claiming native model unavailable', () => {
  const html = renderToStaticMarkup(React.createElement(CockpitView, {
    surface: 'competition-board', modelAvailable: false,
  }));
  assert.match(html, /data-testid="sm-competition-board"/);
  assert.match(html, /data-model="0"/);
  assert.match(html, /此看板入口提供手动编辑/);
  assert.doesNotMatch(html, /模型不可用/);
  assert.match(html, /一板多块/);
  assert.match(html, /批量分板/);
  assert.match(html, /data-testid="sm-endorsement"/);
  assert.doesNotMatch(html, /linear-gradient\([^)]*#805D9D/);
});

test('compiled actions surface shows zero-copy and no auto send', () => {
  const html = renderToStaticMarkup(React.createElement(CockpitView, {
    surface: 'competition-actions', modelAvailable: false,
  }));
  assert.match(html, /data-testid="sm-competition-actions"/);
  assert.match(html, /data-auto-send="0"/);
  assert.match(html, /data-testid="sm-no-auto-send"/);
  assert.match(html, /auto_send=false/);
  assert.match(html, /AND/);
});

test('board DOM: endorse COMPLETE, reject empty, preview layout on pointerup not pointermove, 409 keeps draft', async () => {
  resetInflightForTests();
  const { previous } = installDom();
  const transport = createFixtureBoardTransport({ scenario: 'success' });
  const root = createRoot(globalThis.document.getElementById('root'));
  await act(() => {
    root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport, modelAvailable: false }));
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-result-list"] li'));
  const items = [...globalThis.document.querySelectorAll('[data-testid="sm-result-list"] li')];
  assert.ok(items.some(row => row.getAttribute('data-completeness') === 'COMPLETE'));
  assert.ok(items.some(row => row.getAttribute('data-completeness') === 'EMPTY'));
  const emptyBox = items.find(row => row.getAttribute('data-completeness') === 'EMPTY').querySelector('input[type="checkbox"]');
  assert.equal(emptyBox.disabled, true);
  const completeBox = items.find(row => row.getAttribute('data-completeness') === 'COMPLETE').querySelector('input[type="checkbox"]');
  await act(() => { completeBox.click(); });
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-board-grid"]'));
  await act(() => {
    globalThis.document.querySelector('[data-block-id="card_c0_block_1"]').click();
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-drag-card_c0_block_1"]'));
  const previewBefore = transport.getPendingPatch();
  const drag = globalThis.document.querySelector('[data-testid="sm-drag-card_c0_block_1"]');
  await act(() => {
    drag.dispatchEvent(new globalThis.window.PointerEvent('pointerdown', { bubbles: true, clientX: 0, clientY: 0 }));
  });
  await act(() => {
    globalThis.window.dispatchEvent(new globalThis.window.PointerEvent('pointermove', { bubbles: true, clientX: 96, clientY: 0 }));
  });
  assert.equal(transport.getPendingPatch(), previewBefore);
  await act(async () => {
    globalThis.window.dispatchEvent(new globalThis.window.PointerEvent('pointerup', { bubbles: true, clientX: 96, clientY: 0 }));
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-preview-hint"]'));
  assert.match(globalThis.document.querySelector('[data-testid="sm-board-status"]').textContent, /预览未保存/);

  transport.setScenario('conflict_409');
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-board-save"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-error-state"]'));
  assert.equal(globalThis.document.querySelector('[data-testid="sm-error-state"]').getAttribute('data-kind'), 'conflict');
  assert.match(globalThis.document.body.textContent, /未覆盖/);
  root.unmount();
  restoreDom(previous);
  resetInflightForTests();
});

test('actions DOM: AND count, zero audience, copy-only vs expired draft', async () => {
  const { previous } = installDom();
  const transport = createFixtureAudienceTransport({ scenario: 'success' });
  const root = createRoot(globalThis.document.getElementById('root'));
  await act(() => {
    root.render(React.createElement(CockpitView, {
      surface: 'competition-actions', audienceTransport: transport, modelAvailable: false,
    }));
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-preview-candidates"]'));
  await waitFor(() => globalThis.document.body.textContent.includes('draft_c0_1'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-preview-candidates"]').click();
    await delay(30);
  });
  await waitFor(() => (globalThis.document.querySelector('[data-testid="sm-candidate-count"]')?.textContent ?? '').includes('unique_count=2'));
  assert.match(globalThis.document.querySelector('[data-testid="sm-candidate-explanations"]').textContent, /ORIGIN_CHANNEL_ABSENT/);

  transport.setScenario('empty');
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-preview-candidates"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-zero="1"]'));
  assert.match(globalThis.document.body.textContent, /零人群|零候选/);

  transport.setScenario('success');
  // A newly previewed candidate set starts a separate draft; it must not
  // silently retarget the previous draft's immutable candidate binding.
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-create-draft"]').click();
    await delay(20);
  });
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-save-copy"]').click();
    await delay(20);
  });
  await waitFor(() => (globalThis.document.querySelector('[data-testid="sm-actions-status"]')?.textContent ?? '').includes('未过期'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-mark-rule-change"]').click();
    await delay(20);
  });
  await waitFor(() => globalThis.document.querySelector('[data-expired="1"]'));
  assert.equal(globalThis.document.querySelector('[data-testid="sm-auto-send"]').disabled, true);
  root.unmount();
  restoreDom(previous);
});

function sparseHttpResult() {
  const row = JSON.parse(JSON.stringify(RESULT_SUCCESS));
  delete row.row_count;
  delete row.resolved_condition.history_scope;
  delete row.resolved_condition.sales_scope;
  delete row.resolved_condition.cutoff;
  delete row.resolved_condition.sample_mode;
  return row;
}

test('HTTP-shaped sparse result: confirm panel does not throw, 行数 is not undefined', async () => {
  resetInflightForTests();
  const { previous } = installDom();
  const transport = createFixtureBoardTransport({
    results: [sparseHttpResult(), JSON.parse(JSON.stringify(RESULT_EMPTY))],
  });
  const root = createRoot(globalThis.document.getElementById('root'));
  await act(() => {
    root.render(React.createElement(CockpitView, {
      surface: 'competition-board', boardTransport: transport, modelAvailable: false,
    }));
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-result-list"] li'));
  const completeBox = [...globalThis.document.querySelectorAll('[data-testid="sm-result-list"] li')]
    .find(row => row.getAttribute('data-completeness') === 'COMPLETE')
    .querySelector('input[type="checkbox"]');
  await act(() => { completeBox.click(); });
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click();
    await delay(30);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-board-grid"]'));
  assert.ok(globalThis.document.querySelector('[data-testid="sm-competition-board"]'));
  assert.equal(globalThis.document.querySelector('[data-testid="sm-overlay-render-error"]'), null);
  const rowCount = globalThis.document.querySelector('[data-field="行数"] td')?.textContent;
  assert.ok(rowCount);
  assert.notEqual(rowCount, 'undefined');
  assert.match(rowCount, /^(\d+|—)$/);
  assert.doesNotMatch(globalThis.document.body.textContent, /行数\s*undefined/);
  assert.match(globalThis.document.querySelector('[data-testid="sm-board-status"]').textContent, /已按认可结果成板/);
  root.unmount();
  restoreDom(previous);
  resetInflightForTests();
});

test('failed 成板 retry stays mounted and does not duplicate the board', async () => {
  resetInflightForTests();
  const { previous } = installDom();
  const transport = createFixtureBoardTransport({ scenario: 'fail_once' });
  const root = createRoot(globalThis.document.getElementById('root'));
  await act(() => {
    root.render(React.createElement(CockpitView, {
      surface: 'competition-board', boardTransport: transport, modelAvailable: false,
    }));
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-result-list"] li'));
  const completeBox = [...globalThis.document.querySelectorAll('[data-testid="sm-result-list"] li')]
    .find(row => row.getAttribute('data-completeness') === 'COMPLETE')
    .querySelector('input[type="checkbox"]');
  await act(() => { completeBox.click(); });
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click();
    await delay(30);
  });
  await waitFor(() => (globalThis.document.querySelector('[data-testid="sm-board-status"]')?.textContent ?? '').includes('可重试'));
  assert.ok(globalThis.document.querySelector('[data-testid="sm-competition-board"]'));
  assert.equal(globalThis.document.querySelector('[data-testid="sm-board-grid"]'), null);
  const firstId = transport.getSavedBoard().board_id;
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click();
    await delay(30);
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-board-grid"]'));
  const createdId = transport.getSavedBoard().board_id;
  await act(() => {
    [...globalThis.document.querySelectorAll('button')].find(row => row.textContent === '选择结果').click();
  });
  await waitFor(() => globalThis.document.querySelector('[data-testid="sm-confirm-boards"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click();
    await delay(20);
  });
  assert.equal(transport.getSavedBoard().board_id, createdId);
  assert.equal(transport.getApplyCount(), 3);
  assert.equal(createdId, firstId);
  root.unmount();
  restoreDom(previous);
  resetInflightForTests();
});

test('HTTP board reopens pinned result and layout; unavailable binding never substitutes list results', async () => {
  for (const unavailable of [false, true]) {
    const { previous, dom } = installDom();
    const spec = { ...structuredClone(BOARD_SUCCESS.board), block_ids: ['block_saved_b'] };
    const a = { ...structuredClone(RESULT_SUCCESS), result_id: 'result_A', query_id: 'query_A' };
    const b = { ...structuredClone(RESULT_SUCCESS), result_id: 'result_B', query_id: 'query_B', row_count: 77 };
    const document = { spec, blocks: [{ block_id: 'block_saved_b', result_id: 'result_B',
      result: unavailable ? undefined : b, source_status: unavailable ? 'UNAVAILABLE' : 'OK',
      layout: { x: 6, y: 9, w: 4, h: 4 }, display_overrides: { title: 'saved block B' } }] };
    const transport = createHttpBoardTransport({ fetchImpl: async path => ({ status: 200, json: async () =>
      path.endsWith('/results') ? { items: [a] } : path.endsWith('/boards') ? { items: [spec] } : document }) });
    const root = createRoot(globalThis.document.getElementById('root'));
    try {
      await act(() => root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport })));
      await waitFor(() => globalThis.document.querySelector('[data-testid="sm-result-list"] li'));
      await act(() => globalThis.document.querySelector('[data-testid="sm-open-board"]').click());
      await waitFor(() => globalThis.document.querySelector('[data-block-id="block_saved_b"]'));
      const block = globalThis.document.querySelector('[data-block-id="block_saved_b"]');
      assert.equal(block.style.gridColumn, '7 / span 4');
      assert.equal(block.style.gridRow, '10 / span 4');
      assert.match(block.textContent, /saved block B/);
      assert.doesNotMatch(block.textContent, /query_A/);
      if (unavailable) assert.doesNotMatch(block.textContent, /query_B|77/);
      else { assert.match(block.textContent, /query_B/); assert.equal(block.querySelector('[data-field="行数"] td').textContent, '77'); }
    } finally { await act(() => root.unmount()); dom.window.close(); restoreDom(previous); resetInflightForTests(); }
  }
});

test('HTTP create retries keep IDs, next selection creates a distinct board, preview does not write', async () => {
  const { previous, dom } = installDom();
  const rows = ['A', 'B'].map(letter => ({ ...structuredClone(RESULT_SUCCESS), result_id: `result_${letter}` }));
  const boards = new Map();
  const requests = [];
  let loseFirstResponse = true;
  const fetchImpl = async (path, options) => {
    if (options.method === 'POST') {
      assert.ok(path.endsWith('/batches'));
      const payload = JSON.parse(options.body);
      requests.push(payload);
      const existing = boards.get(payload.batch_id);
      if (existing) assert.deepEqual(existing.payload, payload);
      else {
        const spec = { ...structuredClone(BOARD_SUCCESS.board), board_id: `board_${boards.size + 1}`,
          block_ids: ['block_created'], version: 1, base_version: 1 };
        const ref = payload.operations[0].endorsed_result_refs[0];
        boards.set(payload.batch_id, { payload, spec, blocks: [{ block_id: 'block_created', result_id: ref.result_id,
          result: rows.find(row => row.result_id === ref.result_id), layout: { x: 0, y: 0, w: 6, h: 4 } }] });
      }
      if (loseFirstResponse) { loseFirstResponse = false; throw new Error('synthetic response lost after commit'); }
      const board = boards.get(payload.batch_id).spec;
      return { status: 200, json: async () => ({ status: 'SUCCEEDED', board, items: [{ board_id: board.board_id }] }) };
    }
    const body = path.endsWith('/results') ? { items: rows }
      : path.endsWith('/boards') ? { items: [...boards.values()].map(row => row.spec) }
        : [...boards.values()].find(row => path.endsWith('/' + row.spec.board_id));
    return { status: 200, json: async () => body };
  };
  const transport = createHttpBoardTransport({ fetchImpl });
  const root = createRoot(globalThis.document.getElementById('root'));
  try {
    await act(() => root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport })));
    await waitFor(() => globalThis.document.querySelectorAll('[data-testid="sm-result-list"] input').length === 2);
    await act(() => globalThis.document.querySelector('[data-testid="sm-result-list"] input').click());
    await act(async () => { globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click(); await delay(20); });
    assert.equal(requests.length, 1);
    assert.equal(boards.size, 1);
    await act(async () => { globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click(); await delay(20); });
    assert.equal(requests.length, 2);
    assert.deepEqual(requests[0], requests[1]);
    assert.equal(boards.size, 1);
    await act(() => [...globalThis.document.querySelectorAll('button')].find(button => button.textContent === '选择结果').click());
    const boxes = globalThis.document.querySelectorAll('[data-testid="sm-result-list"] input');
    await act(() => { boxes[0].click(); boxes[1].click(); });
    await act(async () => { globalThis.document.querySelector('[data-testid="sm-confirm-boards"]').click(); await delay(20); });
    assert.equal(boards.size, 2);
    assert.notEqual(requests[2].batch_id, requests[0].batch_id);
    assert.notEqual(requests[2].operations[0].operation_id, requests[0].operations[0].operation_id);
  } finally { await act(() => root.unmount()); dom.window.close(); restoreDom(previous); resetInflightForTests(); }
});

test('HTTP actions can create first draft, reopen with a new transport, then update same versioned draft', async () => {
  const { previous, dom } = installDom();
  const pack = structuredClone(AUDIENCE_SUCCESS);
  let saved = null;
  let root;
  const writes = [];
  const fetchImpl = async (path, options) => {
    if (path.endsWith('/candidates/preview')) return { status: 200, json: async () => ({ candidates: pack.candidates, cohort: pack.cohort }) };
    if (options.method === 'POST') {
      const payload = JSON.parse(options.body); writes.push(payload);
      saved = { ...pack.draft, draft_id: 'draft_new', candidate_set_id: pack.candidates.candidate_set_id,
        version: (saved?.version || 0) + 1, control_design: payload.control_design, stop_condition: payload.stop_condition };
      return { status: 200, json: async () => saved };
    }
    return { status: 200, json: async () => ({ draft: saved, candidates: saved ? pack.candidates : null, cohort: saved ? pack.cohort : null }) };
  };
  try {
    root = createRoot(globalThis.document.getElementById('root'));
    await act(() => root.render(React.createElement(CockpitView, { surface: 'competition-actions', audienceTransport: createHttpAudienceTransport({ fetchImpl }) })));
    await act(async () => { globalThis.document.querySelector('[data-testid="sm-preview-candidates"]').click(); await delay(20); });
    await waitFor(() => globalThis.document.querySelector('[data-testid="sm-create-draft"]'));
    await act(async () => { globalThis.document.querySelector('[data-testid="sm-create-draft"]').click(); await delay(20); });
    assert.equal(writes.length, 1);
    await act(() => root.unmount());
    root = createRoot(globalThis.document.getElementById('root'));
    await act(() => root.render(React.createElement(CockpitView, { surface: 'competition-actions', audienceTransport: createHttpAudienceTransport({ fetchImpl }) })));
    await waitFor(() => globalThis.document.querySelector('[data-testid="sm-save-copy"]'));
    assert.match(globalThis.document.querySelector('[data-testid="sm-draft-panel"]').textContent, /draft_new/);
    await act(async () => { globalThis.document.querySelector('[data-testid="sm-save-copy"]').click(); await delay(20); });
    assert.equal(writes[1].draft_id, 'draft_new');
    assert.equal(writes[1].base_version, 1);
    assert.equal(writes[1].candidate_set_id, pack.candidates.candidate_set_id);
  } finally { if (root) await act(() => root.unmount()); dom.window.close(); restoreDom(previous); }
});


test('saved-board picker loads each authorized board, preserves selection on reopen and locks unsaved edits', async () => {
  // A fresh compiled module keeps deliberately retained attempts in other cases isolated.
  const { CockpitView } = await import(pathToFileURL(join(plugin, 'lib/views/cockpit-view.js')).href + '?picker=switch');
  const { previous, dom } = installDom(); resetInflightForTests();
  const a = { ...structuredClone(createFixtureBoardTransport().getSavedBoard()), title: 'First saved board' };
  const b = { ...structuredClone(createFixtureBoardTransport().getSavedBoard()), board_id: 'dash_c0_board_b', title: 'Second saved board' };
  const transport = createFixtureBoardTransport();
  const reads = [], patches = [];
  transport.listBoards = async () => ({ ok: true, status: 200, body: [a, b] });
  transport.loadBoard = async id => { reads.push(id); return { ok: true, status: 200, body: structuredClone(id === b.board_id ? b : a) }; };
  transport.previewPatch = async (_actor, patch) => { patches.push(patch); return { ok: true, status: 200, body: { ...structuredClone(b), preview: true } }; };
  let root;
  const mount = async () => {
    root = createRoot(document.getElementById('root'));
    await act(async () => { root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport })); await delay(20); });
    await act(() => document.querySelector('[data-testid="sm-open-board"]').click());
  };
  try {
    await mount();
    assert.ok(document.querySelector('[aria-label="选择已保存看板"]'), 'saved assets must be selectable');
    await act(() => document.querySelector('.sm-board-picker .ant-select-selector').dispatchEvent(new dom.window.MouseEvent('mousedown', { bubbles: true })));
    const option = [...document.querySelectorAll('[role="option"]')].find(el => el.textContent.includes('Second saved board'));
    assert.ok(option); await act(async () => { option.click(); await delay(20); });
    assert.equal(reads.at(-1), b.board_id);
    await act(() => root.unmount()); root = null;
    await mount();
    assert.equal(reads.at(-1), b.board_id, 'reopen honors an authorized selected board');
    const block = document.querySelector('article[data-block-id]');
    await act(() => block.click());
    const select = block.querySelector('select');
    await act(async () => { select.value = 'BAR'; select.dispatchEvent(new dom.window.Event('change', { bubbles: true })); await delay(20); });
    assert.equal(patches.length, 1); assert.equal(patches[0].board_id, b.board_id);
    assert.equal(document.querySelector('.sm-board-picker input[role="combobox"]').disabled, true);
    await act(() => [...document.querySelectorAll('[data-testid="sm-board-editor"] button')].find(el => el.textContent === '放弃预览').click());
    await act(() => document.querySelector('[data-testid="sm-discard-preview"]').click());
    assert.equal(document.querySelector('.sm-board-picker input[role="combobox"]').disabled, false);
  } finally { if (root) await act(() => root.unmount()); dom.window.close(); restoreDom(previous); resetInflightForTests(); }
});


test('board switching keeps the prior asset on denial and does not restore an unlisted preference', async () => {
  const { CockpitView } = await import(pathToFileURL(join(plugin, 'lib/views/cockpit-view.js')).href + '?picker=denial');
  const { previous, dom } = installDom(); resetInflightForTests();
  const transport = createFixtureBoardTransport();
  const a = { ...structuredClone(transport.getSavedBoard()), title: 'Accessible board' };
  const b = { ...structuredClone(a), board_id: 'dash_c0_board_b', title: 'Denied board' };
  let rows = [a, b], deny = false, gate; const reads = [];
  transport.listBoards = async () => ({ ok: true, status: 200, body: rows });
  transport.loadBoard = async id => {
    reads.push(id);
    if (id === b.board_id && deny) {
      await new Promise(resolve => { gate = resolve; });
      return { ok: false, status: 403, body: { error: { code: 'FORBIDDEN', http_status: 403, message: 'Board access revoked', request_id: 'picker-denied' } } };
    }
    return { ok: true, status: 200, body: structuredClone(id === b.board_id ? b : a) };
  };
  let root;
  const mount = async () => {
    root = createRoot(document.getElementById('root'));
    await act(async () => { root.render(React.createElement(CockpitView, { surface: 'competition-board', boardTransport: transport })); await delay(20); });
    await act(() => document.querySelector('[data-testid="sm-open-board"]').click());
  };
  const chooseB = async () => {
    await act(() => document.querySelector('.sm-board-picker .ant-select-selector').dispatchEvent(new dom.window.MouseEvent('mousedown', { bubbles: true })));
    await act(() => [...document.querySelectorAll('[role="option"]')].find(el => el.textContent.includes('Denied board')).click());
  };
  try {
    await mount(); deny = true; await chooseB();
    assert.equal(document.querySelector('[data-testid="sm-scope-send"]'), null, 'no edits while the new board is loading');
    await act(async () => { gate(); await delay(20); });
    assert.match(document.querySelector('[data-testid="sm-error-state"]').textContent, /Board access revoked/);
    assert.match(document.querySelector('.sm-board-picker .ant-select-selection-item').textContent, /Accessible board/);
    deny = false; await chooseB(); await act(async () => { await delay(20); });
    assert.match(document.querySelector('.sm-board-picker .ant-select-selection-item').textContent, /Denied board/);
    await act(() => root.unmount()); root = null; rows = [a]; reads.length = 0;
    await mount();
    assert.deepEqual(reads, [a.board_id], 'revoked saved preference must not bypass the current list');
  } finally { if (root) await act(() => root.unmount()); dom.window.close(); restoreDom(previous); resetInflightForTests(); }
});
