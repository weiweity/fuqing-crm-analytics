/** Shared HTTP options for A6/A7. Never targets 4327/8000/5173. */

export const COMPETITION_API_PREFIX = '/api/v1/analytics/competition';
export const FORBIDDEN_HTTP_PORTS = Object.freeze([4327, 8000, 5173]);

function readCompetitionEnv() {
  // Static process.env.NAME so the client bundle can inline COMPETITION_HTTP_* at build.
  const fromProcessBase = process.env.COMPETITION_HTTP_BASE;
  const fromProcessToken = process.env.COMPETITION_HTTP_TOKEN;
  const g = typeof globalThis !== 'undefined' ? globalThis : {};
  const base = String(
    fromProcessBase || g.COMPETITION_HTTP_BASE || g.__COMPETITION_HTTP_BASE__ || '',
  ).replace(/\/$/, '');
  const token = String(
    fromProcessToken || g.COMPETITION_HTTP_TOKEN || g.__COMPETITION_HTTP_TOKEN__ || '',
  );
  return { base, token };
}

export function assertCompetitionHttpBase(base) {
  if (/:(4327|8000|5173)(\/|$)/.test(String(base))) {
    throw new Error('competition HTTP must not target user demo ports 4327/8000/5173');
  }
  return base;
}

export function competitionHttpOptions() {
  const { base, token } = readCompetitionEnv();
  if (!base || !token) return null;
  assertCompetitionHttpBase(base);
  return {
    fetchImpl: (path, init = {}) => {
      const headers = { ...(init.headers || {}), authorization: `Bearer ${token}` };
      const url = String(path).startsWith('http') ? path : `${base}${path}`;
      return fetch(url, { ...init, headers });
    },
    basePath: COMPETITION_API_PREFIX,
  };
}
