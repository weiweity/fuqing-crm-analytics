import test from 'node:test';
import assert from 'node:assert/strict';
import { parseBoardSpec, parsePatchBlock, parseRollback, applyPatch } from './schema.mjs';

const validBoard = {
  board_id: 'board_retail_gsv_2026_08',
  version: 1,
  session_id: 'sess_1',
  blocks: [
    { block_id: 'b1', kind: 'METRIC', title: '零售 GSV', metric_ref: 'retail_gsv', source_result_id: 'r1' },
    { block_id: 'b2', kind: 'BAR', title: '两期对比', metric_ref: 'retail_gsv', source_result_id: 'r1' },
    { block_id: 'b3', kind: 'html_sandbox', title: '渠道结构', source_result_id: 'r1' },
  ],
};

test('parseBoardSpec accepts GENERATE_BOARD minimum', () => {
  const got = parseBoardSpec(validBoard);
  assert.equal(got.ok, true);
  assert.equal(got.value.blocks.length, 3);
});

test('parseBoardSpec accepts layout and rejects fractional w', () => {
  const got = parseBoardSpec({
    ...validBoard,
    blocks: [{ block_id: 'b1', kind: 'METRIC', layout: { x: 0, y: 0, w: 6, h: 4 } }],
  });
  assert.equal(got.ok, true);
  const bad = parseBoardSpec({
    ...validBoard,
    blocks: [{ block_id: 'b1', kind: 'METRIC', layout: { x: 0, y: 0, w: 1.5, h: 4 } }],
  });
  assert.equal(bad.ok, false);
  assert.equal(bad.error.code, 'SPEC_LAYOUT');
});

test('parseBoardSpec rejects unknown kind', () => {
  const got = parseBoardSpec({
    ...validBoard,
    blocks: [{ block_id: 'x', kind: 'PIE' }],
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'SPEC_KIND');
});

test('parseBoardSpec rejects duplicate block_id', () => {
  const got = parseBoardSpec({
    ...validBoard,
    blocks: [
      { block_id: 'b1', kind: 'METRIC' },
      { block_id: 'b1', kind: 'BAR' },
    ],
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'SPEC_BLOCK_DUP');
});

test('parsePatchBlock requires base_version', () => {
  const got = parsePatchBlock({ block_id: 'b3', op: 'set_title', title: '本月渠道占比' });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'PATCH_BASE_VERSION');
});

test('applyPatch set_title bumps version and does not touch source_result_id', () => {
  const got = applyPatch(validBoard, {
    block_id: 'b3',
    base_version: 1,
    op: 'set_title',
    title: '本月渠道占比',
  });
  assert.equal(got.ok, true);
  assert.equal(got.value.version, 2);
  assert.equal(got.value.blocks[2].title, '本月渠道占比');
  assert.equal(got.value.blocks[2].source_result_id, 'r1');
});

test('applyPatch rejects stale base_version', () => {
  const got = applyPatch(validBoard, {
    block_id: 'b3',
    base_version: 9,
    op: 'set_title',
    title: 'x',
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'PATCH_VERSION_CONFLICT');
});

test('parseRollback accepts to_version', () => {
  const got = parseRollback({ board_id: validBoard.board_id, to_version: 1 });
  assert.equal(got.ok, true);
});

test('LINK kind requires url', () => {
  const got = parseBoardSpec({
    board_id: 'b',
    version: 1,
    blocks: [{ block_id: 'l1', kind: 'LINK', title: '飞书文档' }],
  });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'SPEC_LINK');
});

test('applyPatch set_kind/set_layout/set_metric_ref; LINK href ok; missing block and LINK-without-url refused', () => {
  const href = parseBoardSpec({
    board_id: 'b',
    version: 1,
    blocks: [{ block_id: 'l1', kind: 'LINK', href: 'https://example.invalid/x' }],
  });
  assert.equal(href.ok, true);
  const kind = applyPatch(validBoard, { block_id: 'b1', base_version: 1, op: 'set_kind', kind: 'LINE' });
  assert.equal(kind.ok, true);
  assert.equal(kind.value.blocks[0].kind, 'LINE');
  const layout = applyPatch(validBoard, {
    block_id: 'b1', base_version: 1, op: 'set_layout', layout: { x: 1, y: 2, w: 3, h: 4 },
  });
  assert.deepEqual(layout.value.blocks[0].layout, { x: 1, y: 2, w: 3, h: 4 });
  const metric = applyPatch(validBoard, {
    block_id: 'b1', base_version: 1, op: 'set_metric_ref', metric_ref: 'retail_gsv',
  });
  assert.equal(metric.value.blocks[0].metric_ref, 'retail_gsv');
  const missing = applyPatch(validBoard, { block_id: 'nope', base_version: 1, op: 'set_title', title: 'x' });
  assert.equal(missing.error.code, 'PATCH_BLOCK_MISSING');
  const toLink = applyPatch(validBoard, { block_id: 'b1', base_version: 1, op: 'set_kind', kind: 'LINK' });
  assert.equal(toLink.ok, false);
  assert.equal(toLink.error.code, 'SPEC_LINK');
});
