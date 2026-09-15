import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { executeBoardTool, BOARD_TOOL_PARAMETERS } from './board-tools.mjs';
import { BOARD_CATALOG_TOOL_NAME as CATALOG, BOARD_GENERATE_TOOL_NAME as GENERATE,
  BOARD_EDIT_CONTEXT_TOOL_NAME as CONTEXT, BOARD_EDIT_TOOL_NAME as EDIT } from './family.mjs';
import { COMPONENT_CATALOG } from '../board-spec/component-catalog.mjs';
import { libraryPreview, librarySnapshot } from '../../test/helpers/library-board-fixtures.mjs';

test('generation identifies TABLE properties before HTTP and preserves the caller draft', async t => {
  const previous = ['COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN'].map(key => [key, process.env[key]]);
  t.after(() => previous.forEach(([key, value]) => { if (value === undefined) delete process.env[key]; else process.env[key] = value; }));
  process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:4318';
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-r1-tool-test';
  const args = { title: 'R-1 属性复现', blocks: [{ block_id: 'table', kind: 'TABLE', title: '明细',
    library_version: COMPONENT_CATALOG.library_version, source_result_id: 'result_test',
    layout: { x: 0, y: 10, w: 12, h: 7 }, props: { page_size: 10, sort_direction: 'asc', show_values: true } }] };
  const before = structuredClone(args);
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return Response.json({ error: {
    code: 'INVALID_REQUEST', message: '请求与当前合同不匹配。',
  } }, { status: 422 }); });
  const result = await executeBoardTool(GENERATE, args, { agent: { session: { id: 'native_session' } } });
  assert.equal(result.status, 'REFUSED');
  assert.equal(result.error.code, 'COMPONENT_PROPERTY');
  assert.match(result.error.message, /blocks\[0\].*TABLE.*show_values/);
  assert.equal(result.error.details.phase, 'preflight');
  assert.equal(calls, 0, 'invalid props must not reach HTTP or be retried');
  assert.deepEqual(args, before, 'do not silently drop unsupported props');
});

test('generation identifies LINE/TABLE overlap and retains FUNNEL when only the layout is corrected', async t => {
  const previous = ['COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN'].map(key => [key, process.env[key]]);
  t.after(() => previous.forEach(([key, value]) => { if (value === undefined) delete process.env[key]; else process.env[key] = value; }));
  process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:4318';
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-r1-tool-test';
  const make = (kind, layout) => ({ block_id: kind.toLowerCase(), kind, title: kind,
    library_version: COMPONENT_CATALOG.library_version, source_result_id: 'result_test', props: {}, layout });
  const args = { title: 'R-1 布局复现', blocks: [
    make('LINE', { x: 6, y: 4, w: 6, h: 7 }),
    make('FUNNEL', { x: 0, y: 10, w: 6, h: 6 }),
    make('TABLE', { x: 6, y: 10, w: 6, h: 6 }),
  ] };
  const original = structuredClone(args), calls = [];
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    const body = JSON.parse(options.body); calls.push(body);
    return Response.json(libraryPreview({ facts_by_result_id: { result_test: {} }, spec: {
      ...librarySnapshot().spec, title: body.title, blocks: body.blocks,
    } }));
  });
  const exec = { agent: { session: { id: 'native_session' } } };
  const refused = await executeBoardTool(GENERATE, args, exec);
  assert.equal(refused.error.code, 'COMPONENT_OVERLAP');
  assert.match(refused.error.message, /blocks\[2\].*blocks\[0\]/);
  assert.equal(calls.length, 0);
  assert.deepEqual(args, original);
  args.blocks[2].layout.y = 11;
  const generated = await executeBoardTool(GENERATE, args, exec);
  assert.equal(generated.status, 'PREVIEW_READY'); assert.equal(generated.published, false);
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], { ...args, session_id: 'native_session' });
  assert.deepEqual(calls[0].blocks[1], original.blocks[1], 'keep FUNNEL and its result binding');
});

