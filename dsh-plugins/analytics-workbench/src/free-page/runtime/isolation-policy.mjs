/**
 * D2: opaque-origin sandbox iframe (allow-scripts, no allow-same-origin).
 * D23/T0: sandbox attributes are permission isolation, not CPU/process isolation.
 * cpuIsolation is filled from probe evidence; never inferred from this string.
 */

export const FREE_PAGE_SANDBOX = 'allow-scripts';
export const FREE_PAGE_REFERRER_POLICY = 'no-referrer';

export const FREE_PAGE_CSP = [
  "default-src 'none'",
  "base-uri 'none'",
  "object-src 'none'",
  "frame-src 'none'",
  "child-src 'none'",
  "connect-src 'none'",
  "form-action 'none'",
  "script-src 'unsafe-inline' blob:",
  "style-src 'unsafe-inline' blob:",
  "img-src blob: data:",
  "font-src blob: data:",
  "media-src blob: data:",
  "worker-src blob:",
].join('; ');

export function describeIsolation(evidence = null) {
  const cpu = evidence?.cpu_isolation
    ?? 'unverified; sandbox attributes are not a CPU isolation claim';
  return {
    sandbox: FREE_PAGE_SANDBOX,
    origin: 'opaque-unique (srcdoc + sandbox without allow-same-origin)',
    permissionIsolation: true,
    parentDomAccess: false,
    hostStorageAccess: false,
    cpuIsolation: cpu,
    terminateMechanism: 'replace/remove the iframe; ping watchdog only if the page event loop yields',
    allowScripts: true,
    allowSameOrigin: false,
  };
}

export function sandboxAllowsScripts(sandbox) {
  return String(sandbox || '').split(/\s+/).includes('allow-scripts');
}

export function sandboxAllowsSameOrigin(sandbox) {
  return String(sandbox || '').split(/\s+/).includes('allow-same-origin');
}
