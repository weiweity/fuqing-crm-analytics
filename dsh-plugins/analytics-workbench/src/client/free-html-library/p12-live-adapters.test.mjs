import test from 'node:test';
import assert from 'node:assert/strict';
import { createLivePageAdapters } from './live-adapters.mjs';
import { createFreeHtmlLibraryStore } from './store.mjs';
import { SAMPLE_PACKAGE } from './mock-adapters.mjs';
import { FREE_PAGE_SANDBOX } from '../../free-page/runtime/isolation-policy.mjs';
import { hasUnsavedChanges, hasActiveEditContext } from '../leave/dirty-predicate.mjs';

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
    pkg: SAMPLE_PACKAGE, selection: located, instruction: '局部标题',
  });
  assert.equal(patched.status, 'PENDING');
  assert.match(patched.snapshot.html, /局部标题/);
  assert.doesNotMatch(patched.snapshot.html, /示例标题/);

  await assert.rejects(
    () => adapters.bridge.readResult({ op: 'sql' }),
    error => error.code === 'BRIDGE_UNKNOWN_OP',
  );
});

test('P12 store with live adapters: dirty predicate is not clean selection', async () => {
  const adapters = createLivePageAdapters();
  const store = createFreeHtmlLibraryStore({ adapters, viewportWidth: 1440 });
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
