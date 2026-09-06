import test from 'node:test';
import assert from 'node:assert/strict';
import { loadRunView } from '../src/run-view.mjs';

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
  assert.deepEqual(calls.map(call => call.url), ['/b0/context', `/b0/runs/${id}`]);
  assert.ok(calls.every(call => call.options.method === 'GET' && call.options.cache === 'no-store'));
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
