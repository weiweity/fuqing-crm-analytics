/** Runtime gate for the shine-waterfall Cordis pack. Node tests default on. */
import { funnelPackEnabled } from './funnel-pack.mjs';

export function waterfallPackEnabled() {
  const env = typeof process !== 'undefined' ? process.env?.SHINE_WATERFALL : undefined;
  if (typeof env === 'string' && env.length) return env !== 'off';
  const flag = typeof globalThis !== 'undefined' ? globalThis.__SHINE_WATERFALL__ : undefined;
  if (flag === true) return true;
  if (flag === false) return false;
  return typeof window === 'undefined';
}

export function catalogKinds(kinds) {
  return kinds.filter(kind => (kind !== 'WATERFALL' || waterfallPackEnabled())
    && (kind !== 'FUNNEL' || funnelPackEnabled()));
}
