import test from 'node:test';
import assert from 'node:assert/strict';
import { interpretBoard } from './interpret.mjs';
import { catalogFromGsvItems, factsFromGsvResult } from './facts-from-result.mjs';
import { BOARD_SPEC_FIXTURE } from './fixture.mjs';

test('factsFromGsvResult copies 410/305 and does not invent 400', () => {
  const got = factsFromGsvResult({
    facts: { current: { gsv: 410 }, comparison: { gsv: 305 }, difference: 105, change_ratio: 105 / 305 },
  });
  assert.equal(got.ok, true);
  assert.equal(got.value.r1.current_gsv, 410);
  assert.equal(got.value.r1.comparison_gsv, 305);
  const view = interpretBoard(BOARD_SPEC_FIXTURE, got.value);
  assert.equal(view.value.blocks.find((b) => b.block_id === 'b1').paint.headline, 410);
});

test('catalogFromGsvItems keys rows by result_id not a fake r1', () => {
  const catalog = catalogFromGsvItems([{
    result_id: 'result_c0_gsv_20260831',
    facts: { current: { gsv: 410 }, comparison: { gsv: 305 }, difference: 105 },
  }]);
  assert.equal(catalog.result_c0_gsv_20260831.current_gsv, 410);
  assert.equal(catalog.r1, undefined);
});

test('factsFromGsvResult refuses incomplete GSV', () => {
  const got = factsFromGsvResult({ facts: { current: { gsv: 410 } } });
  assert.equal(got.ok, false);
  assert.equal(got.error.code, 'FACTS_SHAPE');
});