test('native board tools use execution session, expose catalogue and preview only, never confirmation', async t => {
  const before = ['COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN'].map(key => [key, process.env[key]]);
  t.after(() => before.forEach(([key, value]) => { if (value === undefined) delete process.env[key]; else process.env[key] = value; }));
  process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:4318'; process.env.COMPETITION_HTTP_TOKEN = 'isolated-tool-test';
  const calls = [], preview = libraryPreview();
  let reply = { schema_version: 'board-generation-context/v1', session_id: 'native_session', catalog: COMPONENT_CATALOG, results: [] };
  t.mock.method(globalThis, 'fetch', async (url, options) => { calls.push({ url, options }); return new Response(JSON.stringify(reply)); });
  const exec = { agent: { session: { id: 'native_session' } } };
  const context = await executeBoardTool(CATALOG, { session_id: 'forged' }, exec);
  assert.equal(context.session_id, 'native_session');
  assert.match(calls[0].url, /session_id=native_session&offset=0$/);
  reply = preview;
  const generated = await executeBoardTool(GENERATE, { title: '自选内容', blocks: preview.snapshot.spec.blocks,
    session_id: 'forged', owner: 'forged', facts_by_result_id: { invented: 100 }, status: 'APPLIED' }, exec);
  assert.equal(generated.status, 'PREVIEW_READY'); assert.equal(generated.published, false);
  assert.deepEqual(JSON.parse(calls[1].options.body), { title: '自选内容', blocks: preview.snapshot.spec.blocks, session_id: 'native_session' });
  assert.equal(calls.length, 2);
  assert.deepEqual(Object.keys(BOARD_TOOL_PARAMETERS), [CATALOG, GENERATE, CONTEXT, EDIT]);
  await assert.rejects(executeBoardTool('competition_board_confirm', {}, exec), /UNREGISTERED_BOARD_TOOL/);
  assert.equal((await executeBoardTool(GENERATE, {}, {})).error.code, 'SESSION_REQUIRED');
  assert.equal((await executeBoardTool(GENERATE, null, exec)).error.code, 'INVALID_REQUEST');
  assert.equal(calls.length, 2);
  reply = libraryPreview(); reply.snapshot.spec.session_id = 'other';
  const validArgs = { title: '有效请求', blocks: preview.snapshot.spec.blocks };
  assert.equal((await executeBoardTool(GENERATE, validArgs, exec)).error.code, 'INVALID_RESPONSE');
  reply = { status: 'PENDING', operation: 'GENERATE', preview_id: 'preview_1', snapshot: { spec: { session_id: 'native_session' } } };
  assert.equal((await executeBoardTool(GENERATE, validArgs, exec)).error.code, 'INVALID_RESPONSE');
  reply = { schema_version: 'board-generation-context/v1', session_id: 'other', catalog: COMPONENT_CATALOG, results: [] };
  assert.equal((await executeBoardTool(CATALOG, {}, exec)).error.code, 'INVALID_RESPONSE');
});

