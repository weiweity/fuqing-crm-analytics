export const BOARD_API_ENDPOINT: 'shine-mage-board';
export function callBoardConnection(rpc: { call(channel: string, operation: string, payload: unknown, signal?: AbortSignal): Promise<any> }, channel: string, operation: string, payload: unknown, signal?: AbortSignal): Promise<any>;
