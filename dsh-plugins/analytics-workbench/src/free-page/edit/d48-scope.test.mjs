import test from 'node:test';
import assert from 'node:assert/strict';
import { D48_CASES, d48Package } from '../source-index/page-fixture.mjs';
import { applyInnerText, applyRegionOuter, createMemoryPageStore } from '../patch/index.mjs';
import { createEditController, makeIds } from './index.mjs';

function spec(id) {
  const row = D48_CASES.cases.find(item => item.id === id);
  assert.ok(row, id);
  return row;
}

function session() {
  const clock = { t: 1_000_000, now() { return this.t; }, advance(ms) { this.t += ms; } };
  const store = createMemoryPageStore({ now: () => clock.now() });
  const page = store.seedPage({
    page_id: 'page_fixture_unbound',
    session_id: 'native_session_fixture',
    version: 1,
    package: d48Package(),
  });
  const controller = createEditController({
    store, now: () => clock.now(), ttl_ms: 1_000, ids: makeIds(),
  });
  controller.open(page);
  controller.enterEdit();
  return { clock, store, controller };
}

test('D48 static-precise: PATCH html title text only; canvas/js unchanged', async () => {
  const expected = spec('static-precise');
  assert.equal(expected.allowed_scope, 'exact_source_range');
  assert.equal(expected.submit_without_confirm, false);
  const { controller, store } = session();
  const selected = controller.select(expected.selection);
  assert.equal(selected.ok, true);
  assert.equal(selected.located.scope, 'exact_source_range');
  const proposed = applyInnerText(controller.snapshot().draft, selected.located, '精确标题').package;
  const preview = controller.previewPatch(proposed);
  assert.equal(preview.ok, true);
  assert.equal(preview.impact.html_changed_nodes.join(), 'n_title');
  assert.equal(preview.impact.canvas_html_unchanged, true);
  assert.equal(preview.impact.js_bytes_unchanged, true);
  const confirmed = await controller.confirmPatch();
  assert.equal(confirmed.ok, true);
  assert.equal(confirmed.page.version, 2);
  const saved = store.getPage('page_fixture_unbound').package;
  assert.match(saved.html, /精确标题/);
  assert.match(saved.html, /data-shine-region="r_chart"/);
  assert.equal(saved.js, d48Package().js);
});

test('D48 dynamic-region: PATCH region as a whole; sibling static nodes unchanged', async () => {
  const expected = spec('dynamic-region');
  const { controller } = session();
  const selected = controller.select(expected.selection);
  assert.equal(selected.located.scope, 'declared_region');
  const proposed = applyRegionOuter(controller.snapshot().draft, selected.located,
    '<canvas data-shine-region="r_chart" width="640" height="180"></canvas>').package;
  const preview = controller.previewPatch(proposed);
  assert.equal(preview.ok, true);
  assert.equal(preview.impact.unchanged_nodes.includes('n_title'), true);
  const confirmed = await controller.confirmPatch();
  assert.equal(confirmed.page.package.html.includes('width="640"'), true);
  assert.equal(confirmed.page.package.html.includes('示例标题'), true);
});

test('D48 mapping-stale: keep draft; require reselect; do not widen to whole page', async () => {
  const expected = spec('mapping-stale');
  const { controller, store } = session();
  const selected = controller.select(expected.selection);
  assert.equal(selected.ok, false);
  assert.equal(selected.error.code, expected.error);
  assert.equal(selected.require, 'reselect');
  assert.equal(selected.widen_to_whole_page, false);
  const preview = controller.previewPatch({ ...d48Package(), html: '<html><body>整页救场</body></html>' });
  assert.equal(preview.ok, false);
  assert.equal(preview.error.code, 'MAPPING_STALE');
  assert.equal(preview.submitted, false);
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  assert.equal(controller.snapshot().draft.html.includes('示例标题'), true);
});

