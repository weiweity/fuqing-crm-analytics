// Compiler-only C0 contract; not a connected DSH adapter or HTTP client.
import type { components } from '../../../../dsh-plugins/analytics-workbench/src/competition-c0-contract.generated.js';

type Condition = components['schemas']['CompetitionCondition'];
type ResultRef = components['schemas']['CompetitionResultRef'];
type BoardSpec = components['schemas']['CompetitionBoardSpec'];
type Patch = components['schemas']['CompetitionPatchRequest'];
type Batch = components['schemas']['CompetitionBoardBatchRequest'];
type Receipt = components['schemas']['CompetitionBoardBatchReceipt'];
type Candidates = components['schemas']['CompetitionCandidateSet'];
type Draft = components['schemas']['CompetitionActionDraft'];
type C0Error = components['schemas']['CompetitionErrorDetail'];
type AddOp = components['schemas']['AnalyticsCockpitAddOp'];

const period = {
  start_date: '2026-08-01',
  end_date: '2026-08-31',
  end_bound: 'INCLUSIVE_CALENDAR_DAY' as const,
};
const scope = { kind: 'ALL' as const, channel_ids: [], product_ids: [] };

export const condition: Condition = {
  schema_version: 'competition-condition/v1',
  metrics_contract_id: 'competition-metrics/v1',
  metric_type: 'GSV',
  timezone: 'Asia/Shanghai',
  current_period: period,
  comparison_mode: 'YOY_SAME_PERIOD',
  comparison_period: period,
  sales_scope: scope,
  history_scope: scope,
  sample_mode: 'EXCLUDE_CURRENT_SALES_ONLY',
  sample_channel_ids: ['sample-channel-unverified-a'],
  data_cutoff_policy: 'T_PLUS_1_YESTERDAY',
  leap_day_alignment: 'CLAMP_TO_MONTH_END',
  data_snapshot_ref: 'synthetic-c0-demo-v1',
  as_of: '2026-08-31T16:00:00.000000+00:00',
  rule_version: 'competition-condition-rule/v1',
};

export function isEmptyResult(row: ResultRef) {
  return row.completeness === 'EMPTY' && row.row_count === 0 && row.contains_real_data === false;
}

export function isPrivateBoard(row: BoardSpec) {
  return row.visibility === 'PRIVATE' && row.existing_dashboard_schema === 'analytics-cockpit/v1';
}

export const addOp: AddOp = {
  op: 'add',
  analysis_ref: { analysis_id: 'analysis_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', version: 1 },
  display_overrides: null,
  layout: null,
  plugin_ref: null,
};

export function isPartialReceipt(row: Receipt) {
  return row.status === 'PARTIAL';
}

export function refusesAutoSend(row: Candidates | Draft) {
  return row.auto_send === false;
}

export function errorHasParam(row: C0Error) {
  return row.param !== undefined && row.maps_to === 'backend.contracts.analytics.AnalyticsErrorDetail';
}

export function patchIsStyle(row: Patch) {
  return row.intent === 'STYLE_ONLY';
}

export function batchIsOneBoard(row: Batch) {
  return row.layout_mode === 'ONE_BOARD_MULTI_BLOCK';
}

// @ts-expect-error C0 tools cannot inherit the old /table GMV default.
export const gmv: Condition['metric_type'] = 'GMV';
// @ts-expect-error B0 STUB schema is not a competition result.
export const b0Result: ResultRef['schema_version'] = 'analytics-run-b0/v1';
// @ts-expect-error Public boards are outside C0.
export const publicBoard: BoardSpec['visibility'] = 'PUBLIC';
// @ts-expect-error Action drafts cannot auto-send.
export const send: Draft['auto_send'] = true;
// @ts-expect-error Existing cockpit add cannot upload facts.
export type ForgedFacts = AddOp['facts'];
