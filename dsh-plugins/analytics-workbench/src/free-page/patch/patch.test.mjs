import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSourceIndex, locateSelection } from '../source-index/index.mjs';
import { d48Package } from '../source-index/page-fixture.mjs';
import {
  applyInnerText, applyRegionOuter, createMemoryPageStore, createPatchPreview,
} from './index.mjs';

function setup() {
  const pagePackage = d48Package();
  const index = buildSourceIndex(pagePackage);
  const clock = { t: 1_000_000, now() { return this.t; }, advance(ms) { this.t += ms; } };
  const store = createMemoryPageStore({ now: () => clock.now() });
  store.seedPage({
    page_id: 'page_fixture_unbound',
    session_id: 'native_session_fixture',
    version: 1,
    package: pagePackage,
  });
  return { pagePackage, index, clock, store };
}

function previewOpts(index, pagePackage, selection, proposed, extra = {}) {
  return {
    index,
    pagePackage,
    selection,
    proposed,
    page_id: 'page_fixture_unbound',
    session_id: 'native_session_fixture',
    base_version: 1,
    idempotency_key: extra.idempotency_key ?? 'patch_key_1',
    preview_id: extra.preview_id ?? 'preview_1',
    now_ms: extra.now_ms ?? 1_000_000,
    ttl_ms: extra.ttl_ms ?? 60_000,
    scope_confirmed: extra.scope_confirmed ?? false,
    impact_hash: extra.impact_hash ?? null,
  };
}

test('static title patch leaves canvas and js untouched', () => {
  const { pagePackage, index } = setup();
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_title' });
  const applied = applyInnerText(pagePackage, located, '精确标题');
  assert.equal(applied.ok, true);
  const created = createPatchPreview(previewOpts(index, pagePackage, located.selection, applied.package));
  assert.equal(created.ok, true);
  assert.equal(created.preview.operation, 'PATCH');
  assert.equal(created.preview.status, 'PENDING');
  assert.equal(created.impact.html_changed_nodes.join(), 'n_title');
  assert.equal(created.impact.canvas_html_unchanged, true);
  assert.equal(created.impact.js_bytes_unchanged, true);
  assert.match(applied.package.html, /精确标题/);
  assert.match(applied.package.html, /data-shine-region="r_chart"/);
  assert.equal(applied.package.js, pagePackage.js);
});

test('dynamic region patch leaves sibling static nodes unchanged', () => {
  const { pagePackage, index } = setup();
  const located = locateSelection(index, { kind: 'dynamic_region', node_id: 'r_chart' });
  const next = applyRegionOuter(pagePackage, located,
    '<canvas data-shine-region="r_chart" width="640" height="180"></canvas>');
  assert.equal(next.ok, true);
  const created = createPatchPreview(previewOpts(index, pagePackage, located.selection, next.package));
  assert.equal(created.ok, true);
  assert.equal(created.located.scope, 'declared_region');
  assert.equal(created.impact.html_changed_nodes.join(), 'r_chart');
  assert.equal(created.impact.unchanged_nodes.includes('n_title'), true);
  assert.equal(created.impact.unchanged_nodes.includes('n_lede'), true);
  assert.match(next.package.html, /示例标题/);
});

test('stale or forged selection cannot submit a whole-page proposed package', () => {
  const { pagePackage, index } = setup();
  const whole = { ...pagePackage, html: '<!doctype html><html><body><p>rewritten</p></body></html>', js: '', css: '' };
  for (const selection of [
    { kind: 'static_element', node_id: 'n_missing', mapping: 'stale' },
    { kind: 'static_element', node_id: 'n_forged', mapping: 'forged' },
  ]) {
    const created = createPatchPreview(previewOpts(index, pagePackage, selection, whole));
    assert.equal(created.ok, false, selection.node_id);
    assert.equal(created.error.code, 'MAPPING_STALE');
    assert.equal(created.widen_to_whole_page, false);
    assert.equal(created.preview, null);
    assert.equal(created.submitted, false);
  }
});

test('shared CSS impact requires matching confirmation before a pending preview exists', () => {
  const { pagePackage, index } = setup();
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_title' });
  const proposed = { ...pagePackage, css: pagePackage.css.replace('28px', '32px') };
  const blocked = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed));
  assert.equal(blocked.ok, false);
  assert.equal(blocked.error.code, 'SCOPE_REQUIRES_CONFIRMATION');
  assert.equal(blocked.impact.shared_css, true);
  assert.equal(blocked.preview, null);
  const allowed = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed, {
    scope_confirmed: true,
    impact_hash: blocked.impact_hash,
  }));
  assert.equal(allowed.ok, true);
  assert.equal(allowed.preview.status, 'PENDING');
  const mismatch = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed, {
    scope_confirmed: true,
    impact_hash: 'deadbeefdeadbeefdeadbeefdeadbeef',
  }));
  assert.equal(mismatch.ok, false);
  assert.equal(mismatch.error.code, 'SCOPE_REQUIRES_CONFIRMATION');
});

