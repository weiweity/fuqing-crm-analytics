import test from 'node:test';
import { createServer } from 'node:net';
import { once } from 'node:events';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { startPageHttp, assertNotLivePort, pageHttpOrigin, writePageHttpState, PAGE_HTTP_DEFAULT_PORT } from './page-http.mjs';
import { isolatedEnv, parseServeArgs } from './serve.mjs';
import { pageGlobalRows } from './page-globals.mjs';

test('launcher boots the isolated python server and the full page chain answers', { timeout: 30000 }, async () => {
  const stateDir = await mkdtemp(join(tmpdir(), 'lane-h-launcher-'));
  let service;
  try {
    const reservation = createServer(); reservation.listen(0, '127.0.0.1'); await once(reservation, 'listening');
    const port = reservation.address().port; await new Promise(resolve => reservation.close(resolve));
    service = await startPageHttp({ port, stateDir });
    assert.equal(service.base, `http://127.0.0.1:${port}`);
    const headers = { authorization: `Bearer ${service.token}`, 'content-type': 'application/json' };
    const unauth = await fetch(`${service.base}/api/v1/analytics/page-documents/pages`);
    assert.equal(unauth.status, 401);
    const pages = await fetch(`${service.base}/api/v1/analytics/page-documents/pages`, { headers });
    assert.equal(pages.status, 200);
    assert.deepEqual((await pages.json()).items, []);
    const generated = await fetch(`${service.base}/api/v1/analytics/page-documents/previews`, {
      method: 'POST', headers,
      body: JSON.stringify({
        title: 'launcher', session_id: 'native_session_fixture',
        package: { html: '<html><body><p id="n_one">一</p></body></html>', css: '', js: '', resources: [], node_map: [] },
        binding_manifest: { bindings: [], result_refs: [] },
      }),
    });
    const generatedBody = await generated.json();
    assert.equal(generated.status, 201);
    const previewId = generatedBody.preview_id;
    const confirmed = await fetch(`${service.base}/api/v1/analytics/page-documents/previews/${previewId}/confirm`, {
      method: 'POST', headers: { ...headers, 'idempotency-key': 'lane-h-launcher-1' },
    });
    assert.equal(confirmed.status, 200);
    const snapshot = await confirmed.json();
    const pageId = snapshot.spec.page_id;
    assert.equal(snapshot.spec.version, 1);
    const saved = await fetch(`${service.base}/api/v1/analytics/page-documents/pages/${pageId}/save-preview`, {
      method: 'POST', headers,
      body: JSON.stringify({
        base_version: 1, title: 'launcher saved',
        package: { html: '<html><body><p id="n_one">二</p></body></html>', css: '', js: '', resources: [], node_map: [] },
        binding_manifest: { bindings: [], result_refs: [] },
      }),
    });
    assert.equal(saved.status, 201);
    const savePreviewId = (await saved.json()).preview_id;
    const saveConfirmed = await fetch(`${service.base}/api/v1/analytics/page-documents/previews/${savePreviewId}/confirm`, {
      method: 'POST', headers: { ...headers, 'idempotency-key': 'lane-h-launcher-2' },
    });
    assert.equal(saveConfirmed.status, 200);
    assert.equal((await saveConfirmed.json()).spec.version, 2);
    const result = await fetch(`${service.base}/api/v1/analytics/page-result-access/binding-state`, {
      method: 'POST', headers, body: JSON.stringify({ manifest: { bindings: [], result_refs: [] } }),
    });
    assert.equal(result.status, 200);
    assert.equal((await result.json()).binding_state, 'UNBOUND_SAMPLE');
  } finally {
    await service?.stop();
    await rm(stateDir, { recursive: true, force: true });
  }
});

test('launcher refuses the live web port before spawning anything', async () => {
  await assert.rejects(() => startPageHttp({ port: 6677, stateDir: '/tmp/lane-h-never' }),
    /6677 is the live web/);
  assert.throws(() => assertNotLivePort('http://127.0.0.1:6677'), error => error.code === 'REFUSED_LIVE_PORT');
  assert.equal(assertNotLivePort(`http://127.0.0.1:${PAGE_HTTP_DEFAULT_PORT}`),
    `http://127.0.0.1:${PAGE_HTTP_DEFAULT_PORT}`);
  assert.equal(pageHttpOrigin(18091), 'http://127.0.0.1:18091');
});

