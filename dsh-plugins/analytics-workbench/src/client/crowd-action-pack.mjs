/** Runtime gate for the shine-crowd-action Cordis pack. Node tests default on. */
export function crowdActionPackEnabled() {
  const env = typeof process !== 'undefined' ? process.env?.SHINE_CROWD_ACTION : undefined;
  if (typeof env === 'string' && env.length) return env !== 'off';
  const flag = typeof globalThis !== 'undefined' ? globalThis.__SHINE_CROWD_ACTION__ : undefined;
  if (flag === true) return true;
  if (flag === false) return false;
  return typeof window === 'undefined';
}
