/** Host-owned page HTTP configuration bridge. Adds no business routes.

 When the supervisor starts the isolated page-documents/result-access HTTP,
 it exports PAGE_DOCUMENTS_HTTP_BASE / PAGE_DOCUMENTS_HTTP_TOKEN and the
 PAGE_RESULT_* pair into the 6677 host process env. This row renders those
 values into index.html as `globalThis` rows, which is the only supported
 channel for the browser bundle (`page-http.mjs` falls back to
 `globalThis.__PAGE_*__`; build-time `process.env` is deliberately blanked).
 Without the env the row pushes nothing and the client keeps failing with
 `http_not_configured` — it never defaults to 6677.
 */
import assert from 'node:assert/strict';
import { PAGE_HTTP_DEFAULT_PORT, assertNotLivePort } from './page-http.mjs';

export const name = 'analytics-dev-page-globals';
export const inject = [];

function readPageEnv(env = process.env) {
  const base = String(env.PAGE_DOCUMENTS_HTTP_BASE ?? '').replace(/\/$/, '');
  const token = String(env.PAGE_DOCUMENTS_HTTP_TOKEN ?? '');
  if (!base) return null;
  assert.ok(token.length >= 32, 'PAGE_DOCUMENTS_HTTP_TOKEN must be at least 32 chars when a base is set');
  assertNotLivePort(base);
  const resultBase = String(env.PAGE_RESULT_HTTP_BASE ?? '').replace(/\/$/, '') || base;
  assertNotLivePort(resultBase);
  const resultToken = String(env.PAGE_RESULT_HTTP_TOKEN ?? '') || token;
  return {
    __PAGE_DOCUMENTS_HTTP_BASE__: base,
    __PAGE_DOCUMENTS_HTTP_TOKEN__: token,
    __PAGE_RESULT_HTTP_BASE__: resultBase,
    __PAGE_RESULT_HTTP_TOKEN__: resultToken,
  };
}

export function pageGlobalRows(env = process.env) {
  const values = readPageEnv(env);
  if (!values) return [];
  return Object.entries(values).map(([nameKey, value]) => ({ kind: 'global', name: nameKey, value }));
}

export async function apply(ctx) {
  const rows = pageGlobalRows();
  if (!rows.length) return;
  assert.ok(ctx?.on, 'page-globals row requires a cordis context');
  ctx.on('webserver/index-inject', table => { table.push(...rows); });
  console.log(`analytics-dev-page-globals: page HTTP bridge -> ${rows[0].value} (not 6677; default ${PAGE_HTTP_DEFAULT_PORT})`);
}