test('D48 forged-marker: same as stale; markers are not credentials', () => {
  const expected = spec('forged-marker');
  const { controller } = session();
  const selected = controller.select(expected.selection);
  assert.equal(selected.ok, false);
  assert.equal(selected.error.code, expected.error);
  assert.equal(selected.widen_to_whole_page, false);
  assert.equal(controller.snapshot().index.nodes.n_forged, undefined);
});

test('D48 user-whole-page: only when user_switched is true', async () => {
  const expected = spec('user-whole-page');
  const { controller, store } = session();
  const denied = controller.select({ kind: 'whole_page', user_switched: false });
  assert.equal(denied.ok, false);
  assert.equal(denied.widen_to_whole_page, false);
  const switched = controller.switchWholePage();
  assert.equal(switched.ok, true);
  assert.equal(switched.located.scope, expected.allowed_scope);
  const proposed = {
    html: '<!doctype html><html><body><h1 data-shine-node="n_title">整页标题</h1></body></html>',
    css: '',
    js: '',
    resources: [],
    node_map: [{ node_id: 'n_title', kind: 'static_element', selector: "[data-shine-node='n_title']" }],
  };
  const preview = controller.previewPatch(proposed);
  assert.equal(preview.ok, true);
  const confirmed = await controller.confirmPatch();
  assert.equal(confirmed.ok, true);
  assert.equal(store.getPage('page_fixture_unbound').package.html.includes('整页标题'), true);
});

test('D48 shared-css-expansion: show actual shared CSS impact; wait for matching confirm', async () => {
  const expected = spec('shared-css-expansion');
  const { controller, store } = session();
  const selected = controller.select({ kind: 'static_element', node_id: 'n_title', mapping: 'valid' });
  assert.equal(selected.ok, true);
  const proposed = { ...controller.snapshot().draft, css: d48Package().css.replace('28px', '42px') };
  const blocked = controller.previewPatch(proposed);
  assert.equal(blocked.ok, false);
  assert.equal(blocked.error.code, expected.error_if_unconfirmed);
  assert.equal(blocked.impact.shared_css, true);
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  const allowed = controller.previewPatch(proposed, {
    scope_confirmed: true,
    impact_hash: blocked.impact_hash,
  });
  assert.equal(allowed.ok, true);
  const confirmed = await controller.confirmPatch();
  assert.equal(confirmed.ok, true);
  assert.match(store.getPage('page_fixture_unbound').package.css, /42px/);
});

test('D48 cancel-expired-fail: no new server version; retain current source', async () => {
  const expected = spec('cancel-expired-fail');
  assert.deepEqual(expected.outcomes, ['cancel', 'expired', 'failed']);
  const { controller, store, clock } = session();
  const selected = controller.select(expected.selection);
  const proposed = applyInnerText(controller.snapshot().draft, selected.located, '不会落盘').package;
  assert.equal(controller.previewPatch(proposed).ok, true);
  const cancelled = controller.cancelPreview();
  assert.equal(cancelled.saved, false);
  assert.equal(store.getPage('page_fixture_unbound').version, 1);

  assert.equal(controller.previewPatch(proposed).ok, true);
  clock.advance(5_000);
  const expired = await controller.confirmPatch();
  assert.equal(expired.error.code, 'PREVIEW_EXPIRED');
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  const failed = controller.previewPatch({ ...proposed, html: '' });
  assert.equal(failed.ok, false);
  assert.equal(failed.error.code, 'INVALID_PAGE');
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  const sneak = controller.previewPatch({
    ...controller.snapshot().draft,
    html: controller.snapshot().draft.html.replace('</h1>', '</h1><div>sneak</div>'),
  });
  assert.equal(sneak.ok, false);
  assert.equal(sneak.error.code, 'INVALID_PAGE');
  assert.equal(store.getPage('page_fixture_unbound').version, 1);
  assert.equal(controller.snapshot().draft.html.includes('示例标题'), true);
});
