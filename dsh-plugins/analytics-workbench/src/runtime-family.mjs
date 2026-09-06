/** Trusted static family and registered session list. Not a plugin registry. */
export const QUERY_FAMILY = 'channel_followup';
const sessionId = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);

export function runtimeFamily() {
  return process.env.B0_RUNTIME_FAMILY === QUERY_FAMILY ? QUERY_FAMILY : 'b0';
}

export function registeredSessionIds() {
  if (runtimeFamily() === QUERY_FAMILY) {
    const list = (process.env.B0_SESSION_IDS ?? '').split(',').filter(Boolean);
    if (list.length !== 2 || new Set(list).size !== 2 || !list.every(sessionId)) {
      throw new Error('query-mode requires exactly two registered sessions');
    }
    return list;
  }
  const id = process.env.B0_SESSION_ID;
  if (!sessionId(id)) throw new Error('B0 bridge requires explicit isolated capabilities');
  return [id];
}

export function isRegisteredSession(id) {
  return registeredSessionIds().includes(id);
}
