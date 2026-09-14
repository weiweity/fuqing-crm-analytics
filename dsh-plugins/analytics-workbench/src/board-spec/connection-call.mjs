/** Logical board operations carried by the native authenticated shared API. */
export const BOARD_API_ENDPOINT = 'shine-mage-board';
export function callBoardConnection(rpc, channel, operation, payload, signal) {
  if (channel !== '/shine-mage-board') throw new Error('Unexpected board channel');
  return rpc.call('/api', BOARD_API_ENDPOINT, { operation, payload }, signal);
}
