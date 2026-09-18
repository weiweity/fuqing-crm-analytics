import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSourceIndex, locateSelection, rebuildSourceIndex } from './index.mjs';
import { D48_CASES, DUPLICATE_HTML, d48Package, frozenPackage } from './page-fixture.mjs';

function indexOf(pkg = d48Package()) {
  return buildSourceIndex(pkg);
}

test('consumes coordinator D48 fixture with the five required branches', () => {
  const ids = D48_CASES.cases.map(row => row.id);
  for (const id of ['static-precise', 'dynamic-region', 'mapping-stale', 'forged-marker', 'user-whole-page', 'shared-css-expansion', 'cancel-expired-fail']) {
    assert.equal(ids.includes(id), true, id);
  }
});

test('frozen-contract package maps n_title exactly and r_chart as a region', () => {
  const index = indexOf(frozenPackage());
  const title = locateSelection(index, { kind: 'static_element', node_id: 'n_title', mapping: 'valid' });
  assert.equal(title.ok, true);
  assert.equal(title.scope, 'exact_source_range');
  assert.match(title.node.html_range.inner_text, /示例标题/);
  const chart = locateSelection(index, { kind: 'dynamic_region', node_id: 'r_chart', mapping: 'valid' });
  assert.equal(chart.ok, true);
  assert.equal(chart.scope, 'declared_region');
  assert.match(chart.node.html_range.outer_text, /canvas/);
});

test('static element locate is exact and does not return whole_package', () => {
  const located = locateSelection(indexOf(), { kind: 'static_element', node_id: 'n_title' });
  assert.equal(located.ok, true);
  assert.equal(located.allowed_scope, 'exact_source_range');
  assert.equal(located.widen_to_whole_page, undefined);
  assert.equal(located.scope === 'whole_package', false);
});

test('dynamic canvas region is declared_region, not guessed DOM', () => {
  const located = locateSelection(indexOf(), { kind: 'dynamic_region', node_id: 'r_chart' });
  assert.equal(located.ok, true);
  assert.equal(located.scope, 'declared_region');
  assert.equal(located.node.kind, 'dynamic_region');
});

test('missing node is MAPPING_STALE and refuses silent whole-page widen', () => {
  const located = locateSelection(indexOf(), { kind: 'static_element', node_id: 'n_missing', mapping: 'stale' });
  assert.equal(located.ok, false);
  assert.equal(located.error.code, 'MAPPING_STALE');
  assert.equal(located.error.http, 409);
  assert.equal(located.require, 'reselect');
  assert.equal(located.keep_draft, true);
  assert.equal(located.widen_to_whole_page, false);
  assert.equal(located.allowed_scope, 'none');
});

test('forged marker is not a credential', () => {
  const index = indexOf();
  assert.equal(index.untrusted_markers.includes('n_forged'), true);
  assert.equal(index.nodes.n_forged, undefined);
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_forged', mapping: 'forged' });
  assert.equal(located.ok, false);
  assert.equal(located.error.code, 'MAPPING_STALE');
  assert.equal(located.widen_to_whole_page, false);
});

test('duplicate markers require reselect', () => {
  const index = buildSourceIndex(d48Package({
    html: DUPLICATE_HTML,
    node_map: [{ node_id: 'n_title', kind: 'static_element', selector: "[data-shine-node='n_title']" }],
  }));
  assert.equal(index.duplicates.includes('n_title'), true);
  const located = locateSelection(index, { kind: 'static_element', node_id: 'n_title' });
  assert.equal(located.ok, false);
  assert.equal(located.error.code, 'MAPPING_STALE');
  assert.equal(located.widen_to_whole_page, false);
});

test('whole_page without user_switched is rejected; switch is explicit', () => {
  const index = indexOf();
  const denied = locateSelection(index, { kind: 'whole_page', user_switched: false });
  assert.equal(denied.ok, false);
  assert.equal(denied.widen_to_whole_page, false);
  const allowed = locateSelection(index, { kind: 'whole_page', user_switched: true });
  assert.equal(allowed.ok, true);
  assert.equal(allowed.scope, 'whole_package');
});

test('static_element cannot silently locate a dynamic region', () => {
  const located = locateSelection(indexOf(), { kind: 'static_element', node_id: 'r_chart' });
  assert.equal(located.ok, false);
  assert.equal(located.error.code, 'MAPPING_STALE');
  assert.equal(located.widen_to_whole_page, false);
});

test('stale mapping_token after rebuild requires reselect', () => {
  const pkg = d48Package();
  const index = indexOf(pkg);
  const token = index.nodes.n_title.mapping_token;
  const next = { ...pkg, html: pkg.html.replace('示例标题', '新标题') };
  const rebuilt = rebuildSourceIndex(next);
  assert.notEqual(rebuilt.version_hash, index.version_hash);
  const stale = locateSelection(rebuilt, {
    kind: 'static_element', node_id: 'n_title', mapping_token: token,
  });
  assert.equal(stale.ok, false);
  assert.equal(stale.error.code, 'MAPPING_STALE');
  const fresh = locateSelection(rebuilt, { kind: 'static_element', node_id: 'n_title' });
  assert.equal(fresh.ok, true);
});
