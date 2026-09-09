/** Compiled view DOM: endorsement, board grid, actions. Uses pinned React; mock transport only. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { createFixtureBoardTransport } from './transport.mjs';
import { createFixtureAudienceTransport } from '../competition-actions/transport.mjs';
import { resetInflightForTests } from './selection.mjs';
import { RESULT_EMPTY, RESULT_SUCCESS } from './c0-fixtures.mjs';

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
  const previous = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return { dom, previous };
}

function restoreDom(previous) {
  if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
  if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
  if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
}

async function waitFor(check) {
  for (let i = 0; i < 40; i++) {
    if (check()) return;
    await act(async () => { await delay(15); });
  }
  throw new Error('competition-board DOM wait timeout');
}

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

test('compiled competition board surface shows endorsement and model-unavailable banner', () => {
  const html = renderToStaticMarkup(React.createElement(CockpitView, {
    surface: 'competition-board', modelAvailable: false,
  }));
  assert.match(html, /data-testid="sm-competition-board"/);
  assert.match(html, /data-model="0"/);
  assert.match(html, /模型不可用/);
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
