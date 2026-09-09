import type { BoardLayoutMode, CompetitionBoardBatchRequest, EndorsedResultRef, Principal } from './types.ts';
export type BatchIntent = { fingerprint: string; payload: CompetitionBoardBatchRequest };
export function batchIntent(principal: Principal, layoutMode: BoardLayoutMode, refs: EndorsedResultRef[], prior?: BatchIntent | null): BatchIntent;
export function finishBatchIntent(principal: Principal, intent: BatchIntent | null): void;
