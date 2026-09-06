// Compiler-only positive and negative contracts; not a connected DSH adapter.
import type { components, operations } from '../src/run-contract.generated.js';

type Snapshot = components['schemas']['AnalyticsRunSnapshot'];
type Accepted = components['schemas']['AnalyticsRunAccepted'];
type Facts = components['schemas']['AnalyticsB0Facts'];
type CancelHeaders = NonNullable<operations['analytics_cancel_run']['parameters']['header']>;

export const initial: Accepted = {
  schema_version: 'analytics-run-b0/v1', run_id: 'run_fixture', version: 1,
  status: 'QUEUED', phase: 'ACCEPTED', location: '/api/v1/analytics/runs/run_fixture',
};
export const cancelHeaders: CancelHeaders = { 'Idempotency-Key': 'cancel-1', 'If-Match': '2' };
export const syntheticFacts: Facts = { customers: 100, repeat_customers: 25, repeat_ratio: 0.25 };
export function canReadFinalResult(run: Snapshot) {
  return run.status === 'SUCCEEDED' && run.result?.contains_real_data === false;
}
// @ts-expect-error A running snapshot cannot replace the original 202 contract.
export const falseAccepted: Accepted['status'] = 'RUNNING';
// @ts-expect-error Current version is required by the generated cancel contract.
export const missingVersion: CancelHeaders = { 'Idempotency-Key': 'cancel-1' };
// @ts-expect-error Arbitrary model facts are outside the fixed B0 fixture.
export const fabricatedCount: Facts['customers'] = 101;
// @ts-expect-error The generated schema also preserves the exact B0 ratio.
export const fabricatedRatio: Facts['repeat_ratio'] = 0.5;