test('isolatedEnv forwards PAGE_* only when configured and never a 6677 base', () => {
  const additions = {
    PAGE_DOCUMENTS_HTTP_BASE: 'http://127.0.0.1:18091',
    PAGE_DOCUMENTS_HTTP_TOKEN: 'forwarded-isolated-page-token-32ch',
    PAGE_RESULT_HTTP_BASE: 'http://127.0.0.1:18091',
    PAGE_RESULT_HTTP_TOKEN: 'forwarded-result-page-token-32ch',
  };
  const prior = Object.fromEntries(Object.keys(additions).map(key => [key, process.env[key]]));
  try {
    const before = isolatedEnv('/tmp/runtime', '/tmp/runtime/harness');
    assert.equal(before.PAGE_DOCUMENTS_HTTP_BASE, undefined);
    Object.assign(process.env, additions);
    const forwarded = isolatedEnv('/tmp/runtime', '/tmp/runtime/harness');
    assert.equal(forwarded.PAGE_DOCUMENTS_HTTP_BASE, 'http://127.0.0.1:18091');
    assert.equal(forwarded.PAGE_DOCUMENTS_HTTP_TOKEN, 'forwarded-isolated-page-token-32ch');
    assert.equal(forwarded.PAGE_RESULT_HTTP_BASE, 'http://127.0.0.1:18091');
    assert.equal(forwarded.PAGE_RESULT_HTTP_TOKEN, 'forwarded-result-page-token-32ch');
    process.env.PAGE_DOCUMENTS_HTTP_BASE = 'http://127.0.0.1:6677';
    assert.throws(() => isolatedEnv('/tmp/runtime', '/tmp/runtime/harness'), /must not target the live web port 6677/);
    process.env.PAGE_DOCUMENTS_HTTP_BASE = 'http://127.0.0.1:18091';
    delete process.env.PAGE_DOCUMENTS_HTTP_TOKEN;
    assert.throws(() => isolatedEnv('/tmp/runtime', '/tmp/runtime/harness'), /at least 32 chars/);
  } finally {
    for (const [key, value] of Object.entries(prior)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});

test('page globals rows mirror the env and refuse 6677; absent env injects nothing', () => {
  const additions = {
    PAGE_DOCUMENTS_HTTP_BASE: 'http://127.0.0.1:18091',
    PAGE_DOCUMENTS_HTTP_TOKEN: 'globals-page-documents-token-32ch',
  };
  const prior = Object.fromEntries(Object.keys(additions).map(key => [key, process.env[key]]));
  try {
    assert.deepEqual(pageGlobalRows({}), []);
    Object.assign(process.env, additions);
    const rows = pageGlobalRows();
    assert.deepEqual(rows.map(row => row.kind), ['global', 'global', 'global', 'global']);
    assert.deepEqual(rows.map(row => row.name), [
      '__PAGE_DOCUMENTS_HTTP_BASE__', '__PAGE_DOCUMENTS_HTTP_TOKEN__',
      '__PAGE_RESULT_HTTP_BASE__', '__PAGE_RESULT_HTTP_TOKEN__',
    ]);
    assert.equal(rows[0].value, 'http://127.0.0.1:18091');
    assert.equal(rows[2].value, 'http://127.0.0.1:18091'); // result falls back to documents base
    assert.equal(rows[3].value, 'globals-page-documents-token-32ch');
    process.env.PAGE_DOCUMENTS_HTTP_BASE = 'http://127.0.0.1:6677';
    assert.throws(() => pageGlobalRows(), error => error.code === 'REFUSED_LIVE_PORT');
    process.env.PAGE_DOCUMENTS_HTTP_BASE = 'http://127.0.0.1:18091';
    delete process.env.PAGE_DOCUMENTS_HTTP_TOKEN;
    assert.throws(() => pageGlobalRows(), /at least 32 chars/);
  } finally {
    for (const [key, value] of Object.entries(prior)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});

test('page globals respect an explicit result base override', () => {
  const rows = pageGlobalRows({
    PAGE_DOCUMENTS_HTTP_BASE: 'http://127.0.0.1:18091',
    PAGE_DOCUMENTS_HTTP_TOKEN: 'globals-page-documents-token-32ch',
    PAGE_RESULT_HTTP_BASE: 'http://127.0.0.1:18092',
    PAGE_RESULT_HTTP_TOKEN: 'globals-result-override-token-32',
  });
  assert.equal(rows[2].value, 'http://127.0.0.1:18092');
  assert.equal(rows[3].value, 'globals-result-override-token-32');
});

test('serve args accept page-http flags and reject the live port as a page port', () => {
  const options = parseServeArgs(['--page-http', 'on', '--page-http-port', '18092']);
  assert.equal(options.pageHttp, 'on');
  assert.equal(options.pageHttpPort, 18092);
  assert.equal(parseServeArgs([]).pageHttp, undefined);
  assert.throws(() => parseServeArgs(['--page-http', 'maybe']), /Usage: --page-http/);
  assert.throws(() => parseServeArgs(['--page-http-port', '6677']), /never 6677/);
  assert.throws(() => parseServeArgs(['--page-http-port', '4327']), /1-65535/);
});

test('writePageHttpState records the base without the token next to it', async () => {
  const { readFile } = await import('node:fs/promises');
  const runtime = await mkdtemp(join(tmpdir(), 'lane-h-state-'));
  try {
    await writePageHttpState(runtime, { base: 'http://127.0.0.1:18091', token: 'state-token-not-in-json-32ch' });
    const state = JSON.parse(await readFile(join(runtime, 'page-http-state.json'), 'utf8'));
    assert.deepEqual(state, { base: 'http://127.0.0.1:18091' });
    const tokenFile = await readFile(join(runtime, 'page-http-token'), 'utf8');
    assert.equal(tokenFile, 'state-token-not-in-json-32ch');
  } finally {
    await rm(runtime, { recursive: true, force: true });
  }
});
