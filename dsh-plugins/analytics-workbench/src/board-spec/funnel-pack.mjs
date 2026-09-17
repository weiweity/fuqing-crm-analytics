/** Runtime gate for the shine-funnel Cordis pack. Node tests default on. */
export function funnelPackEnabled() {
  const env = typeof process !== 'undefined' ? process.env?.SHINE_FUNNEL : undefined;
  if (typeof env === 'string' && env.length) return env !== 'off';
  const flag = typeof globalThis !== 'undefined' ? globalThis.__SHINE_FUNNEL__ : undefined;
  if (flag === true) return true;
  if (flag === false) return false;
  return typeof window === 'undefined';
}
