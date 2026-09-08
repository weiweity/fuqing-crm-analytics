/** Click compiled query save/join; mock same-origin asset HTTP only. Not a native session. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
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
const successBlock = QUERY_CARD_CASES.find(row => row.id === 'query-success').block;
const board = {
  schema_version: 'analytics-cockpit/v1', http_api: 'CONNECTED', dashboard_id: 'dashboard_1', version: 1, cards: [],
};

function jsonResponse(status, payload) {
  return {
    status,
    json: async () => payload,
    headers: { get: () => null },
  };
}

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',
    { url: 'http://127.0.0.1:4318/' });
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

async function mountCard(fetchImpl) {
  let factory;
  const context = {
    window: Object.assign(globalThis.window, { __ModuleLoader__: { load: row => { factory = row; } }, fetch: fetchImpl }),
    document: globalThis.document,
    fetch: fetchImpl,
    Event: globalThis.window.Event,
    CustomEvent: globalThis.window.CustomEvent,
  };
  vm.runInNewContext(source, context, { timeout: 2000 });
  const api = factory.factory(name => {
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return webReq('react/jsx-runtime');
    if (name === '@deepseek-ai/dsh-client-store') return stores;
    throw new Error(`unexpected ${name}`);
  });
  const registrations = [];
  api.apply({ effect: () => {}, sessions: {}, slots: { inject: (_, fn) => fn(), register: (options, component) => {
    registrations.push({ options, component }); return () => {};
  } } });
  const queryCard = registrations.find(row => row.options.key === QUERY_TOOL_NAME);
  assert.ok(queryCard);
  globalThis.fetch = fetchImpl;
  const rootEl = globalThis.document.getElementById('root');
  const root = createRoot(rootEl);
  await act(() => { root.render(React.createElement(queryCard.component, {
    block: successBlock, callId: successBlock.callId, toolName: QUERY_TOOL_NAME,
  })); });
  return { unmount: () => act(() => root.unmount()) };
}

async function waitFor(check) {
  for (let i = 0; i < 40; i++) {
    if (check()) return;
    await act(async () => { await delay(15); });
  }
  throw new Error('query-card-save wait timeout');
}

function statusText() {
  return globalThis.document.querySelector('[data-testid="analytics-query-save-status"]')?.textContent ?? '';
}

test('save then join creates an owner board and posts add with board-version key', async () => {
  const { previous } = installDom();
  const calls = [];
  const fetchImpl = async (url, options = {}) => {
    const path = String(url);
    const method = options.method ?? 'GET';
    calls.push({ method, path, headers: options.headers ?? {}, body: options.body });
    if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
    if (method === 'POST' && path === '/b0/analyses') {
      return jsonResponse(201, { analysis_id: 'analysis_1', version: 1 });
    }
    if (method === 'GET' && path === '/b0/dashboards') return jsonResponse(200, { items: [] });
    if (method === 'POST' && path === '/b0/dashboards') return jsonResponse(201, board);
    if (method === 'POST' && path === '/b0/dashboards/dashboard_1/versions') return jsonResponse(201, board);
    throw new Error(`unexpected ${method} ${path}`);
  };
  const mounted = await mountCard(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-query-save-button"]'));
  const save = globalThis.document.querySelector('[data-testid="analytics-query-save-button"]');
  const join = globalThis.document.querySelector('[data-testid="analytics-query-join-button"]');
  assert.equal(join.disabled, true);
  await act(async () => { save.click(); await delay(20); });
  await waitFor(() => statusText().includes('已保存当前口径'));
  assert.equal(join.disabled, false);
  const saved = calls.find(row => row.method === 'POST' && row.path === '/b0/analyses');
  assert.equal(saved.headers['idempotency-key'], 'save-run_1');
  assert.equal(JSON.parse(saved.body).created_from_run_id, 'run_1');
  await act(async () => { join.click(); await delay(20); });
  await waitFor(() => statusText().includes('已加入我的驾驶舱'));
  const created = calls.find(row => row.method === 'POST' && row.path === '/b0/dashboards');
  assert.equal(created.headers['idempotency-key'], 'board-owner');
  const added = calls.find(row => row.path === '/b0/dashboards/dashboard_1/versions');
  assert.equal(added.headers['idempotency-key'], 'add-analysis_1-v1-b1');
  assert.equal(added.headers['if-match'], '1');
  assert.equal(JSON.parse(added.body).op, 'add');
  mounted.unmount();
  restoreDom(previous);
});

test('save surfaces contract errors and malformed payloads without treating them as saved', async () => {
  for (const mode of [
    { id: 'http-error', status: 422, payload: { error: { code: 'UNPROCESSABLE', message: '保存分析缺少合法冻结 SNAPSHOT。' } }, expect: '保存分析缺少合法冻结 SNAPSHOT。' },
    { id: 'malformed', status: 201, payload: { title: '缺标识' }, expect: '资产请求失败。' },
  ]) {
    const { previous } = installDom();
    const fetchImpl = async (url, options = {}) => {
      const path = String(url);
      if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
      if ((options.method ?? 'GET') === 'POST' && path === '/b0/analyses') return jsonResponse(mode.status, mode.payload);
      throw new Error(`unexpected ${path}`);
    };
    const mounted = await mountCard(fetchImpl);
    await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-query-save-button"]'));
    await act(async () => {
      globalThis.document.querySelector('[data-testid="analytics-query-save-button"]').click();
      await delay(20);
    });
    await waitFor(() => statusText().includes(mode.expect));
    assert.equal(globalThis.document.querySelector('[data-testid="analytics-query-join-button"]').disabled, true);
    mounted.unmount();
    restoreDom(previous);
  }
});

test('join keeps the analysis saved when listing the board fails', async () => {
  const { previous } = installDom();
  const fetchImpl = async (url, options = {}) => {
    const path = String(url);
    const method = options.method ?? 'GET';
    if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
    if (method === 'POST' && path === '/b0/analyses') return jsonResponse(201, { analysis_id: 'analysis_1', version: 1 });
    if (method === 'GET' && path === '/b0/dashboards') {
      return jsonResponse(503, { error: { code: 'UNAVAILABLE', message: '驾驶舱状态暂不可用。' } });
    }
    throw new Error(`unexpected ${method} ${path}`);
  };
  const mounted = await mountCard(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-query-save-button"]'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-query-save-button"]').click();
    await delay(20);
  });
  await waitFor(() => statusText().includes('已保存当前口径'));
  await act(async () => {
    globalThis.document.querySelector('[data-testid="analytics-query-join-button"]').click();
    await delay(20);
  });
  await waitFor(() => statusText().includes('分析已保存；加入驾驶舱失败'));
  assert.match(statusText(), /驾驶舱状态暂不可用/);
  mounted.unmount();
  restoreDom(previous);
});

test('save 201 then dashboard 4xx/409 does not POST a second analysis; join retries joinAttempt only', async () => {
  for (const joinStatus of [409, 422]) {
    const { previous } = installDom();
    const calls = [];
    const analysisDoc = {
      analysis_id: `analysis_keep_${joinStatus}`,
      version: 1,
      title: '渠道后续购买 N=30',
      http_api: 'CONNECTED',
    };
    const fetchImpl = async (url, options = {}) => {
      const path = String(url);
      const method = options.method ?? 'GET';
      calls.push({ method, path, headers: options.headers ?? {}, body: options.body });
      if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
      if (method === 'POST' && path === '/b0/analyses') {
        return jsonResponse(201, analysisDoc);
      }
      if (method === 'GET' && path === '/b0/analyses') {
        return jsonResponse(200, { items: [analysisDoc] });
      }
      if (method === 'GET' && path === '/b0/dashboards') return jsonResponse(200, { items: [board] });
      if (method === 'GET' && path === '/b0/dashboards/dashboard_1') return jsonResponse(200, board);
      if (method === 'POST' && path === '/b0/dashboards/dashboard_1/versions') {
        return jsonResponse(joinStatus, { error: { code: joinStatus === 409 ? 'CONFLICT' : 'UNPROCESSABLE', message: '驾驶舱版本冲突。' } });
      }
      throw new Error(`unexpected ${method} ${path}`);
    };
    const mounted = await mountCard(fetchImpl);
    await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-query-save-button"]'));
    const save = globalThis.document.querySelector('[data-testid="analytics-query-save-button"]');
    const join = globalThis.document.querySelector('[data-testid="analytics-query-join-button"]');
    await act(async () => { save.click(); await delay(20); });
    await waitFor(() => statusText().includes('已保存当前口径'));
    assert.equal(save.disabled, true);
    await act(async () => { join.click(); await delay(20); });
    await waitFor(() => statusText().includes('分析已保存；加入驾驶舱失败'));
    const listGetsAfterJoin = calls.filter(row => row.method === 'GET' && row.path === '/b0/dashboards').length;
    await act(async () => { save.click(); join.click(); await delay(20); });
    await waitFor(() => statusText().includes('分析已保存；加入驾驶舱失败'));
    const analysisPosts = calls.filter(row => row.method === 'POST' && row.path === '/b0/analyses');
    assert.equal(analysisPosts.length, 1);
    assert.equal(JSON.parse(analysisPosts[0].body).created_from_run_id, 'run_1');
    assert.equal(
      calls.filter(row => row.method === 'GET' && row.path === '/b0/dashboards').length,
      listGetsAfterJoin,
    );
    const listed = await fetchImpl('/b0/analyses');
    const payload = await listed.json();
    assert.equal(payload.items.length, 1);
    assert.equal(payload.items[0].analysis_id, analysisDoc.analysis_id);
    mounted.unmount();
    restoreDom(previous);
  }
});

test('duplicate save click while posting does not open a second request', async () => {
  const { previous } = installDom();
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  let posts = 0;
  const fetchImpl = (url, options = {}) => {
    const path = String(url);
    if (path === '/b0/assets') return jsonResponse(200, { http_api: 'CONNECTED', cockpit: true });
    if ((options.method ?? 'GET') === 'POST' && path === '/b0/analyses') {
      posts += 1;
      return pending;
    }
    throw new Error(`unexpected ${path}`);
  };
  const mounted = await mountCard(fetchImpl);
  await waitFor(() => globalThis.document.querySelector('[data-testid="analytics-query-save-button"]'));
  const save = globalThis.document.querySelector('[data-testid="analytics-query-save-button"]');
  await act(async () => { save.click(); await delay(10); });
  assert.equal(posts, 1);
  assert.equal(save.disabled, true);
  await act(async () => { save.click(); await delay(10); });
  assert.equal(posts, 1);
  release(jsonResponse(201, { analysis_id: 'analysis_1', version: 1 }));
  await act(async () => { await delay(20); });
  await waitFor(() => statusText().includes('已保存当前口径'));
  mounted.unmount();
  restoreDom(previous);
});
