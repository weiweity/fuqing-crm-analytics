import test from 'node:test';
import assert from 'node:assert/strict';
import { loadRunView, visibleRunView, emptyRunView } from '../src/run-view.mjs';

const id = 'run_' + 'a'.repeat(32);
const row = { schema_version: 'analytics-run-b0/v1', run_id: id, version: 2, conversation_id: 'conv',
  status: 'RUNNING', phase: 'PLANNING', diagnostics: { tool_steps_used: 0 } };
const context = { session_id: 'session', ready: true, conversation: { schema_version: 'analytics-run-b0/v1',
  conversation_id: 'conv', run_ids: [id] } };

test('refresh only GETs authenticated context and exact run snapshot, never resubmits', async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    return Response.json(url === '/b0/context' ? context : row);
  };
  const value = await loadRunView(fetcher, 'session', new AbortController().signal);
  assert.equal(value.runs[0].status, 'RUNNING');
  assert.equal(value.runs[0].version, 2);
  assert.equal(value.sessionId, 'session');
  assert.deepEqual(calls.map(call => call.url), ['/b0/context', `/b0/runs/${id}`]);
  assert.ok(calls.every(call => call.options.method === 'GET' && call.options.cache === 'no-store'
    && call.options.headers['x-runtime-session-id'] === 'session'));
});

test('foreign-session and foreign-run responses are not rendered', async () => {
  await assert.rejects(loadRunView(async () => Response.json(context), 'foreign', new AbortController().signal), /INVALID_RUN_VIEW/);
  await assert.rejects(loadRunView(async url => Response.json(url === '/b0/context' ? context : { ...row, run_id: 'foreign' }),
    'session', new AbortController().signal), /INVALID_RUN_VIEW/);
});

test('permission loss is explicit and no fallback data source or write is tried', async () => {
  let count = 0;
  await assert.rejects(loadRunView(async () => { count++; return new Response('', { status: 403 }); },
    'session', new AbortController().signal), /ACCESS_LOST/);
  assert.equal(count, 1);
});

test('query run schema is accepted and switching session hides the other view immediately', async () => {
  const queryRow = { ...row, schema_version: 'analytics-run-channel-followup/v1' };
  const queryContext = { session_id: 'session-query-synthetic-a', ready: true,
    conversation: { schema_version: 'analytics-run-channel-followup/v1', conversation_id: 'conv', run_ids: [id] } };
  const value = await loadRunView(async (url, options) => {
    assert.equal(options.headers['x-runtime-session-id'], 'session-query-synthetic-a');
    return Response.json(url === '/b0/context' ? queryContext : queryRow);
  }, 'session-query-synthetic-a', new AbortController().signal);
  assert.equal(value.runs[0].schema_version, 'analytics-run-channel-followup/v1');
  const hidden = visibleRunView(value, 'session-query-synthetic-b');
  assert.deepEqual(hidden.runs, []);
  assert.equal(hidden.ready, false);
  assert.equal(hidden.sessionId, 'session-query-synthetic-b');
  assert.equal(visibleRunView(value, 'session-query-synthetic-a').runs[0].run_id, id);
  assert.deepEqual(emptyRunView('session-query-synthetic-b').runs, []);
});
