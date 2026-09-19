import test from 'node:test';
import assert from 'node:assert/strict';
import { createLivePageAdapters } from './live-adapters.mjs';
import { createHostPageStore } from './create-host-page-store.mjs';
import { createFreeHtmlLibraryStore } from './store.mjs';
import { SAMPLE_PACKAGE } from './mock-adapters.mjs';
import { FREE_PAGE_SANDBOX } from '../../free-page/runtime/isolation-policy.mjs';
import { hasUnsavedChanges, hasActiveEditContext } from '../leave/dirty-predicate.mjs';
import { AGENT_PACKAGE, createIsolatedFetch } from './p12-http-fakes.mjs';
import { createNativePageGenerate, extractPagePackage } from './native-generate.mjs';
import { PAGE_RESULT_PREFIX } from './page-http.mjs';

const TOKEN = 'library-page-isolated-test-token-32chars';
const BASE = 'http://127.0.0.1:18091';

function liveStore(extra = {}) {
  const isolated = createIsolatedFetch({ token: TOKEN });
  const adapters = createLivePageAdapters({
    nativeGenerate: async () => AGENT_PACKAGE,
    documentsHttp: { base: BASE, token: TOKEN, fetchImpl: isolated.fetchImpl },
    resultHttp: { base: BASE, token: TOKEN, fetchImpl: isolated.fetchImpl },
    ...extra,
  });
  return { isolated, adapters, store: createFreeHtmlLibraryStore({ adapters, viewportWidth: 1440 }) };
}

test('P12 live adapters: unbound generate, sandbox srcdoc, D locate, C forbids SQL', async () => {
  const adapters = createLivePageAdapters();
  assert.equal(adapters.preview.sandbox, 'allow-scripts');
  assert.equal(FREE_PAGE_SANDBOX.includes('allow-same-origin'), false);
  const srcdoc = adapters.preview.srcdoc(SAMPLE_PACKAGE);
  assert.match(srcdoc, /data-shine-node="n_title"/);
  assert.match(srcdoc, /Content-Security-Policy/);
  assert.equal(adapters.preview.pointerEvents('browse'), 'auto');
  assert.equal(adapters.preview.pointerEvents('edit'), 'none');

  const located = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'static_element', node_id: 'n_title' });
  assert.equal(located.ok, true);
  const stale = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'static_element', node_id: 'n_missing' });
  assert.equal(stale.ok, false);
  assert.equal(stale.widenToPage, false);

  const patched = adapters.edit.previewPatch({
    pkg: SAMPLE_PACKAGE, selection: located, replacementText: '局部标题',
  });
  assert.equal(patched.status, 'PENDING');
  assert.match(patched.snapshot.html, /局部标题/);
  assert.doesNotMatch(patched.snapshot.html, /示例标题/);

  await assert.rejects(
    () => adapters.bridge.readResult({ op: 'sql' }),
    error => error.code === 'BRIDGE_UNKNOWN_OP',
  );
});

test('live adapters pull page list over isolated HTTP mock, never port 6677', async () => {
  const calls = [];
  const adapters = createLivePageAdapters({
    documentsHttp: {
      base: 'http://127.0.0.1:18091',
      token: 'library-page-isolated-test-token-32chars',
      fetchImpl: async (url, init) => {
        calls.push({ url, auth: init.headers.Authorization });
        return {
          ok: true,
          json: async () => ({ items: [{ page_id: 'page_http', title: 'HTTP 页', version: 2, binding_state: 'UNBOUND_SAMPLE' }] }),
        };
      },
    },
  });
  const pulled = await adapters.documents.pullList();
  assert.equal(pulled.ok, true);
  assert.equal(pulled.count, 1);
  assert.equal(adapters.assets.get('page_http').title, 'HTTP 页');
  assert.match(calls[0].url, /18091\/api\/v1\/analytics\/page-documents\/pages/);
  assert.doesNotMatch(calls[0].url, /:6677/);
});

test('live adapters pull one page snapshot over isolated HTTP', async () => {
  const adapters = createLivePageAdapters({
    documentsHttp: {
      base: 'http://127.0.0.1:18091',
      token: 'library-page-isolated-test-token-32chars',
      fetchImpl: async (url) => {
        assert.match(url, /\/pages\/page_http$/);
        return {
          ok: true,
          json: async () => ({ page_id: 'page_http', title: '单页', version: 3, binding_state: 'BOUND_VERIFIED' }),
        };
      },
    },
  });
  const pulled = await adapters.documents.pullPage('page_http');
  assert.equal(pulled.ok, true);
  assert.equal(adapters.assets.get('page_http').binding_state, 'BOUND_VERIFIED');
  assert.equal(adapters.assets.get('page_http').version, 3);
});

test('live adapters refuse a 6677 documents base and skip fetch when HTTP is unset', async () => {
  const unset = createLivePageAdapters();
  const skipped = await unset.documents.pullList();
  assert.equal(skipped.ok, false);
  assert.equal(skipped.reason, 'http_not_configured');
  const live = createLivePageAdapters({
    documentsHttp: { base: 'http://127.0.0.1:6677', fetchImpl: async () => ({ ok: true, json: async () => ({ items: [] }) }) },
  });
  await assert.rejects(() => live.documents.pullList(), error => error.code === 'REFUSED_LIVE_PORT');
});

