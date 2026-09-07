import type { components as B0 } from './run-contract.generated.js';
import type { components as Query } from './query-run-contract.generated.js';
export interface RunView {
  ready: boolean;
  sessionId: string;
  runs: Array<B0['schemas']['AnalyticsRunSnapshot'] | Query['schemas']['AnalyticsQueryRunSnapshot']>;
}
export function emptyRunView(sessionId: string): RunView;
export function visibleRunView(view: RunView | null | undefined, sessionId: string): RunView;
export function loadRunView(fetcher: typeof fetch, sessionId: string, signal: AbortSignal): Promise<RunView>;
