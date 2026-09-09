// Compiler-only first-purchase saved-analysis HTTP contract; plugin view stays NOT_CONNECTED.
import type { components, operations } from '../src/first-purchase-analysis-contract.generated.js';

type Created = components['schemas']['FirstPurchaseAnalysisCreateRequest'];
type Saved = components['schemas']['FirstPurchaseSavedAnalysis'];
type Listed = components['schemas']['FirstPurchaseSavedAnalysisList'];
type CreateHeaders = NonNullable<operations['analytics_first_purchase_analysis_create']['parameters']['header']>;

export const createBody: Created = {
  created_from_run_id: 'run_fixture',
  title: '首购商品路径 / 30日正装转化',
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
export const unknownSchema: Saved['schema_version'] = 'analytics-saved-analysis/v1';
