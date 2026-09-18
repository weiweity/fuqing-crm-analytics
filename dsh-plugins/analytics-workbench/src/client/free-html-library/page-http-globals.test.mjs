import test from 'node:test';
import assert from 'node:assert/strict';
import { pageDocumentsHttpOptions, pageResultHttpOptions, refuseLivePort } from './page-http.mjs';

/**
 * The production browser bundle reads PAGE_* config only through the
 * globalThis fallback (build.mjs blanks process.env.PAGE_*). dsh-dev's
 * analytics-dev-page-globals overlay row is what sets those globals via
 * `webserver/index-inject`; these tests pin the exact read side of that
 * contract, including the refused live port and the unconfigured failure.
 */
test('host-injected globals configure the browser page http options', () => {
  const globals = ['__PAGE_DOCUMENTS_HTTP_BASE__', '__PAGE_DOCUMENTS_HTTP_TOKEN__'];
  const prior = Object.fromEntries([
    ...globals, '__PAGE_RESULT_HTTP_BASE__', '__PAGE_RESULT_HTTP_TOKEN__',
  ].map(key => [key, globalThis[key]]));
  try {
    globalThis.__PAGE_DOCUMENTS_HTTP_BASE__ = 'http://127.0.0.1:18091';
    globalThis.__PAGE_DOCUMENTS_HTTP_TOKEN__ = 'host-injected-page-documents-tok';
    const documents = pageDocumentsHttpOptions();
    assert.equal(documents.base, 'http://127.0.0.1:18091');
    assert.equal(documents.token, 'host-injected-page-documents-tok');
    assert.equal(typeof documents.fetchImpl, 'function');
    const result = pageResultHttpOptions();
    assert.equal(result.base, 'http://127.0.0.1:18091');
    assert.equal(result.token, 'host-injected-page-documents-tok');
  } finally {
    for (const [key, value] of Object.entries(prior)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  }
});

test('an unconfigured browser store stays null and a 6677 base refuses', () => {
  const globals = ['__PAGE_DOCUMENTS_HTTP_BASE__', '__PAGE_DOCUMENTS_HTTP_TOKEN__',
    '__PAGE_RESULT_HTTP_BASE__', '__PAGE_RESULT_HTTP_TOKEN__'];
  const prior = Object.fromEntries(globals.map(key => [key, globalThis[key]]));
  try {
    for (const key of globals) delete globalThis[key];
    assert.equal(pageDocumentsHttpOptions(), null);
    assert.equal(pageResultHttpOptions(), null);
    assert.throws(() => refuseLivePort('http://127.0.0.1:6677/api/v1/analytics/page-documents/pages'),
      error => error.code === 'REFUSED_LIVE_PORT');
  } finally {
    for (const [key, value] of Object.entries(prior)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  }
});