test('foreign HTML change is rejected and is not a silent whole-page patch', () => {
  const { pagePackage, index } = setup();
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_title' });
  const proposed = { ...pagePackage, html: pagePackage.html.replace('导语保持不变', '被静默改掉') };
  const created = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed));
  assert.equal(created.ok, false);
  assert.equal(created.error.code, 'INVALID_PAGE');
  assert.equal(created.require, 'user_switch_whole_page');
  assert.equal(created.widen_to_whole_page, false);
  assert.equal(created.preview, null);
});

test('untagged HTML inserted outside the selection cannot be submitted', () => {
  const { pagePackage, index } = setup();
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_title' });
  const proposed = {
    ...pagePackage,
    html: pagePackage.html.replace('</h1>', '</h1><div class="sneak">未选区插入</div>'),
  };
  const created = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed));
  assert.equal(created.ok, false);
  assert.equal(created.error.code, 'INVALID_PAGE');
  assert.equal(created.impact.html_outside_selection, true);
  assert.equal(created.preview, null);
});

test('region JS rewritten to document-wide APIs requires scope confirmation', () => {
  const { pagePackage, index } = setup();
  const located = locateSelection(index, { kind: 'dynamic_region', node_id: 'r_chart' });
  const proposed = { ...pagePackage, js: 'document.body.replaceChildren();' };
  const created = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed));
  assert.equal(created.ok, false);
  assert.equal(created.error.code, 'SCOPE_REQUIRES_CONFIRMATION');
  assert.equal(created.impact.shared_js, true);
  assert.equal(created.preview, null);
});

test('shared at-rule CSS change requires confirmation even when a unique rule is also edited', () => {
  const { pagePackage, index } = setup();
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_title' });
  const proposed = {
    ...pagePackage,
    css: `${pagePackage.css}@media (min-width: 800px){h1{letter-spacing:1px}}`,
  };
  const created = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed));
  assert.equal(created.ok, false);
  assert.equal(created.error.code, 'SCOPE_REQUIRES_CONFIRMATION');
  assert.equal(created.impact.shared_css, true);
});

test('cancel, expire, and store failure do not write a version; duplicate confirm is idempotent', () => {
  const { pagePackage, index, clock, store } = setup();
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_title' });
  const proposed = applyInnerText(pagePackage, located, '精确标题').package;

  const pending = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed, {
    preview_id: 'preview_cancel', idempotency_key: 'patch_cancel', now_ms: clock.now(),
  }));
  store.putPreview(pending.preview);
  const cancelled = store.cancelPreview('preview_cancel');
  assert.equal(cancelled.ok, true);
  assert.equal(cancelled.preview.status, 'CANCELLED');
  const afterCancel = store.confirmPatch({
    preview_id: 'preview_cancel', idempotency_key: 'patch_cancel', now_ms: clock.now(),
  });
  assert.equal(afterCancel.ok, false);
  assert.equal(afterCancel.error.code, 'PREVIEW_CANCELLED');
  assert.equal(store.getPage('page_fixture_unbound').version, 1);

  const expiring = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed, {
    preview_id: 'preview_exp', idempotency_key: 'patch_exp', now_ms: clock.now(), ttl_ms: 10,
  }));
  store.putPreview(expiring.preview);
  clock.advance(20);
  const expired = store.confirmPatch({
    preview_id: 'preview_exp', idempotency_key: 'patch_exp', now_ms: clock.now(),
  });
  assert.equal(expired.ok, false);
  assert.equal(expired.error.code, 'PREVIEW_EXPIRED');
  assert.equal(store.getPage('page_fixture_unbound').version, 1);

  const okPreview = createPatchPreview(previewOpts(index, pagePackage, located.selection, proposed, {
    preview_id: 'preview_ok', idempotency_key: 'patch_ok', now_ms: clock.now(),
  }));
  store.putPreview(okPreview.preview);
  const first = store.confirmPatch({
    preview_id: 'preview_ok', idempotency_key: 'patch_ok', now_ms: clock.now(),
  });
  assert.equal(first.ok, true);
  assert.equal(first.page.version, 2);
  const second = store.confirmPatch({
    preview_id: 'preview_ok', idempotency_key: 'patch_ok', now_ms: clock.now(),
  });
  assert.equal(second.ok, true);
  assert.equal(second.idempotent, true);
  assert.equal(second.page.version, 2);
  assert.equal(store.getPage('page_fixture_unbound').version, 2);
});
