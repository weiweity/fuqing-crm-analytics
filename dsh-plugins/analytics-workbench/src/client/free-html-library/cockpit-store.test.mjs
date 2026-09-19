import test from 'node:test';
import assert from 'node:assert/strict';
import { createLivePageAdapters } from './live-adapters.mjs';
import { createFreeHtmlLibraryStore } from './store.mjs';
import { createIsolatedFetch } from './p12-http-fakes.mjs';
import { editableTextNodes } from '../html-selection-bridge.mjs';

function fixture(t) {
  const token = 'isolated-cockpit-page-token-32chars';
  const http = createIsolatedFetch({ token }), control = { lose: false, cancel: false }, calls = [];
  const adapters = createLivePageAdapters({ documentsHttp: { base: 'http://127.0.0.1:18999', token, fetchImpl: async (url, options) => {
    calls.push({ url, options });
    if (control.cancel && url.endsWith('/cancel')) throw new Error('cancel unavailable');
    const result = await http.fetchImpl(url, options);
    if (control.lose && url.endsWith('/confirm')) { control.lose = false; throw new Error('receipt lost'); }
    return result;
  } } });
  const store = createFreeHtmlLibraryStore({ adapters });
  t.after(() => store.dispose());
  return { store, control, calls, adapters };
}
const input = { html: '<h1 data-shine-node="title">标题</h1><p data-shine-node="body">正文</p>', path: 'report.html', sessionId: 'source_session' };
async function imported(store) {
  await store.previewImport(input);
  assert.equal(store.getSnapshot().current, null);
  assert.equal(store.hasUnsavedChanges(), true);
  await store.confirmImport();
  assert.equal(store.getSnapshot().current.version, 1);
  store.enterEdit(); store.selectLocatable(editableTextNodes(store.getSnapshot().current.package)[0]);
}
test('import requires explicit confirmation; failed cancel retains the actual candidate', async t => {
  const { store, control, calls } = fixture(t);
  await store.previewImport(input);
  const candidate = store.getSnapshot().importCandidate;
  assert.ok(candidate); assert.equal(calls.filter(row => row.url.endsWith('/confirm')).length, 0);
  control.cancel = true; await store.cancelPreview();
  assert.equal(store.getSnapshot().importCandidate, candidate);
  assert.equal(store.hasUnsavedChanges(), true);
  control.cancel = false; await store.cancelPreview(); assert.equal(store.hasUnsavedChanges(), false);
});
test('unknown import receipt preserves candidate and uses one key on retry', async t => {
  const { store, control, calls } = fixture(t);
  await store.previewImport(input); control.lose = true;
  await store.confirmImport(); assert.equal(store.getSnapshot().confirmationUncertain, true);
  await store.cancelPreview(); assert.ok(store.getSnapshot().importCandidate);
  await store.inspectConfirmation();
  assert.equal(store.getSnapshot().current.version, 1);
  assert.equal(store.getSnapshot().confirmationUncertain, false);
  const keys = calls.filter(row => row.url.endsWith('/confirm')).map(row => row.options.headers['Idempotency-Key']);
  assert.equal(keys.length, 2); assert.equal(new Set(keys).size, 1);
});
test('typed text is dirty before preview; selection/close cannot lose it; leave save commits once', async t => {
  const { store } = fixture(t); await imported(store);
  store.setReplacementText('新标题', '标题'); assert.equal(store.hasUnsavedChanges(), true);
  store.clearSelection(); assert.ok(store.getSnapshot().selection);
  store.selectLocatable(editableTextNodes(store.getSnapshot().current.package)[1]);
  assert.equal(store.getSnapshot().selection.node_id, 'title');
  const result = await store.persistForLeave();
  assert.equal(result.ok, true); assert.equal(store.getSnapshot().current.version, 2);
  assert.match(store.getSnapshot().current.package.html, /新标题/);
});
test('lost PATCH confirmation locks selection and another PATCH until same-key retry settles', async t => {
  const { store, control, calls } = fixture(t); await imported(store);
  store.setReplacementText('新标题', '标题'); await store.previewPatch('新标题');
  control.lose = true; await store.confirmPatch();
  const draft = store.getSnapshot().preview, count = calls.length;
  await store.previewPatch('another'); store.selectLocatable({ node_id: 'body' }); await store.cancelPreview();
  assert.equal(calls.length, count); assert.equal(store.getSnapshot().preview, draft);
  assert.equal(store.getSnapshot().confirmationUncertain, true);
  await store.inspectConfirmation();
  assert.equal(store.getSnapshot().current.version, 2);
  assert.equal(store.hasUnsavedChanges(), false);
});

for (const operation of ['save', 'rollback']) test(`legacy ${operation} also retains a lost receipt for same-key recovery`, async t => {
  const { store, control, calls } = fixture(t); await imported(store);
  store.setReplacementText('新标题', '标题'); await store.previewPatch('新标题'); await store.confirmPatch();
  if (operation === 'save') store.markLocalDraft({ ...store.getSnapshot().current.package, css: 'h1{color:red}' });
  control.lose = true;
  if (operation === 'save') await store.saveDraft(); else await store.rollback(1);
  assert.equal(store.getSnapshot().confirmationUncertain, true);
  const preview = store.getSnapshot().preview, count = calls.length;
  await store.saveDraft(); await store.rollback(1);
  assert.equal(calls.length, count); assert.equal(store.getSnapshot().preview, preview);
  await store.inspectConfirmation();
  assert.equal(store.getSnapshot().current.version, 3);
  assert.equal(store.hasUnsavedChanges(), false);
  const confirmations = calls.filter(row => row.url.endsWith('/confirm')).slice(-2);
  assert.equal(confirmations[0].options.headers['Idempotency-Key'], confirmations[1].options.headers['Idempotency-Key']);
});
