import test from 'node:test';
import assert from 'node:assert/strict';
import { previewLiteralText, submitHtmlPatchPreview } from './html-edit-kernel.mjs';
import { createLivePageAdapters } from './live-adapters.mjs';
import { createIsolatedFetch, AGENT_PACKAGE } from './p12-http-fakes.mjs';
import { SAMPLE_PACKAGE } from './mock-adapters.mjs';

const TOKEN = 'library-page-isolated-test-token-32chars';
const BASE = 'http://127.0.0.1:18091';

test('literal replacement changes only the selected duplicate title', () => {
  const pkg = {
    html: '<h1 data-shine-node="n_a">相同标题</h1><h1 data-shine-node="n_b">相同标题</h1>',
    css: '',
    js: '',
    resources: [],
    node_map: [
      { node_id: 'n_a', kind: 'static_element', selector: "[data-shine-node='n_a']" },
      { node_id: 'n_b', kind: 'static_element', selector: "[data-shine-node='n_b']" },
    ],
  };
  const got = previewLiteralText({
    pkg,
    selection: { kind: 'static_element', node_id: 'n_a' },
    replacementText: '只改 A',
  });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  assert.match(got.package.html, /只改 A/);
  assert.equal((got.package.html.match(/相同标题/g) || []).length, 1);
  assert.match(got.package.html, /data-shine-node="n_b">相同标题/);
});

test('special characters are escaped rather than injected as markup', () => {
  const got = previewLiteralText({
    pkg: SAMPLE_PACKAGE,
    selection: { kind: 'static_element', node_id: 'n_title' },
    replacementText: '<script>alert(1)</script>',
  });
  assert.equal(got.ok, true, JSON.stringify(got.error));
  assert.doesNotMatch(got.package.html, /<script>alert/);
  assert.match(got.package.html, /&lt;script&gt;/);
});

test('instruction is a deprecated literal alias; aiInstruction is refused', () => {
  const literal = previewLiteralText({
    pkg: SAMPLE_PACKAGE,
    selection: { kind: 'static_element', node_id: 'n_title' },
    instruction: '把标题改得更清楚',
  });
  assert.equal(literal.ok, true, JSON.stringify(literal.error));
  assert.equal(literal.literalSource, 'instruction');
  assert.match(literal.package.html, /把标题改得更清楚/);
  const ai = previewLiteralText({
    pkg: SAMPLE_PACKAGE,
    selection: { kind: 'static_element', node_id: 'n_title' },
    aiInstruction: '把标题改得更清楚',
  });
  assert.equal(ai.ok, false);
  assert.equal(ai.error.code, 'AI_INSTRUCTION_UNSUPPORTED');
});

test('stale mapping and bound nodes are refused without widening', () => {
  const stale = previewLiteralText({
    pkg: SAMPLE_PACKAGE,
    selection: { kind: 'static_element', node_id: 'n_missing' },
    replacementText: 'x',
  });
  assert.equal(stale.ok, false);
  assert.equal(stale.error.widenToPage, false);

  const bound = previewLiteralText({
    pkg: SAMPLE_PACKAGE,
    selection: { kind: 'static_element', node_id: 'n_title' },
    replacementText: '99',
    binding_manifest: { result_refs: ['result_1'], bindings: [{ binding_id: 'b1', result_ref: 'result_1', node_id: 'n_title' }] },
  });
  assert.equal(bound.ok, false);
  assert.equal(bound.error.code, 'BINDING_PROTECTED');
});

test('patch-preview HTTP uses existing documents adapter; cancel does not save', async () => {
  const isolated = createIsolatedFetch({ token: TOKEN });
  const adapters = createLivePageAdapters({
    documentsHttp: { base: BASE, token: TOKEN, fetchImpl: isolated.fetchImpl },
    nativeGenerate: async () => AGENT_PACKAGE,
  });
  const generated = await adapters.documents.generateAndConfirm({
    title: '可编辑页',
    session_id: 'native_session_fixture',
    package: SAMPLE_PACKAGE,
    binding_manifest: { bindings: [], result_refs: [] },
    idempotency_key: 'gen_edit_1',
  });
  const literal = previewLiteralText({
    pkg: generated.page.package,
    selection: { kind: 'static_element', node_id: 'n_title' },
    replacementText: '精确标题',
    page_id: generated.page.page_id,
    session_id: generated.page.session_id,
    base_version: generated.page.version,
  });
  assert.equal(literal.ok, true, JSON.stringify(literal.error));
  const preview = await submitHtmlPatchPreview(adapters.documents, {
    page_id: generated.page.page_id,
    base_version: generated.page.version,
    package: literal.package,
  });
  assert.equal(preview.ok, true, JSON.stringify(preview.error));
  await adapters.documents.cancelPreview(preview.preview_id);
  const page = await adapters.documents.pullPage(generated.page.page_id);
  assert.equal(page.ok, true);
  assert.match(adapters.assets.get(generated.page.page_id).package.html, /示例标题/);
});
