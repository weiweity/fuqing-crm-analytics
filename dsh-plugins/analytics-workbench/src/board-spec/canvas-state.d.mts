import type { InterpretedBlock } from './interpret.d.mts';

export type CanvasState = {
  spec: { board_id: string; version: number; blocks: object[] };
  facts: object | null;
  tab: 'board' | 'links' | 'browser';
  selected_block_id: string | null;
  ask: string;
  pending_patch: object | null;
  history: object[];
};
export type CanvasResult = { ok: true; value: CanvasState } | { ok: false; error: { code: string; message: string } };
export function createCanvasState(spec: unknown, facts?: object | null): CanvasResult;
export function setTab(state: CanvasState, tab: string): CanvasResult;
export function selectBlock(state: CanvasState, blockId: string): CanvasResult;
export function setAsk(state: CanvasState, ask: string): CanvasResult;
export function stageTitlePatch(state: CanvasState): CanvasResult;
export function cancelPatch(state: CanvasState): CanvasResult;
export function confirmPatch(state: CanvasState): CanvasResult;
export function rollbackTo(state: CanvasState, version: number): CanvasResult;
export function visibleBlocks(state: CanvasState): InterpretedBlock[];
