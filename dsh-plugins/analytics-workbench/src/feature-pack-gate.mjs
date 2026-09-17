/** Host/browser gates for shine-query and shine-board. Node tests default on. */
function packEnabled(envName, flagName) {
  const env = typeof process !== 'undefined' ? process.env?.[envName] : undefined;
  if (typeof env === 'string' && env.length) return env !== 'off';
  const flag = typeof globalThis !== 'undefined' ? globalThis[flagName] : undefined;
  if (flag === true) return true;
  if (flag === false) return false;
  return typeof window === 'undefined';
}

export function queryPackEnabled() {
  return packEnabled('SHINE_QUERY', '__SHINE_QUERY__');
}

export function boardPackEnabled() {
  return packEnabled('SHINE_BOARD', '__SHINE_BOARD__');
}
