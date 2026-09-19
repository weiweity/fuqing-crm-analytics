import test from 'node:test';
import assert from 'node:assert/strict';
import { describeBlockPatch, validateBlockChanges } from './block-changes.mjs';

test('METRIC patches expose source_result_id, not a fake props.metric_ref', () => {
  const block = { kind: 'METRIC', source_result_id: 'result_a' };
  const described = describeBlockPatch(block, {
    factsByResultId: { result_a: { current_gsv: 1 }, result_b: { current_gsv: 2 } },
  });
  assert.equal(described.supported, true);
  assert.equal(described.source_result_id, true);
  assert.deepEqual(described.source_result_options, ['result_a', 'result_b']);
  assert.equal(described.metric_ref, undefined);
  assert.equal(Object.hasOwn(described, 'metric_ref_options'), false);
  assert.ok(!described.props.includes('metric_ref'));

  const rejected = validateBlockChanges(
    { props: { metric_ref: 'retail_gsv' } },
    { block },
  );
  assert.equal(rejected.ok, false);
  assert.match(rejected.message, /source_result_id/);

  const allowed = validateBlockChanges(
    { source_result_id: 'result_b', props: { show_comparison: false } },
    { block, factsByResultId: { result_a: {}, result_b: {} } },
  );
  assert.equal(allowed.ok, true, JSON.stringify(allowed));
  const unknownFact = validateBlockChanges(
    { source_result_id: 'result_z' },
    { block, factsByResultId: { result_a: {} } },
  );
  assert.equal(unknownFact.ok, false);
});
