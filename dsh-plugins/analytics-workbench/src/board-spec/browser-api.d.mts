import type { BoardHttpResult } from './server-http.mjs';
export const BOARD_RPC_CHANNEL: string;
export function handleBoardBrowserCall(operation: string, payload: unknown, signal?: AbortSignal): Promise<BoardHttpResult>;
