import test from 'node:test';
import assert from 'node:assert/strict';
import { editableTextNodes, acceptSelection, selectionSrcdoc } from './html-selection-bridge.mjs';
import { previewLiteralText } from './free-html-library/html-edit-kernel.mjs';

const pkg = { html: '<h1 data-shine-node="a">相同</h1><h2 data-shine-node="b">相同</h2><p data-shine-node="bound">42</p><div data-shine-node="nested">文本<strong>子节点</strong></div>',
  css: '', js: '', resources: [], node_map: ['a','b','bound','nested'].map(node_id => ({ node_id, kind: 'static_element', selector: `[data-shine-node="${node_id}"]` })) };
test('only mapped static leaf text is selectable; bound values and nested markup stay read-only', () => {
  const nodes = editableTextNodes(pkg, { bindings: [{ node_id: 'bound' }] });
  assert.deepEqual(nodes.map(row => row.node_id), ['a','b']);
  assert.equal(previewLiteralText({ pkg, selection: { kind: 'static_element', node_id: 'nested' }, replacementText: 'x' }).error.code, 'TEXT_REPLACE_UNSUPPORTED');
  const dynamic = { ...pkg, js: 'document.querySelector(\'[data-shine-node="a"]\').textContent = "dynamic";' };
  assert.equal(editableTextNodes(dynamic).some(row => row.node_id === 'a'), false);
});
test('opaque-origin bridge rejects wrong window, token, page, version, unknown nodes and write-shaped messages', () => {
  const source = {}, nodes = editableTextNodes(pkg);
  const context = { source, channel: 'nonce', pageId: 'page_a', version: 2, nodes };
  const data = { type: 'cockpit.selection', channel: 'nonce', pageId: 'page_a', version: 2, nodeId: 'b' };
  const event = { source, origin: 'null', data };
  assert.equal(acceptSelection(event, context).node_id, 'b');
  for (const patch of [{ source: {} }, { origin: 'https://example.invalid' },
    ...[{ channel: 'wrong' }, { pageId: 'other' }, { version: 1 }, { nodeId: 'unknown' }, { replacementText: 'write' }].map(patch => ({ data: { ...data, ...patch } }))]) {
    assert.equal(acceptSelection({ ...event, ...patch }, context), undefined);
  }
  assert.equal(acceptSelection({ ...event, data: { ...data, nodeId: null } }, context), null);
});
test('browse retains normal interactions; editing adds only the selection bridge under the unchanged CSP', () => {
  const config = { channel: 'nonce', pageId: 'page_a', version: 1, nodes: editableTextNodes(pkg) };
  const browse = selectionSrcdoc(pkg, config);
  const edit = selectionSrcdoc(pkg, { ...config, editing: true });
  assert.doesNotMatch(browse, /cockpit\.selection/);
  assert.match(edit, /cockpit\.selection/);
  assert.match(edit, /Content-Security-Policy/);
  assert.doesNotMatch(edit, /allow-same-origin/);
  assert.match(edit, /data-cockpit-target.*data-cockpit-selected/);
});
