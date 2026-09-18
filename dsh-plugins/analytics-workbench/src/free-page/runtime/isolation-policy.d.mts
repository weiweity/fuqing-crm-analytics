export const FREE_PAGE_SANDBOX: 'allow-scripts';
export const FREE_PAGE_REFERRER_POLICY: 'no-referrer';
export const FREE_PAGE_CSP: string;
export function describeIsolation(evidence?: { cpu_isolation?: string } | null): {
  sandbox: string;
  origin: string;
  permissionIsolation: true;
  parentDomAccess: false;
  hostStorageAccess: false;
  cpuIsolation: string;
  terminateMechanism: string;
  allowScripts: boolean;
  allowSameOrigin: boolean;
};
export function sandboxAllowsScripts(sandbox: string): boolean;
export function sandboxAllowsSameOrigin(sandbox: string): boolean;
