// Compiler-only saved-analysis HTTP contract; plugin view stays NOT_CONNECTED.
import type { components, operations } from '../src/analysis-contract.generated.js';

type Created = components['schemas']['AnalyticsAnalysisCreateRequest'];
type Saved = components['schemas']['AnalyticsSavedAnalysis'];
type Listed = components['schemas']['AnalyticsSavedAnalysisList'];
type CreateHeaders = NonNullable<operations['analytics_analysis_create']['parameters']['header']>;

export const createBody: Created = {
  created_from_run_id: 'run_fixture',
  title: '首次观察到的渠道 / 30日二单率',
  visual_spec: { schema_version: 'analytics-visual-table/v1', kind: 'TABLE' },
};
export const createHeaders: CreateHeaders = { 'Idempotency-Key': 'save-1' };
export function isConnectedSnapshot(row: Saved) {
  return row.http_api === 'CONNECTED' && row.data_mode === 'SNAPSHOT' && row.finite_mock === true;
}
export function emptyList(rows: Listed) {
  return rows.items.length === 0;
}
// @ts-expect-error Browser cannot upload facts to prove success.
export type ForgedFacts = Created['facts'];
// @ts-expect-error HTTP surface is CONNECTED, not the mock NOT_CONNECTED flag.
export const mockFlag: Saved['http_api'] = 'NOT_CONNECTED';
// @ts-expect-error Unknown schema is outside this contract.
export const unknownSchema: Saved['schema_version'] = 'analytics-saved-analysis/v0';