test('native edit tools cannot create a selection or replace its owner/session/target/version', async t => {
  const previous = ['COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN'].map(key => [key, process.env[key]]);
  t.after(() => previous.forEach(([key, value]) => { if (value === undefined) delete process.env[key]; else process.env[key] = value; }));
  process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:4318'; process.env.COMPETITION_HTTP_TOKEN = 'isolated-edit-tool-test';
  const snapshot = librarySnapshot(), eid = 'edit_' + 'a'.repeat(32);
  const context = { schema_version: 'board-edit-context/v1', edit_context_id: eid, board_id: snapshot.spec.board_id,
    base_version: 1, block_id: 'note', session_id: 'native_session', expires_at_ms: Date.now() + 10000,
    status: 'OPEN', preview_id: null, block: snapshot.spec.blocks[0], facts_by_result_id: {} };
  let contextReply = context, previewReply = libraryPreview(librarySnapshot({ version: 2, content: '用户要求的说明' }));
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options }); return Response.json(url.includes('/propose') ? previewReply : contextReply);
  });
  const execution = { agent: { session: { id: 'native_session' } } };
  const read = await executeBoardTool(CONTEXT, { edit_context_id: eid, session_id: 'forged' }, execution);
  assert.equal(read.session_id, 'native_session'); assert.equal(read.catalog, COMPONENT_CATALOG);
  const changes = { props: { content: '用户要求的说明' } };
  const result = await executeBoardTool(EDIT, { edit_context_id: eid, changes,
    session_id: 'forged', owner: 'other', board_id: 'other', block_id: 'other', base_version: 999 }, execution);
  assert.equal(result.status, 'PREVIEW_READY'); assert.equal(result.operation, 'PATCH'); assert.equal(result.block_id, 'note');
  assert.equal(result.published, false); assert.equal(result.edit_context_id, eid);
  assert.deepEqual(JSON.parse(calls.at(-1).options.body), { session_id: 'native_session', changes });
  assert.match(calls[1].url, /session_id=native_session$/);
  const count = calls.length;
  assert.equal((await executeBoardTool(EDIT, { edit_context_id: '../boards', changes }, execution)).error.code, 'SELECTION_REQUIRED');
  for (const name of ['competition_board_select', 'competition_board_confirm', 'competition_board_cancel']) {
    await assert.rejects(executeBoardTool(name, {}, execution), /UNREGISTERED_BOARD_TOOL/);
  }
  assert.equal(calls.length, count);
  contextReply = { ...context, session_id: 'wrong' };
  assert.equal((await executeBoardTool(EDIT, { edit_context_id: eid, changes }, execution)).error.code, 'INVALID_RESPONSE');
  contextReply = { ...context, status: 'PROPOSED', preview_id: 'preview_test' };
  assert.equal((await executeBoardTool(EDIT, { edit_context_id: eid, changes }, execution)).error.code, 'EDIT_PROPOSED');
  contextReply = context;
  previewReply = libraryPreview(librarySnapshot({ boardId: 'wrong', version: 2 }));
  assert.equal((await executeBoardTool(EDIT, { edit_context_id: eid, changes }, execution)).error.code, 'INVALID_RESPONSE');
});

test('catalog saved_boards reach the tool result, missing is unknown, generate stays unpublished', async t => {
  const previous = ['COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN'].map(key => [key, process.env[key]]);
  t.after(() => previous.forEach(([key, value]) => { if (value === undefined) delete process.env[key]; else process.env[key] = value; }));
  const saved = { board_id: 'board_' + 'a'.repeat(32), title: '原板 v2', version: 2,
    facts: { secret: 9 }, spec: { blocks: [{ kind: 'METRIC' }] } };
  let payload = { schema_version: 'board-generation-context/v1', session_id: 'native_session',
    catalog: COMPONENT_CATALOG, results: [], saved_boards: [saved], saved_boards_status: 'complete' };
  const preview = libraryPreview();
  const server = http.createServer((req, res) => {
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify(req.method === 'POST' ? preview : payload));
  });
  t.after(() => new Promise(resolve => server.close(resolve)));
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  process.env.COMPETITION_HTTP_BASE = `http://127.0.0.1:${server.address().port}`;
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-saved-board-tool';
  const exec = { agent: { session: { id: 'native_session' } } };
  const catalog = await executeBoardTool(CATALOG, {}, exec);
  assert.deepEqual(catalog.saved_boards, [{ board_id: saved.board_id, title: saved.title, version: 2 }]);
  assert.equal(catalog.saved_boards_status, 'complete');
  assert.equal(JSON.stringify(catalog.saved_boards).includes('facts'), false);
  const generated = await executeBoardTool(GENERATE, { title: preview.snapshot.spec.title, blocks: preview.snapshot.spec.blocks }, exec);
  assert.equal(generated.status, 'PREVIEW_READY');
  assert.equal(generated.published, false);
  assert.notEqual(generated.board_id, saved.board_id);
  payload = { schema_version: 'board-generation-context/v1', session_id: 'native_session', catalog: COMPONENT_CATALOG, results: [] };
  const legacy = await executeBoardTool(CATALOG, {}, exec);
  assert.equal(Object.hasOwn(legacy, 'saved_boards'), false);
  assert.equal(Object.hasOwn(legacy, 'saved_boards_status'), false);
  payload = { ...payload, saved_boards: { board_id: saved.board_id } };
  assert.equal((await executeBoardTool(CATALOG, {}, exec)).error.code, 'INVALID_RESPONSE');
  payload = { schema_version: 'board-generation-context/v1', session_id: 'native_session', catalog: COMPONENT_CATALOG, results: [],
    saved_boards_status: 'complete' };
  const lying = await executeBoardTool(CATALOG, {}, exec);
  assert.equal(Object.hasOwn(lying, 'saved_boards'), false);
  assert.equal(lying.saved_boards_status, 'unknown');
  assert.deepEqual(Object.keys(BOARD_TOOL_PARAMETERS), [CATALOG, GENERATE, CONTEXT, EDIT]);
});

