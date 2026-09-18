import test from 'node:test';
import assert from 'node:assert/strict';
import { applyTextToShineNode, createMockPageAdapters, SAMPLE_PACKAGE } from './mock-adapters.mjs';

test('D48 locate: exact, region, stale/forged never widen, whole page only if user switched', () => {
  const adapters = createMockPageAdapters();
  const exact = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'static_element', node_id: 'n_title', mapping: 'valid' });
  assert.equal(exact.ok, true);
  assert.equal(exact.scope, 'exact_source_range');
  const region = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'dynamic_region', node_id: 'r_chart', mapping: 'valid' });
  assert.equal(region.scope, 'declared_region');
  const stale = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'static_element', node_id: 'n_missing', mapping: 'stale' });
  assert.equal(stale.ok, false);
  assert.equal(stale.widenToPage, false);
  assert.equal(stale.error.code, 'MAPPING_STALE');
  const forged = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'static_element', node_id: 'n_forged', mapping: 'forged' });
  assert.equal(forged.widenToPage, false);
  const silent = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'whole_page', user_switched: false });
  assert.equal(silent.ok, false);
  const whole = adapters.edit.locate(SAMPLE_PACKAGE, { kind: 'whole_page', user_switched: true });
  assert.equal(whole.scope, 'whole_package');
});

test('shared CSS preview requires confirmation; cancel does not apply', () => {
  const adapters = createMockPageAdapters();
  const selection = adapters.edit.locate(SAMPLE_PACKAGE, { node_id: 'n_title' });
  assert.throws(() => adapters.edit.previewPatch({ pkg: SAMPLE_PACKAGE, selection, instruction: 'x', affectsShared: true }), /SCOPE_REQUIRES_CONFIRMATION|共享/);
  try {
    adapters.edit.previewPatch({ pkg: SAMPLE_PACKAGE, selection, instruction: 'x', affectsShared: true });
  } catch (error) {
    assert.equal(error.code, 'SCOPE_REQUIRES_CONFIRMATION');
    const cancelled = adapters.edit.cancelPatch(error.preview.preview_id);
    assert.equal(cancelled.status, 'CANCELLED');
    assert.throws(() => adapters.edit.confirmPatch(error.preview.preview_id), /PREVIEW_CANCELLED/);
  }
  const preview = adapters.edit.previewPatch({ pkg: SAMPLE_PACKAGE, selection, instruction: '改标题' });
  const applied = adapters.edit.confirmPatch(preview.preview_id, { idempotency_key: preview.idempotency_key });
  assert.equal(applied.status, 'APPLIED');
  assert.match(applied.snapshot.html, /改标题/);
  const renamed = { ...SAMPLE_PACKAGE, html: applyTextToShineNode(SAMPLE_PACKAGE.html, 'n_title', '标题页') };
  const afterGenerate = adapters.edit.previewPatch({ pkg: renamed, selection, instruction: '新标题' });
  assert.match(afterGenerate.snapshot.html, /新标题/);
  assert.doesNotMatch(afterGenerate.snapshot.html, />标题页</);
});

test('C mock forbids SQL/token/save and keeps sample binding readable', async () => {
  const adapters = createMockPageAdapters();
  const binding = await adapters.bridge.readBinding({ binding_state: 'UNBOUND_SAMPLE', binding_manifest: { bindings: [], result_refs: [] } });
  assert.equal(binding.binding_state, 'UNBOUND_SAMPLE');
  await assert.rejects(() => adapters.bridge.readResult({ op: 'sql' }), /forbidden|FORBIDDEN/);
  const preview = adapters.preview.pointerEvents('browse');
  assert.equal(preview, 'auto');
  assert.equal(adapters.preview.pointerEvents('edit'), 'none');
});
