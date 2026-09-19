import test from 'node:test';
import assert from 'node:assert/strict';
import { boardServerRequest, BOARD_HTTP_PREFIX } from './server-http.mjs';
import { handleBoardBrowserCall } from './browser-api.mjs';
import { createLibraryBoardClient } from '../client/library-board-client.mjs';
import { librarySnapshot, libraryPreview } from '../../test/helpers/library-board-fixtures.mjs';

function transport(t, responder = () => new Response('{}')) {
  const calls = [];
  const base = process.env.COMPETITION_HTTP_BASE, token = process.env.COMPETITION_HTTP_TOKEN;
  process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:4318';
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-test-token-not-a-real-credential';
  t.after(() => { for (const [key, value] of [['COMPETITION_HTTP_BASE', base], ['COMPETITION_HTTP_TOKEN', token]]) {
    if (value === undefined) delete process.env[key]; else process.env[key] = value;
  } });
  t.mock.method(globalThis, 'fetch', async (url, options) => { calls.push({ url, options }); return responder(url, options); });
  return calls;
}

test('props-only client edits pass the actual RPC allowlist with their current kind', async t => {
  const saved = librarySnapshot(), pending = libraryPreview(librarySnapshot({ version: 2, content: '新内容' }));
  const context = { schema_version: 'board-edit-context/v1', edit_context_id: 'edit_' + 'a'.repeat(32),
    board_id: saved.spec.board_id, base_version: 1, block_id: 'note', session_id: saved.spec.session_id,
    status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000, block: saved.spec.blocks[0], facts_by_result_id: {} };
  const calls = transport(t, (url, options) => {
    if (url.endsWith('/edit-context')) return Response.json(options.method === 'POST' ? context : { context: null });
    if (url.endsWith('/patch-preview')) return Response.json(pending);
    return Response.json(saved);
  });
  const client = createLibraryBoardClient((_channel, operation, payload, signal) => handleBoardBrowserCall(operation, payload, signal));
  t.after(() => client.dispose());
  await client.openBoard(saved.spec.board_id); await client.selectComponent('note');
  await client.previewBlockPatch({ props: { content: '新内容' } });
  assert.equal(client.getSnapshot().preview?.operation, 'PATCH');
  assert.deepEqual(JSON.parse(calls.at(-1).options.body).changes, { kind: 'TEXT', props: { content: '新内容' } });
  assert.equal(client.getSnapshot().saved.spec.version, 1, 'preview does not save');
});

test('UI bridge forwards only explicit board operations and stable confirmation keys', async t => {
  const calls = transport(t);
  const cases = [
    ['list', {}, '/boards?limit=100&offset=0', 'GET'],
    ['get', { board_id: 'board_1', version: 3 }, '/boards/board_1?version=3', 'GET'],
    ['history', { board_id: 'board_1', offset: 100 }, '/boards/board_1/versions?limit=100&offset=100', 'GET'],
    ['preview', { preview_id: 'preview_1' }, '/previews/preview_1', 'GET'],
    ['cancel', { preview_id: 'preview_1' }, '/previews/preview_1/cancel', 'POST'],
    ['confirm', { preview_id: 'preview_1', key: 'once:preview_1' }, '/previews/preview_1/confirm', 'POST'],
    ['rollback_preview', { board_id: 'board_1', base_version: 3, to_version: 1 }, '/boards/board_1/rollback-preview', 'POST'],
    ['layout_preview', { board_id: 'board_1', base_version: 3, layouts: [] }, '/boards/board_1/layout-preview', 'POST'],
    ['select_edit', { board_id: 'board_1', base_version: 3, block_id: 'block:1' }, '/boards/board_1/edit-context', 'POST'],
    ['cancel_edit', { edit_context_id: 'edit_1' }, '/edit-contexts/edit_1/cancel', 'POST'],
    ['patch_preview', { board_id: 'board_1', base_version: 3, block_id: 'note', changes: { title: '新标题' } },
      '/boards/board_1/patch-preview', 'POST'],
  ];
  for (const [operation, payload, path, method] of cases) {
    assert.equal((await handleBoardBrowserCall(operation, payload)).ok, true);
    assert.equal(calls.at(-1).url, `http://127.0.0.1:4318${BOARD_HTTP_PREFIX}${path}`);
    assert.equal(calls.at(-1).options.method, method);
    assert.equal(calls.at(-1).options.redirect, 'error');
  }
  assert.equal(calls[5].options.headers['idempotency-key'], 'once:preview_1');
  assert.deepEqual(JSON.parse(calls[6].options.body), { base_version: 3, to_version: 1 });
  assert.deepEqual(JSON.parse(calls.at(-1).options.body), {
    base_version: 3, block_id: 'note', changes: { title: '新标题' },
  });
  const status = await handleBoardBrowserCall('status', {});
  assert.deepEqual(status.value, { protocol: 'board-browser/v1', configured: true });
  assert.equal(calls.length, cases.length);
});

