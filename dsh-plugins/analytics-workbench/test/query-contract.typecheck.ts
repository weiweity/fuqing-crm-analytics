// Compiler-only positive and negative contracts; not a connected DSH adapter or HTTP client.
import type { components } from '../src/query-contract.generated.js';

type QueryRequest = components['schemas']['ChannelFollowupQueryRequest'];
type QueryResult = components['schemas']['ChannelFollowupResult'];
type QueryFacts = components['schemas']['ChannelFollowupFacts'];
type QueryCounts = components['schemas']['ChannelFollowupCounts'];
type Snapshot = components['schemas']['ChannelFollowupSnapshot'];
type Resolved = components['schemas']['ChannelFollowupResolvedFilters'];

export const queryRequest: QueryRequest = {
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

export const emptyMature: QueryCounts = {
  channel_mature_cohort_count: 0,
  channel_immature_count: 2,
  channel_repeat_count: 0,
  channel_cross_channel_count: 0,
  channel_repeat_ratio: null,
  channel_cross_channel_ratio: null,
  channel_window_net_paid_minor: null,
  channel_empty_reason: 'EMPTY_MATURE_COHORT',
};

export const facts: QueryFacts = {
  display_name: '首次观察到的渠道 / N日二单率',
  currency: 'CNY',
  amount_unit: 'minor',
  amount_precision: 'integer_fen',
  observation_days: 30,
  channels: [{
    channel_id: 'A',
    channel_mature_cohort_count: 7,
    channel_immature_count: 1,
    channel_repeat_count: 4,
    channel_cross_channel_count: 3,
    channel_repeat_ratio: 0.5714285714285714,
    channel_cross_channel_ratio: 0.42857142857142855,
    channel_window_net_paid_minor: 87000,
    channel_empty_reason: null,
  }],
  totals: {
    channel_mature_cohort_count: 7,
    channel_immature_count: 1,
    channel_repeat_count: 4,
    channel_cross_channel_count: 3,
    channel_repeat_ratio: 0.5714285714285714,
    channel_cross_channel_ratio: 0.42857142857142855,
    channel_window_net_paid_minor: 87000,
    channel_empty_reason: null,
  },
};

export function isSyntheticResult(result: QueryResult) {
  return result.contains_real_data === false && result.schema_version === 'analytics-channel-followup/v1';
}

export function snapshotIdsAreStrings(snapshot: Snapshot) {
  return snapshot.orders.every((order) => typeof order.order_id === 'string' && typeof order.synthetic_user_id === 'string');
}

// @ts-expect-error B0 run schema is not the channel-follow-up query contract.
export const b0Schema: QueryRequest['schema_version'] = 'analytics-run-b0/v1';
// @ts-expect-error as_of is snapshot-resolved and is not a request field.
export const asOfOnRequest: QueryRequest = { ...queryRequest, as_of: '2026-09-01T00:00:00+08:00' };
// @ts-expect-error Arbitrary SQL is outside the query contract.
export const extraSql: QueryRequest = { ...queryRequest, sql: 'SELECT private_information' };
// @ts-expect-error Display name is the first-observed / N-day repeat label, not lifetime repurchase.
export const wrongName: QueryFacts['display_name'] = '终身复购';
// @ts-expect-error B0 25% fixture string is not a channel-follow-up ratio.
export const b0Ratio: QueryCounts['channel_repeat_ratio'] = '25%';
// @ts-expect-error User/order lists are not part of published facts.
export const leakedIds: QueryFacts = { ...facts, user_ids: ['a'] };
// @ts-expect-error Non-empty product filters are outside analytics-channel-followup/v1.
export const nonemptyProducts: QueryRequest = { ...queryRequest, product_ids: ['sku_a'] };
// @ts-expect-error Resolved product_ids cannot contain a product id.
export const resolvedProducts: Resolved['product_ids'] = ['sku_a'];
export const maxSafeNet: QueryCounts['channel_window_net_paid_minor'] = 9007199254740991;
