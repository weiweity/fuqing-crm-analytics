import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeQueryReceipt, decodeQueryRequest } from '../src/query-model.mjs';

const request = {
  schema_version: 'analytics-channel-followup/v1',
  query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1',
  metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1',
  cohort_window: { kind: 'FIXED', start_date: '2026-06-01', end_date: '2026-09-01' },
  observation_days: 30,
  data_snapshot_ref: 'synthetic-channel-followup-v1',
  timezone: 'Asia/Shanghai',
  channel_ids: [],
  cohort_ref: null,
  product_ids: [],
  exclude_low_price: false,
  comparison: null,
};
const counts = {
  channel_mature_cohort_count: 2,
  channel_immature_count: 0,
  channel_repeat_count: 1,
  channel_cross_channel_count: 0,
  channel_repeat_ratio: 0.5,
  channel_cross_channel_ratio: 0,
  channel_window_net_paid_minor: 100,
  channel_empty_reason: null,
};
const filters = {
  schema_version: 'analytics-channel-followup/v1',
  query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1',
  metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1',
  data_version: 'synthetic-channel-followup-data/v1',
  hash_version: 'channel-followup-filter-hash/v1',
  cohort_window_kind: 'FIXED',
  resolved_cohort_start: '2026-05-31T16:00:00.000000+00:00',
  resolved_cohort_end: '2026-08-31T16:00:00.000000+00:00',
  observation_days: 30,
  data_snapshot_ref: 'synthetic-channel-followup-v1',
  as_of: '2026-08-31T16:00:00.000000+00:00',
  timezone: 'Asia/Shanghai',
  channel_ids: ['A'],
  cohort_ref: null,
  product_ids: [],
  exclude_low_price: false,
  comparison: null,
  permission_scope: 'scope_1',
  data_digest: 'a'.repeat(64),
  filter_hash: 'b'.repeat(64),
};
const result = {
  schema_version: 'analytics-channel-followup/v1',
  answer_mode: 'DETERMINISTIC_TOOL',
  query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1',
  metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1',
  data_version: 'synthetic-channel-followup-data/v1',
  hash_version: 'channel-followup-filter-hash/v1',
  contains_real_data: false,
  data_source: 'SYNTHETIC_SNAPSHOT',
  data_snapshot_ref: 'synthetic-channel-followup-v1',
  as_of: filters.as_of,
  resolved_filters: filters,
  filter_hash: filters.filter_hash,
  facts: {
    display_name: '首次观察到的渠道 / N日二单率',
    currency: 'CNY', amount_unit: 'minor', amount_precision: 'integer_fen',
    observation_days: 30,
    channels: [{ channel_id: 'A', ...counts }],
    totals: counts,
  },
  limitations: ['synthetic only'],
};
const receipt = {
  schema_version: 'analytics-run-channel-followup-native-receipt/v1',
  run_id: 'run_1', attempt_id: 'attempt_1', step_id: 'step_1',
  disposition: 'EXECUTE', result,
};

test('valid request and receipt decode', () => {
  assert.equal(decodeQueryRequest(request).observation_days, 30);
  const decoded = decodeQueryReceipt(receipt);
  assert.equal(decoded.schema_version, receipt.schema_version);
  assert.equal(decoded.result.facts.totals.channel_repeat_count, 1);
});

test('SQL extra field unknown version and unknown schema are rejected', () => {
  assert.equal(decodeQueryRequest({ ...request, sql: 'SELECT 1' }), null);
  assert.equal(decodeQueryRequest({ ...request, extra: true }), null);
  assert.equal(decodeQueryRequest({ ...request, query_version: 'channel-followup-query/v0' }), null);
  assert.equal(decodeQueryReceipt({ ...receipt, schema_version: 'analytics-run-b0/v1' }), null);
});

test('illegal numbers and null shapes do not decode', () => {
  const empty = { ...counts, channel_mature_cohort_count: 0, channel_repeat_count: 0,
    channel_repeat_ratio: 0, channel_cross_channel_ratio: 0, channel_window_net_paid_minor: 0,
    channel_empty_reason: null };
  const badNull = structuredClone(receipt);
  badNull.result.facts.channels[0] = { channel_id: 'A', ...empty };
  badNull.result.facts.totals = empty;
  assert.equal(decodeQueryReceipt(badNull), null);
  const nanRatio = structuredClone(receipt);
  nanRatio.result.facts.totals = { ...counts, channel_repeat_ratio: Number.NaN };
  nanRatio.result.facts.channels[0] = { channel_id: 'A', ...counts, channel_repeat_ratio: Number.NaN };
  assert.equal(decodeQueryReceipt(nanRatio), null);
  const boolCount = structuredClone(receipt);
  boolCount.result.facts.totals = { ...counts, channel_mature_cohort_count: true };
  assert.equal(decodeQueryReceipt(boolCount), null);
});
