/** Isolated page-documents / result-access HTTP. Refuses live 6677. */

export const PAGE_DOCUMENTS_PREFIX = '/api/v1/analytics/page-documents';
export const PAGE_RESULT_PREFIX = '/api/v1/analytics/page-result-access';

function readEnv(prefix) {
  const env = typeof process !== 'undefined' && process.env ? process.env : {};
  const g = typeof globalThis !== 'undefined' ? globalThis : {};
  const base = String(
    env[`${prefix}_HTTP_BASE`] || g[`${prefix}_HTTP_BASE`] || g[`__${prefix}_HTTP_BASE__`] || '',
  ).replace(/\/$/, '');
  const token = String(
    env[`${prefix}_HTTP_TOKEN`] || g[`${prefix}_HTTP_TOKEN`] || g[`__${prefix}_HTTP_TOKEN__`] || '',
  );
  return { base, token };
}

export function refuseLivePort(url) {
  if (String(url).includes(':6677')) {
    const error = new Error('REFUSED_LIVE_PORT');
    error.code = 'REFUSED_LIVE_PORT';
    throw error;
  }
  return url;
}

function optionsFrom(prefix, fallback) {
  const own = readEnv(prefix);
  const base = own.base || fallback?.base || '';
  const token = own.token || fallback?.token || '';
  if (!base) return null;
  refuseLivePort(base);
  return {
    base,
    token,
    fetchImpl: (url, init = {}) => fetch(url, init),
  };
}

export function pageDocumentsHttpOptions() {
  return optionsFrom('PAGE_DOCUMENTS');
}

export function pageResultHttpOptions() {
  return optionsFrom('PAGE_RESULT', readEnv('PAGE_DOCUMENTS'));
}
