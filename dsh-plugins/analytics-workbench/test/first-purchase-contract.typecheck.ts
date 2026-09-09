import type { paths, components } from '../src/first-purchase-contract.generated';
type Snapshot = components['schemas']['FirstPurchaseKernelSnapshot'];
type Create = paths['/api/v1/analytics-first-purchase/runs']['post'];
export function status(run: Snapshot): string { return run.status; }
export type Accepted = Create['responses'][202]['content']['application/json'];
