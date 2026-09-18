import test from 'node:test';
import assert from 'node:assert/strict';
import { d48Package } from '../source-index/page-fixture.mjs';
import { applyInnerText, createMemoryPageStore } from '../patch/index.mjs';
import { createEditController, hasActiveEditContext, isDirty, makeIds } from './index.mjs';
import { createFreePageEditAdapter } from './adapter.mjs';

function boot(ttl_ms = 60_000) {
  const clock = { t: 1_000_000, now() { return this.t; }, advance(ms) { this.t += ms; } };
  const store = createMemoryPageStore({ now: () => clock.now() });
  const page = store.seedPage({
    page_id: 'page_fixture_unbound',
    session_id: 'native_session_fixture',
    version: 1,
    package: d48Package(),
  });
  const controller = createEditController({
    store, now: () => clock.now(), ttl_ms, ids: makeIds(),
  });
  controller.open(page);
  return { clock, store, controller, page };
}

test('clean selection is an edit context and is not dirty', () => {
  const { controller } = boot();
  controller.enterEdit();
  const selected = controller.select({ kind: 'static_element', node_id: 'n_title' });
  assert.equal(selected.ok, true);
  const state = controller.snapshot();
  assert.equal(hasActiveEditContext(state), true);
  assert.equal(isDirty(state), false);
  assert.equal(state.saved.version, 1);
});

test('native agent context uses the current selection and does not open a second runtime', () => {
  const { controller } = boot();
  controller.enterEdit();
  controller.select({ kind: 'static_element', node_id: 'n_title' });
  const ctx = controller.agentContext();
  assert.equal(ctx.ok, true);
  assert.equal(ctx.context.runtime, 'native-dsh');
  assert.equal(ctx.context.schema_version, 'free-page-edit-context/v1');
  assert.equal(ctx.context.scope, 'exact_source_range');
  assert.match(ctx.context.source_excerpt, /示例标题/);
  assert.match(ctx.context.constraint, /whole_package/);
});

test('D6 confirm writes one PATCH version; repeat confirm does not mint another', async () => {
  const { controller, store } = boot();
  controller.enterEdit();
  const selected = controller.select({ kind: 'static_element', node_id: 'n_title' });
  const proposed = applyInnerText(controller.snapshot().draft, selected.located, '精确标题').package;
  const preview = controller.previewPatch(proposed);
  assert.equal(preview.ok, true);
  assert.equal(preview.preview.operation, 'PATCH');
  const first = await controller.confirmPatch();
  assert.equal(first.ok, true);
  assert.equal(first.page.version, 2);
  assert.equal(first.operation, 'PATCH');
  const again = await controller.confirmPatch();
  assert.equal(again.ok, false);
  assert.equal(store.getPage('page_fixture_unbound').version, 2);
});

test('D9 explicit save writes one SAVE version; exit/close/clear/cancel do not', async () => {
  const { controller, store } = boot();
  controller.enterEdit();
  controller.select({ kind: 'static_element', node_id: 'n_title' });
  controller.mutateSelectedText('本地草稿标题');
  assert.equal(controller.isDirty(), true);
  assert.equal(store.getPage('page_fixture_unbound').version, 1);

  controller.closePanel();
  controller.clearSelection();
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  assert.equal(controller.isDirty(), true);

  controller.enterEdit();
  controller.select({ kind: 'static_element', node_id: 'n_title' });
  const preview = controller.previewPatch(controller.snapshot().draft);
  assert.equal(preview.ok, true);
  const cancelled = controller.cancelPreview();
  assert.equal(cancelled.saved, false);
  assert.equal(store.getPage('page_fixture_unbound').version, 1);

  controller.exitEdit();
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  assert.equal(controller.snapshot().mode, 'browse');
  assert.equal(controller.isDirty(), true);

  const saved = await controller.saveDraft();
  assert.equal(saved.ok, true);
  assert.equal(saved.operation, 'SAVE');
  assert.equal(saved.page.version, 2);
  assert.equal(store.getPage('page_fixture_unbound').package.html.includes('本地草稿标题'), true);
  const second = await controller.saveDraft();
  assert.equal(second.noop, true);
  assert.equal(store.getPage('page_fixture_unbound').version, 2);
});