test('no pending edit is an explicit nullable context envelope, not a missing or malformed HTTP response', async t => {
  let response = { context: null };
  const calls = transport(t, () => Response.json(response));
  assert.deepEqual(await handleBoardBrowserCall('current_edit', { board_id: 'board_1' }), { ok: true, value: null });
  assert.match(calls[0].url, /\/boards\/board_1\/edit-context$/);
  response = {};
  assert.equal((await handleBoardBrowserCall('current_edit', { board_id: 'board_1' })).error.code, 'INVALID_RESPONSE');
  response = { context: { edit_context_id: 'edit_1' } };
  assert.deepEqual((await handleBoardBrowserCall('current_edit', { board_id: 'board_1' })).value, response.context);
});

test('UI bridge rejects arbitrary HTTP, model generation, forged ownership and invalid identifiers without fetch', async t => {
  const calls = transport(t);
  for (const [operation, payload] of [
    ['generate', {}], ['sql', {}], ['http', { path: '/settings' }],
    ['list', { owner: 'someone' }], ['list', { limit: 101 }], ['list', { offset: -1 }],
    ['get', { board_id: '../settings' }], ['get', { board_id: 'board_1', version: true }],
    ['get', { board_id: '%2e%2e' }], ['confirm', { preview_id: 'preview_1', key: '' }],
    ['confirm', { preview_id: 'preview_1', key: 'key', session_id: 'forged' }],
    ['rollback_preview', { board_id: 'board_1', base_version: 1, to_version: 0 }], ['list', null],
    ['select_edit', { board_id: 'board_1', base_version: 1, block_id: 'note', session_id: 'forged' }],
    ['select_edit', { board_id: 'board_1', base_version: 1, block_id: 'note', changes: { title: 'forged' } }],
    ['propose_edit', { edit_context_id: 'edit_1', changes: {} }],
    ['patch_preview', { board_id: 'board_1', base_version: 1, block_id: 'note', changes: { title: 'x' }, session_id: 'forged' }],
    ['patch_preview', { board_id: 'board_1', base_version: 1, block_id: 'note', changes: { layout: { x: 0, y: 0, w: 1, h: 1 } } }],
    ['patch_preview', { board_id: 'board_1', base_version: 1, block_id: 'note', changes: { title: null } }],
    ['patch_preview', { board_id: 'board_1', base_version: 1, block_id: 'note', changes: { unknown: 1 } }],
    ['patch_preview', { board_id: 'board_1', base_version: 1, block_id: 'm1', changes: { kind: 'METRIC', props: { metric_ref: 'retail_gsv' } } }],
  ]) assert.equal((await handleBoardBrowserCall(operation, payload)).error.code, 'INVALID_REQUEST');
  assert.deepEqual(calls, []);
});

test('host transport refuses traversal and non-isolated destinations before credentials leave host', async t => {
  const calls = transport(t);
  for (const path of ['/../../settings', '/%2e%2e/settings', '//other/boards', '/boards\\x', '/boards#x', '/boards\nx', null]) {
    assert.equal((await boardServerRequest(path)).error.code, 'INVALID_REQUEST');
  }
  for (const origin of ['https://public.example', 'http://127.0.0.1:4327', 'http://localhost:4318', 'http://127.0.0.1:4318/path', 'http://user:pass@127.0.0.1:4318']) {
    process.env.COMPETITION_HTTP_BASE = origin;
    assert.equal((await boardServerRequest('/boards')).error.code, 'NOT_CONNECTED');
  }
  assert.deepEqual(calls, []);
});

test('bounded transport reports malformed/oversize/failure without retry, preserves cancellation', async t => {
  let response = () => new Response('bad JSON');
  const calls = transport(t, () => response());
  assert.equal((await boardServerRequest('/boards')).ok, false);
  response = () => new Response(' '.repeat(2_200_001));
  assert.equal((await boardServerRequest('/boards')).ok, false);
  response = () => new Response(new Uint8Array([0xff, 0xfe]));
  assert.equal((await boardServerRequest('/boards')).ok, false);
  response = () => { throw new Error('sensitive implementation diagnostic'); };
  const lost = await boardServerRequest('/previews/preview_1/confirm', { method: 'POST', key: 'one' });
  assert.equal(lost.error.code, 'TRANSPORT_ERROR');
  assert.doesNotMatch(JSON.stringify(lost), /sensitive implementation/);
  assert.equal(calls.length, 4);
  const abort = new AbortController(); abort.abort(new Error('cancelled'));
  await assert.rejects(boardServerRequest('/boards', { signal: abort.signal }), /cancelled/);
  assert.equal(calls.length, 4);
  response = () => new Response(JSON.stringify({ error: { code: 'VERSION_CONFLICT', message: '版本冲突' } }), { status: 409 });
  assert.deepEqual((await boardServerRequest('/boards')).error, { code: 'VERSION_CONFLICT', message: '版本冲突', details: { status: 409 } });
});
