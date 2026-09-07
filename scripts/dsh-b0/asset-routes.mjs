/** Strict same-origin asset HTTP map. Not a generic /api proxy. */

const ANALYSIS_ITEM = /^\/b0\/analyses\/(analysis_[A-Za-z0-9_.:-]{1,118})$/;
const DASHBOARD_ITEM = /^\/b0\/dashboards\/([A-Za-z0-9_.:-]{1,128})$/;
const DASHBOARD_PREVIEW = /^\/b0\/dashboards\/([A-Za-z0-9_.:-]{1,128})\/preview$/;
const DASHBOARD_VERSIONS = /^\/b0\/dashboards\/([A-Za-z0-9_.:-]{1,128})\/versions$/;
const VERSION_QUERY = /^[1-9][0-9]{0,15}$/;

export function mapAssetRoute(method, pathname, searchParams) {
  if (pathname === '/b0/assets') {
    return method === 'GET' && emptySearch(searchParams) ? { kind: 'status' } : { kind: 'reject' };
  }
  if (pathname === '/b0/analyses') {
    if (method === 'GET' && emptySearch(searchParams)) return { kind: 'proxy', kernel: '/api/v1/analytics/analyses', key: false, match: false };
    if (method === 'POST' && emptySearch(searchParams)) return { kind: 'proxy', kernel: '/api/v1/analytics/analyses', key: true, match: false };
    return { kind: 'reject' };
  }
  const analysis = pathname.match(ANALYSIS_ITEM);
  if (analysis) {
    if (method !== 'GET') return { kind: 'reject' };
    const version = searchParams.get('version');
    if (version !== null && !VERSION_QUERY.test(version)) return { kind: 'reject' };
    for (const key of searchParams.keys()) if (key !== 'version') return { kind: 'reject' };
    const suffix = version ? `?version=${version}` : '';
    return { kind: 'proxy', kernel: `/api/v1/analytics/analyses/${analysis[1]}${suffix}`, key: false, match: false };
  }
  if (pathname === '/b0/dashboards') {
    if (method === 'GET' && emptySearch(searchParams)) return { kind: 'proxy', kernel: '/api/v1/analytics/dashboards', key: false, match: false };
    if (method === 'POST' && emptySearch(searchParams)) return { kind: 'proxy', kernel: '/api/v1/analytics/dashboards', key: true, match: false };
    return { kind: 'reject' };
  }
  const preview = pathname.match(DASHBOARD_PREVIEW);
  if (preview) {
    return method === 'POST' && emptySearch(searchParams)
      ? { kind: 'proxy', kernel: `/api/v1/analytics/dashboards/${preview[1]}/preview`, key: false, match: true }
      : { kind: 'reject' };
  }
  const versions = pathname.match(DASHBOARD_VERSIONS);
  if (versions) {
    return method === 'POST' && emptySearch(searchParams)
      ? { kind: 'proxy', kernel: `/api/v1/analytics/dashboards/${versions[1]}/versions`, key: true, match: true }
      : { kind: 'reject' };
  }
  const dashboard = pathname.match(DASHBOARD_ITEM);
  if (dashboard) {
    return method === 'GET' && emptySearch(searchParams)
      ? { kind: 'proxy', kernel: `/api/v1/analytics/dashboards/${dashboard[1]}`, key: false, match: false }
      : { kind: 'reject' };
  }
  return null;
}

function emptySearch(searchParams) {
  return [...searchParams.keys()].length === 0;
}

export function assetHeaderViolation(rawHeaders) {
  const names = [];
  for (let index = 0; index < rawHeaders.length; index += 2) names.push(String(rawHeaders[index]).toLowerCase());
  if (names.includes('authorization')) return 'browser-authorization';
  if (names.includes('x-runtime-session-id')) return 'session-fence';
  const seen = new Set();
  for (const name of names) {
    if ((name === 'idempotency-key' || name === 'if-match') && seen.has(name)) return `duplicate-${name}`;
    seen.add(name);
  }
  return null;
}
