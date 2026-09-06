// Compiler-only query-run store contract; not a connected DSH adapter or HTTP client.
import type { components } from '../src/query-run-contract.generated.js';

type QueryRunSnapshot = components['schemas']['AnalyticsQueryRunSnapshot'];
type QueryRunAccepted = components['schemas']['AnalyticsQueryRunAccepted'];
type QueryRunRequest = components['schemas']['AnalyticsQueryRunRequest'];
type QueryResult = components['schemas']['ChannelFollowupResult'];
type Descriptor = components['schemas']['ChannelFollowupFixtureDescriptor'];
type QueryReceipt = components['schemas']['AnalyticsQueryNativeReceipt'];

export const accepted: QueryRunAccepted = {
  schema_version: 'analytics-run-channel-followup/v1',
  run_id: 'run_fixture',
  version: 1,
  status: 'QUEUED',
  phase: 'ACCEPTED',
  location: '/internal/store/analytics-query/runs/run_fixture',
};

export const request: QueryRunRequest = {
  schema_version: 'analytics-run-channel-followup/v1',
  question: '查看合成渠道后续购买',
  parent_run_id: null,
  condition_patch: null,
};

export const descriptor: Descriptor = {
  snapshot_id: 'synthetic-channel-followup-v1',
  data_version: 'synthetic-channel-followup-data/v1',
  data_digest: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  as_of: '2026-08-31T16:00:00.000000+00:00',
  timezone: 'Asia/Shanghai',
  physical_sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
};

export function isQueryRun(run: QueryRunSnapshot) {
  return run.schema_version === 'analytics-run-channel-followup/v1' && run.answer_mode === 'DETERMINISTIC_TOOL';
}

export function resultIsSynthetic(result: QueryResult) {
  return result.contains_real_data === false && result.schema_version === 'analytics-channel-followup/v1';
}

export function receiptIsQuery(receipt: QueryReceipt) {
  return receipt.schema_version === 'analytics-run-channel-followup-native-receipt/v1'
    && (receipt.disposition === 'EXECUTE' || receipt.disposition === 'REUSE_RESULT');
}

// @ts-expect-error B0 run schema is not the query-run store contract.
export const b0Schema: QueryRunAccepted['schema_version'] = 'analytics-run-b0/v1';
// @ts-expect-error B0 STUB answer mode cannot be used on the query-run snapshot.
export const stubAnswer: QueryRunSnapshot['answer_mode'] = 'STUB';
// @ts-expect-error Arbitrary SQL is outside the query-run request.
export const extraSql: QueryRunRequest = { ...request, sql: 'SELECT private_information' };
// @ts-expect-error The generated snapshot result is G2 ChannelFollowupResult, not B0 facts.
export const b0Facts: QueryRunSnapshot['result'] = { schema_version: 'analytics-run-b0/v1', answer_mode: 'STUB' };
// @ts-expect-error B0 run schema is not the query native receipt.
export const b0ReceiptSchema: QueryReceipt['schema_version'] = 'analytics-run-b0/v1';
