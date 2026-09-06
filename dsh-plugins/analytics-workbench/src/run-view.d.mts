import type { components } from './run-contract.generated.js';
export interface RunView { ready: boolean; runs: components['schemas']['AnalyticsRunSnapshot'][] }
export function loadRunView(fetcher: typeof fetch, sessionId: string, signal: AbortSignal): Promise<RunView>;
