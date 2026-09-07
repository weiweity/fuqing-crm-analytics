import test from 'node:test';
import assert from 'node:assert/strict';
import { formatEmptyReason, formatFenYuan, formatRatioPercent } from '../src/query-format.mjs';

test('raw 0-1 ratios become percents; null stays an explicit placeholder', () => {
  assert.equal(formatRatioPercent(0.25), '25%');
  assert.equal(formatRatioPercent(0.5), '50%');
  assert.equal(formatRatioPercent(0.5714285714285714), '57.1%');
  assert.equal(formatRatioPercent(null), '—');
  assert.equal(formatRatioPercent(1.2), null);
  assert.equal(formatRatioPercent(Number.NaN), null);
});

test('integer fen become yuan; null stays an explicit placeholder', () => {
  assert.equal(formatFenYuan(100), '1.00 元');
  assert.equal(formatFenYuan(87000), '870.00 元');
  assert.equal(formatFenYuan(110000), '1100.00 元');
  assert.equal(formatFenYuan(null), '—');
  assert.equal(formatFenYuan(1.5), null);
  assert.equal(formatFenYuan(-1), null);
});

test('empty mature reason keeps a Chinese meaning and the machine code', () => {
  assert.deepEqual(formatEmptyReason(null), { text: '', code: null });
  const empty = formatEmptyReason('EMPTY_MATURE_COHORT');
  assert.equal(empty.code, 'EMPTY_MATURE_COHORT');
  assert.match(empty.text, /空成熟队列/);
  assert.notEqual(empty.text, 'EMPTY_MATURE_COHORT');
  assert.equal(formatEmptyReason('OTHER'), null);
});