test('catalog saved board titles follow the unicode code-point Title contract', async t => {
  const previous = ['COMPETITION_HTTP_BASE', 'COMPETITION_HTTP_TOKEN'].map(key => [key, process.env[key]]);
  t.after(() => previous.forEach(([key, value]) => { if (value === undefined) delete process.env[key]; else process.env[key] = value; }));
  process.env.COMPETITION_HTTP_BASE = 'http://127.0.0.1:4318';
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-title-contract';
  let payload;
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(payload)));
  const exec = { agent: { session: { id: 'native_session' } } };
  const catalogOf = async title => {
    payload = { schema_version: 'board-generation-context/v1', session_id: 'native_session',
      catalog: COMPONENT_CATALOG, results: [], saved_boards_status: 'complete',
      saved_boards: [{ board_id: 'board_' + 'a'.repeat(32), title, version: 1 }] };
    return executeBoardTool(CATALOG, {}, exec);
  };
  const nonBmp = '\u{20BB7}'.repeat(81);
  const accepted = await catalogOf(nonBmp);
  assert.equal(accepted.saved_boards_status, 'complete');
  assert.equal(accepted.saved_boards[0].title, nonBmp);
  assert.equal(accepted.saved_boards[0].title.length, 162);
  assert.equal(Array.from(accepted.saved_boards[0].title).length, 81);
  const emoji = await catalogOf('😀'.repeat(160));
  assert.equal(emoji.saved_boards[0].title, '😀'.repeat(160));
  assert.equal((await catalogOf('a'.repeat(159))).saved_boards[0].title.length, 159);
  assert.equal((await catalogOf('a'.repeat(160))).saved_boards[0].title.length, 160);
  assert.equal((await catalogOf(' a')).saved_boards[0].title, ' a');
  assert.equal((await catalogOf('\u{20BB7}'.repeat(160))).error, undefined);
  assert.equal((await catalogOf('\u{20BB7}'.repeat(160))).saved_boards[0].title.length, 320);
  assert.equal((await catalogOf('a'.repeat(161))).error.code, 'INVALID_RESPONSE');
  assert.equal((await catalogOf('\u{20BB7}'.repeat(161))).error.code, 'INVALID_RESPONSE');
  assert.equal((await catalogOf('')).error.code, 'INVALID_RESPONSE');
  assert.equal((await catalogOf('   ')).error.code, 'INVALID_RESPONSE');
  assert.equal((await catalogOf('\n')).error.code, 'INVALID_RESPONSE');
  payload = { schema_version: 'board-generation-context/v1', session_id: 'native_session',
    catalog: COMPONENT_CATALOG, results: [], saved_boards_status: 'complete',
    saved_boards: [{ board_id: 'board_' + 'a'.repeat(32), title: 12, version: 1 }] };
  assert.equal((await executeBoardTool(CATALOG, {}, exec)).error.code, 'INVALID_RESPONSE');
  assert.deepEqual(Object.keys(BOARD_TOOL_PARAMETERS), [CATALOG, GENERATE, CONTEXT, EDIT]);
});