test('P12 host page store uses live adapters, not E mocks', async () => {
  const store = createHostPageStore();
  assert.equal(store.getSnapshot().adapterKind, 'p12-live');
  assert.equal(createLivePageAdapters().preview.sandbox.includes('allow-same-origin'), false);
});

test('P12 store with live adapters: dirty predicate is not clean selection', async () => {
  const { store } = liveStore();
  store.applyExample('未绑定经营复盘');
  await store.generate();
  assert.equal(store.getSnapshot().current.binding_state, 'UNBOUND_SAMPLE');
  store.enterEdit();
  store.selectLocatable({ kind: 'static_element', node_id: 'n_title' });
  assert.equal(store.hasActiveEditContext(), true);
  assert.equal(store.hasUnsavedChanges(), false);
  assert.equal(hasActiveEditContext({ editContext: { status: 'OPEN' }, preview: null, confirmationUncertain: false, layoutDraft: null, saved: { spec: { blocks: [] } } }), true);
  assert.equal(hasUnsavedChanges({ editContext: { status: 'OPEN' }, preview: null, confirmationUncertain: false, layoutDraft: null, saved: { spec: { blocks: [] } } }), false);
});

test('live generate uses native Agent package and never SAMPLE_PACKAGE', async () => {
  const { store } = liveStore();
  store.setPrompt('经营杂志复盘');
  await store.generate();
  const html = store.getSnapshot().current.package.html;
  assert.match(html, /原生Agent标题/);
  assert.doesNotMatch(html, /示例标题/);
  assert.equal(store.getSnapshot().current.package.js, AGENT_PACKAGE.js);
  assert.equal(store.getSnapshot().current.version, 1);
});

test('live generate without nativeGenerate keeps the prompt', async () => {
  const store = createFreeHtmlLibraryStore({ adapters: createLivePageAdapters(), viewportWidth: 1440 });
  store.setPrompt('保留我');
  await store.generate();
  assert.equal(store.getSnapshot().prompt, '保留我');
  assert.equal(store.getSnapshot().current, null);
  assert.match(store.getSnapshot().message, /原生 Agent 未返回页面源码包/);
});

test('live D6 patch, D9 save, reopen and rollback go through isolated documents HTTP', async () => {
  const { store, adapters } = liveStore();
  store.setPrompt('经营杂志复盘');
  await store.generate();
  const pageId = store.getSnapshot().current.page_id;
  const v1 = store.getSnapshot().current.version;
  store.enterEdit();
  store.selectLocatable({ kind: 'static_element', node_id: 'n_title' });
  await store.previewPatch('局部新标题');
  assert.equal(store.getSnapshot().preview.status, 'PENDING');
  await store.confirmPatch();
  assert.equal(store.getSnapshot().current.version, v1 + 1);
  assert.match(store.getSnapshot().current.package.html, /局部新标题/);
  store.markLocalDraft({ ...store.getSnapshot().current.package, js: 'window.__d9=true' });
  await store.saveDraft();
  assert.equal(store.getSnapshot().current.version, v1 + 2);
  assert.equal(store.getSnapshot().current.package.js, 'window.__d9=true');
  await store.rollback(v1);
  assert.ok(store.getSnapshot().current.version > v1 + 2 || store.getSnapshot().current.version === v1 + 3);
  assert.match(store.getSnapshot().current.package.html, /原生Agent标题/);
  const pulled = await adapters.documents.pullPage(pageId);
  assert.equal(pulled.ok, true);
  const history = await adapters.documents.pullHistory(pageId);
  assert.equal(history.ok, true);
  assert.ok(history.items.length >= 3);
});

test('live result bridge reads isolated HTTP and refuses 6677', async () => {
  const { adapters } = liveStore();
  const read = await adapters.bridge.readResult({
    op: 'data.read',
    result_ref: 'result_fixture_1',
    mode: 'summary',
    manifest: { result_refs: ['result_fixture_1'], bindings: [] },
  });
  assert.equal(read.ok, true);
  assert.equal(read.result_ref, 'result_fixture_1');
  const unset = createLivePageAdapters({ nativeGenerate: async () => AGENT_PACKAGE });
  await assert.rejects(
    () => unset.bridge.readResult({ op: 'data.read', result_ref: 'result_fixture_1' }),
    error => error.code === 'RESULT_HTTP_NOT_CONFIGURED',
  );
  const live = createLivePageAdapters({
    resultHttp: { base: 'http://127.0.0.1:6677', fetchImpl: async () => ({ ok: true, json: async () => ({}) }) },
  });
  await assert.rejects(
    () => live.bridge.readResult({ op: 'data.read', result_ref: 'result_fixture_1' }),
    error => error.code === 'REFUSED_LIVE_PORT',
  );
  assert.equal(PAGE_RESULT_PREFIX, '/api/v1/analytics/page-result-access');
});

test('native generate extracts a page package and rejects empty Agent replies', async () => {
  const extracted = extractPagePackage({ html: '<html>x</html>', css: 'a{}', js: '' });
  assert.equal(extracted.html, '<html>x</html>');
  const fromFence = extractPagePackage('note {"html":"<html>from-json</html>","css":"","js":""}');
  assert.equal(fromFence.html, '<html>from-json</html>');
  const generate = createNativePageGenerate({
    submitPrompt: async () => ({ ok: true, value: { accepted: true } }),
  });
  await assert.rejects(() => generate('做一页'), error => error.code === 'NATIVE_GENERATE_UNAVAILABLE');
});
