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

test('factsFromGsvResult computes difference when omitted; catalog keys source_result_ref and id', () => {
  const got = factsFromGsvResult({
    facts: { current: { gsv: 50 }, comparison: { gsv: 20 } },
  });
  assert.equal(got.ok, true);
  assert.equal(got.value.r1.difference, 30);
  assert.equal('change_ratio' in got.value.r1, false);
  const catalog = catalogFromGsvItems([
    { facts: { current: { gsv: 1 } } },
    { source_result_ref: 'src_a', facts: { current: { gsv: 10 }, comparison: { gsv: 4 }, difference: 6 } },
    { id: 'legacy', facts: { current: { gsv: 8 }, comparison: { gsv: 8 }, difference: 0 } },
    { facts: { current: { gsv: 3 }, comparison: { gsv: 1 }, difference: 2 } },
  ]);
  assert.equal(catalog.src_a.current_gsv, 10);
  assert.equal(catalog.legacy.current_gsv, 8);
  assert.equal(catalog.r3.current_gsv, 3);
  assert.deepEqual(catalogFromGsvItems(null), {});
});
