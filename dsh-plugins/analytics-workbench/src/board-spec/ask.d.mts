import type { CanvasResult, CanvasState } from './canvas-state.d.mts';
export function titleFromAsk(ask: string): string;
export function kindFromAsk(ask: string): string | null;
export function metricFromAsk(ask: string): string | null;
export function isFactsQuestion(ask: string): boolean;
export function layoutFromAsk(ask: string): { x: number; y: number; w: number; h: number } | null;
export function refreshSelectedFacts(state: CanvasState, items: unknown): CanvasResult | { ok: true; value: CanvasState; refreshed: true };
export function proposeAskLocal(state: CanvasState): CanvasResult;
export function proposeAsk(state: CanvasState, transport?: { fetchImpl: typeof fetch; path?: string }): Promise<CanvasResult>;
