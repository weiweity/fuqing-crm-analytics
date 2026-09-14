import test from 'node:test';
import assert from 'node:assert/strict';
import { executeBoardTool, BOARD_TOOL_PARAMETERS } from './board-tools.mjs';
import { BOARD_CATALOG_TOOL_NAME as CATALOG, BOARD_GENERATE_TOOL_NAME as GENERATE,
  BOARD_EDIT_CONTEXT_TOOL_NAME as CONTEXT, BOARD_EDIT_TOOL_NAME as EDIT } from './family.mjs';
import { COMPONENT_CATALOG } from '../board-spec/component-catalog.mjs';
import { libraryPreview, librarySnapshot } from '../../test/helpers/library-board-fixtures.mjs';

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
  assert.equal((await executeBoardTool(GENERATE, {}, exec)).error.code, 'INVALID_RESPONSE');
  reply = { status: 'PENDING', operation: 'GENERATE', preview_id: 'preview_1', snapshot: { spec: { session_id: 'native_session' } } };
  assert.equal((await executeBoardTool(GENERATE, {}, exec)).error.code, 'INVALID_RESPONSE');
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
