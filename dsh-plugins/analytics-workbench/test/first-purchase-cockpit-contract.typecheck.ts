// Compiler-only first-purchase cockpit HTTP contract; plugin view stays NOT_CONNECTED.
import type { components, operations } from '../src/first-purchase-cockpit-contract.generated.js';

type Created = components['schemas']['FirstPurchaseCockpitCreateRequest'];
type Add = components['schemas']['FirstPurchaseCockpitAddOp'];
type Saved = components['schemas']['FirstPurchaseDashboard'];
type Listed = components['schemas']['FirstPurchaseDashboardList'];
type CreateHeaders = NonNullable<operations['analytics_first_purchase_dashboard_create']['parameters']['header']>;

export const createBody: Created = { title: '我的首购驾驶舱' };
export const createHeaders: CreateHeaders = { 'Idempotency-Key': 'board-1' };
export const addBody: Add = {
  op: 'add',
  analysis_ref: { analysis_id: 'analysis_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', version: 1 },
};
export function isConnectedBoard(row: Saved) {
  return row.http_api === 'CONNECTED' && row.finite_mock === true && row.preview === false;
}
export function emptyList(rows: Listed) {
  return rows.items.length === 0;
}
export function createSuccessStatus(status: 200 | 201): keyof operations['analytics_first_purchase_dashboard_create']['responses'] {
  return status;
}
// @ts-expect-error Browser cannot upload facts to prove a card.
export type ForgedFacts = Add['facts'];
// @ts-expect-error HTTP add cannot send a snapshot.
export type ForgedSnapshot = Add['snapshot'];
// @ts-expect-error HTTP surface is CONNECTED, not the mock NOT_CONNECTED flag.
export const mockFlag: Saved['http_api'] = 'NOT_CONNECTED';
// @ts-expect-error Unknown op is outside this contract.
export const unknownOp: Add['op'] = 'ai_edit';