test('expired preview and thrown confirm keep the current source', async () => {
  const clock = { t: 1_000_000, now() { return this.t; }, advance(ms) { this.t += ms; } };
  const store = createMemoryPageStore({ now: () => clock.now() });
  const page = store.seedPage({
    page_id: 'page_fixture_unbound', session_id: 'native_session_fixture', version: 1, package: d48Package(),
  });
  const controller = createEditController({ store, now: () => clock.now(), ttl_ms: 10, ids: makeIds() });
  controller.open(page);
  controller.enterEdit();
  const selected = controller.select({ kind: 'static_element', node_id: 'n_title' });
  const proposed = applyInnerText(controller.snapshot().draft, selected.located, '精确标题').package;
  assert.equal(controller.previewPatch(proposed).ok, true);
  clock.advance(50);
  const expired = await controller.confirmPatch();
  assert.equal(expired.ok, false);
  assert.equal(expired.error.code, 'PREVIEW_EXPIRED');
  assert.equal(store.getPage('page_fixture_unbound').version, 1);

  const throwing = createMemoryPageStore();
  throwing.seedPage(page);
  throwing.confirmPatch = async () => { throw new Error('network'); };
  const uncertain = createEditController({ store: throwing, ids: makeIds() });
  uncertain.open(page);
  uncertain.enterEdit();
  const located = uncertain.select({ kind: 'static_element', node_id: 'n_title' });
  const next = applyInnerText(uncertain.snapshot().draft, located.located, '精确标题').package;
  uncertain.previewPatch(next);
  const lost = await uncertain.confirmPatch();
  assert.equal(lost.error.code, 'RECEIPT_UNCERTAIN');
  assert.equal(throwing.getPage('page_fixture_unbound').version, 1);
  assert.equal(uncertain.snapshot().confirmation_uncertain, true);
  assert.equal(uncertain.snapshot().preview.idempotency_key, lost.state.last_idempotency_key
    || uncertain.snapshot().last_idempotency_key);
});

test('consecutive local text edits rebind source ranges after each draft', () => {
  const { controller } = boot();
  controller.enterEdit();
  controller.select({ kind: 'static_element', node_id: 'n_title' });
  const first = controller.mutateSelectedText('本地草稿标题');
  assert.equal(first.ok, true);
  const second = controller.mutateSelectedText('第二次');
  assert.equal(second.ok, true);
  const html = controller.snapshot().draft.html;
  assert.match(html, />第二次</);
  assert.doesNotMatch(html, /第二次标题/);
  assert.match(html, /导语保持不变/);
});

test('D9 lost receipt retries the original save idempotency key', async () => {
  const store = createMemoryPageStore();
  const page = store.seedPage({
    page_id: 'page_fixture_unbound', session_id: 'native_session_fixture', version: 1, package: d48Package(),
  });
  const orig = store.saveDraft.bind(store);
  const keys = [];
  store.saveDraft = async (args) => {
    const result = orig(args);
    keys.push(args.idempotency_key);
    if (keys.length === 1) throw new Error('lost receipt after apply');
    return result;
  };
  const controller = createEditController({ store, ids: makeIds() });
  controller.open(page);
  controller.enterEdit();
  controller.select({ kind: 'static_element', node_id: 'n_title' });
  controller.mutateSelectedText('草稿');
  const lost = await controller.saveDraft();
  assert.equal(lost.error.code, 'RECEIPT_UNCERTAIN');
  const retry = await controller.saveDraft();
  assert.equal(retry.ok, true);
  assert.equal(retry.idempotent, true);
  assert.equal(retry.page.version, 2);
  assert.deepEqual(keys, ['save_key_1', 'save_key_1']);
  assert.equal(store.getPage('page_fixture_unbound').version, 2);
});

test('adapter exposes D6/D9 without treating exit as save', async () => {
  const store = createMemoryPageStore();
  const page = store.seedPage({
    page_id: 'page_fixture_unbound', session_id: 'native_session_fixture', version: 1, package: d48Package(),
  });
  const adapter = createFreePageEditAdapter({ store, ids: makeIds() });
  adapter.open(page);
  adapter.enterEdit();
  adapter.select({ kind: 'static_element', node_id: 'n_title' });
  adapter.mutateSelectedText('适配器草稿');
  adapter.exitEdit();
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  const saved = await adapter.saveDraft();
  assert.equal(saved.page.version, 2);
});
