/** Click the compiled query card; mock transport only. Not a native session. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { QUERY_TOOL_NAME } from '../src/query-model.mjs';
import { QUERY_CANCEL_COPY } from '../src/query-cancel.mjs';

const root = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(root, '../../.context/dsh-b0/upstream'));
const webReq = createRequire(join(upstream, 'apps/web/package.json'));
const React = webReq('react');
const { createRoot } = webReq('react-dom/client');
const act = typeof React.act === 'function' ? React.act : webReq('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const stores = await import(pathToFileURL(join(upstream, 'packages/client/store/lib/index.js')).href);
const source = await readFile(join(root, 'lib/client.js'), 'utf8');
const runningBlock = { callId: 'cancel-call-a', name: QUERY_TOOL_NAME, argsRaw: '{}', turn: 1, step: 1, time: 0, subCalls: [] };

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div data-session-id="session-query-synthetic-a"><div id="root"></div></div></body></html>',
    { url: 'http://127.0.0.1:4318/' });
  const previous = { window: globalThis.window, document: globalThis.document, fetch: globalThis.fetch };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  return { dom, previous };
}

function restoreDom(previous) {
  if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
  if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
  if (previous.fetch === undefined) delete globalThis.fetch; else globalThis.fetch = previous.fetch;
}

async function mountCard(fetchImpl) {
  let factory;
  const context = {
    window: Object.assign(globalThis.window, { __ModuleLoader__: { load: row => { factory = row; } } }),
    document: globalThis.document,
    fetch: fetchImpl,
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
  const render = (block) => act(() => { root.render(React.createElement(queryCard.component, { block, callId: block.callId, toolName: QUERY_TOOL_NAME })); });
  await render(runningBlock);
  return { root, render, unmount: () => act(() => root.unmount()) };
}

function card() {
  return globalThis.document.querySelector('.analytics-query-card');
}

test('compiled cancel click surfaces HTTP/RPC/network outcomes and suppresses unhandledRejection', async () => {
  const modes = [
    { id: 'http-403', status: 403, rpcOk: false, expect: QUERY_CANCEL_COPY.error },
    { id: 'http-409', status: 409, rpcOk: false, expect: QUERY_CANCEL_COPY.error },
    { id: 'http-503', status: 503, rpcOk: false, expect: QUERY_CANCEL_COPY.error },
    { id: 'rpc-error-http-200', status: 200, rpcOk: false, expect: QUERY_CANCEL_COPY.error },
    { id: 'network-error', network: true, expect: QUERY_CANCEL_COPY.error },
    { id: 'accepted', status: 200, rpcOk: true, expect: QUERY_CANCEL_COPY.accepted },
  ];
  for (const mode of modes) {
    const { previous } = installDom();
    const unhandled = [];
    const onUnhandled = (error) => { unhandled.push(String(error?.message ?? error)); };
    process.on('unhandledRejection', onUnhandled);
    let calls = 0, statusReads = 0, bodyReads = 0;
    const fetchImpl = async () => {
      calls += 1;
      if (mode.network) throw new Error('review synthetic network failure');
      return {
        get ok() { statusReads += 1; return mode.status >= 200 && mode.status < 300; },
        get status() { statusReads += 1; return mode.status; },
        json: async () => { bodyReads += 1; return { result: { ok: mode.rpcOk, error: { message: 'SECRET_DETAIL' } } }; },
      };
    };
    const mounted = await mountCard(fetchImpl);
    const button = globalThis.document.querySelector('[data-testid="analytics-query-cancel"]');
    assert.ok(button);
    await act(async () => { button.click(); await delay(20); });
    const html = card().outerHTML;
    assert.equal(calls, 1, mode.id);
    assert.ok(statusReads + bodyReads > 0 || mode.network, mode.id);
    assert.ok(html.includes(mode.expect), mode.id);
    assert.equal(html.includes('SECRET_DETAIL'), false, mode.id);
    assert.equal(html.includes('CANCELLED'), false, mode.id);
    assert.equal(card().getAttribute('data-cancel-state'), mode.id === 'accepted' ? 'accepted' : 'error', mode.id);
    assert.equal(button.disabled, mode.id === 'accepted', mode.id);
    assert.deepEqual(unhandled, []);
    if (mode.id !== 'accepted') {
      await act(async () => { button.click(); await delay(20); });
      assert.equal(calls, 2, `${mode.id} retry`);
    } else {
      await act(async () => { button.click(); await delay(20); });
      assert.equal(calls, 1, 'accepted does not resubmit');
    }
    mounted.unmount();
    process.removeListener('unhandledRejection', onUnhandled);
    restoreDom(previous);
  }
});

test('duplicate click while submitting does not open a second request', async () => {
  const { previous } = installDom();
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  let calls = 0;
  const fetchImpl = () => { calls += 1; return pending; };
  const mounted = await mountCard(fetchImpl);
  const button = globalThis.document.querySelector('[data-testid="analytics-query-cancel"]');
  await act(async () => { button.click(); button.click(); await delay(10); });
  assert.equal(calls, 1);
  assert.equal(card().getAttribute('data-cancel-state'), 'submitting');
  assert.equal(button.disabled, true);
  release({ status: 200, get ok() { return true; }, json: async () => ({ result: { ok: true, value: { accepted: true } } }) });
  await act(async () => { await delay(20); });
  assert.equal(card().getAttribute('data-cancel-state'), 'accepted');
  mounted.unmount();
  restoreDom(previous);
});

test('late cancel response does not paint a later call card', async () => {
  const { previous } = installDom();
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const fetchImpl = () => pending;
  const mounted = await mountCard(fetchImpl);
  const button = globalThis.document.querySelector('[data-testid="analytics-query-cancel"]');
  await act(async () => { button.click(); });
  await mounted.render({ ...runningBlock, callId: 'cancel-call-b' });
  assert.equal(card().getAttribute('data-cancel-state'), 'idle');
  release({ status: 200, get ok() { return true; }, json: async () => ({ result: { ok: false, error: { message: 'SECRET' } } }) });
  await act(async () => { await delay(20); });
  assert.equal(card().getAttribute('data-cancel-state'), 'idle');
  assert.equal(card().outerHTML.includes('SECRET'), false);
  assert.equal(globalThis.document.querySelector('[data-testid="analytics-query-cancel-status"]'), null);
  mounted.unmount();
  restoreDom(previous);
});
