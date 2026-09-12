import test from 'node:test';
import assert from 'node:assert/strict';
import { applyGenerate, generateBoard, specFromGsvFacts, specWithLink, summarizeGenerate } from './generate.mjs';
import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from './fixture.mjs';

test('generateBoard accepts the Figma GENERATE_BOARD fixture', () => {
  const got = generateBoard(BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  assert.equal(got.ok, true);
  assert.equal(got.value.spec.board_id, BOARD_SPEC_FIXTURE.board_id);
  assert.equal(got.value.facts, BOARD_SPEC_FACTS);
});

test('generateBoard rejects unknown kind and does not return a half board', () => {
  const got = generateBoard({
    board_id: 'board_bad',
    version: 1,
    blocks: [{ block_id: 'z', kind: 'PIE' }],
  }, BOARD_SPEC_FACTS);
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'SPEC_KIND');
  assert.equal('value' in got, false);
});

test('applyGenerate keeps the previous spec when the next board is illegal', () => {
  const draft = { boardSpec: BOARD_SPEC_FIXTURE, boardFacts: BOARD_SPEC_FACTS, boardError: '' };
  const got = applyGenerate(draft, { board_id: 'x', version: 1, blocks: [{ block_id: 'z', kind: 'PIE' }] });
  assert.equal(got.ok, false);
  assert.equal(draft.boardSpec, BOARD_SPEC_FIXTURE);
  assert.match(draft.boardError, /非法 kind/);
});

test('applyGenerate writes a legal board', () => {
  const draft = { boardSpec: null, boardFacts: null, boardError: 'old' };
  const got = applyGenerate(draft, BOARD_SPEC_FIXTURE, BOARD_SPEC_FACTS);
  assert.equal(got.ok, true);
  assert.equal(draft.boardError, '');
  assert.equal(draft.boardSpec.board_id, BOARD_SPEC_FIXTURE.board_id);
});

test('specWithLink appends a LINK without Feishu token and skips duplicates', () => {
  const link = BOARD_SPEC_FIXTURE.blocks.find((b) => b.block_id === 'b7');
  const empty = specWithLink(null, link);
  assert.equal(empty.ok, true);
  assert.equal(empty.value.blocks.length, 1);
  assert.equal(empty.value.blocks[0].kind, 'LINK');
  const merged = specWithLink(BOARD_SPEC_FIXTURE, link);
  assert.equal(merged.ok, true);
  assert.equal(merged.value.blocks.filter((b) => b.block_id === 'b7').length, 1);
});

test('specFromGsvFacts refuses empty catalog and does not invent 400', () => {
  const empty = specFromGsvFacts({});
  assert.equal(empty.ok, false);
  assert.equal(empty.error.code, 'GENERATE_EMPTY');
});

test('specFromGsvFacts binds METRIC/BAR to verified 410/305', () => {
  const facts = { result_c0: { current_gsv: 410, comparison_gsv: 305, difference: 105 } };
  const spec = specFromGsvFacts(facts);
  assert.equal(spec.ok, true);
  const metric = spec.value.blocks.find((b) => b.kind === 'METRIC');
  assert.equal(metric.source_result_id, 'result_c0');
  assert.deepEqual(metric.layout, { x: 0, y: 0, w: 6, h: 4 });
  assert.equal(metric.query_binding, 'retail_gsv');
  const view = generateBoard(spec.value, facts);
  assert.equal(view.ok, true);
  assert.equal(view.value.spec.blocks[0].kind, 'METRIC');
});

test('summarizeGenerate lists kinds without writing', () => {
  const text = summarizeGenerate(BOARD_SPEC_FIXTURE);
  assert.match(text, /即将写入/);
  assert.match(text, /METRIC/);
  assert.match(text, /确认后进入画布/);
});

test('specWithLink refuses non-LINK; summarizeGenerate returns the parse error', () => {
  const bad = specWithLink(null, { block_id: 'x', kind: 'METRIC' });
  assert.equal(bad.ok, false);
  assert.equal(bad.error.code, 'SPEC_LINK');
  const msg = summarizeGenerate({ board_id: 'x', version: 1, blocks: [{ block_id: 'z', kind: 'PIE' }] });
  assert.match(msg, /非法 kind/);
  const illegalBoard = specWithLink(
    { board_id: 'x', version: 1, blocks: [{ block_id: 'z', kind: 'PIE' }] },
    BOARD_SPEC_FIXTURE.blocks.find((b) => b.kind === 'LINK'),
  );
  assert.equal(illegalBoard.ok, false);
  const withSession = specFromGsvFacts(
    { result_c0: { current_gsv: 410, comparison_gsv: 305, difference: 105 } },
    { session_id: 'sess_ask', board_id: 'board_custom' },
  );
  assert.equal(withSession.value.session_id, 'sess_ask');
  assert.equal(withSession.value.board_id, 'board_custom');
});
