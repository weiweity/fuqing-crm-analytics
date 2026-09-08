import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { decodeQueryRequest } from '../../dsh-plugins/analytics-workbench/src/query-model.mjs';
import { QUERY_SESSION_IDS, queryMockScript } from './query-scenario.mjs';
import {
  FAULT_QUESTIONS, FAULT_SCENARIO, QUERY_FAULT_PROBE_SEQUENCE, SUCCESS_SCENARIO,
  parseQueryCancelRef, parseStopGeneratingRef, queryFaultMockScript, sessionCancelEnvelope,
  sqlHoldObserved,
} from './native-query-fault-scenario.mjs';

const here = dirname(fileURLToPath(import.meta.url));

test('fault entry is independent of the normal native-query scenario', () => {
  assert.equal(FAULT_SCENARIO, 'native-query-fault');
  assert.equal(SUCCESS_SCENARIO, 'native-query');
  assert.notEqual(FAULT_SCENARIO, SUCCESS_SCENARIO);
  assert.deepEqual([...QUERY_FAULT_PROBE_SEQUENCE], ['sql_hold', 'unknown_schema', 'passthrough']);
  assert.equal(QUERY_FAULT_PROBE_SEQUENCE.includes('illegal_facts'), false);
  assert.equal(FAULT_QUESTIONS.length, 4);
  assert.equal(new Set(FAULT_QUESTIONS).size, 4);
  assert.ok(FAULT_QUESTIONS[2].includes('30 日'));
  assert.ok(FAULT_QUESTIONS[3].includes('60 日'));
});

test('fault mock binds A restore N=30 then a later B N=60 turn, not a second call in the success turn', () => {
  const script = queryFaultMockScript();
  assert.equal(script.length, 7);
  assert.ok(script.length <= 16);
  assert.deepEqual(script.map(step => step.sequence), [
    ['tool_call_success'], ['tool_call_success'], ['tool_call_success'], ['success'],
    ['tool_call_success'], ['success'], ['success'],
  ]);
  assert.equal(JSON.parse(script[0].toolArguments).observation_days, 30);
  assert.equal(JSON.parse(script[1].toolArguments).observation_days, 60);
  assert.equal(JSON.parse(script[2].toolArguments).observation_days, 30);
  assert.equal(JSON.parse(script[4].toolArguments).observation_days, 60);
  assert.equal(script.filter(step => step.sequence[0] === 'tool_call_success').length, 4);
  assert.ok(script.every(step => step.chunkDelayMs === 0));
  assert.equal(decodeQueryRequest(JSON.parse(script[0].toolArguments)).cohort_window.kind, 'FIXED');
  const normal = queryMockScript();
  assert.equal(normal.length, 4);
  assert.notEqual(JSON.stringify(script), JSON.stringify(normal));
});

test('visible cancel parsers prefer the query card button; Stop generating is observed not auto-clicked', async () => {
  const card = '@e80 [button] "停止查询"\n@e66 [button] "Stop generating"\n';
  assert.equal(parseQueryCancelRef(card), '@e80');
  assert.equal(parseQueryCancelRef('@e80 [button] "停止查询" [disabled]\n'), '@e80');
  assert.equal(parseStopGeneratingRef(card), '@e66');
  assert.equal(parseQueryCancelRef('@e70 [button] "Send message"\n'), null);
  const envelope = sessionCancelEnvelope(QUERY_SESSION_IDS[0], 'query-cancel-1');
  assert.equal(envelope.method, 'session/cancel');
  assert.deepEqual(envelope.payload.args.request, { sessionId: QUERY_SESSION_IDS[0] });
  const smoke = await readFile(join(here, 'native-query-fault-smoke.mjs'), 'utf8');
  assert.match(smoke, /via = 'query-card-button'/);
  assert.doesNotMatch(smoke, /native-stop-generating/);
});

test('SQL hold proof requires RUNNING worker and matching execution, not QUEUED', () => {
  const proof = { event: 'SQL_ACTIVE', execution_id: 'exec_' + 'ab'.repeat(16), run_id: 'run_1' };
  const worker = { execution_id: proof.execution_id, active_slot: 1 };
  const running = { run_id: 'run_1', status: 'RUNNING' };
  assert.equal(sqlHoldObserved(proof, worker, running), true);
  assert.equal(sqlHoldObserved(proof, worker, { ...running, status: 'QUEUED' }), false);
  assert.equal(sqlHoldObserved({ ...proof, event: 'DONE' }, worker, running), false);
  assert.equal(sqlHoldObserved(proof, { ...worker, active_slot: null }, running), false);
});

test('serve opt-in keeps --native-query on analytics_runtime and attaches the query probe only for --native-query-fault', async () => {
  const serve = await readFile(join(here, 'serve.mjs'), 'utf8');
  assert.match(serve, /\[--native-cards\|--native-state\|--native-query\|--native-query-fault\|--native-query-assets\]/);
  assert.match(serve, /queryFaultScenario/);
  assert.match(serve, /queryFaultScenario \? 'backend\.tests\.analytics_query_native_fault_probe'/);
  assert.match(serve, /queryFaultScenario \? \{ script: queryFaultMockScript\(\) \}/);
  assert.match(serve, /else if \(queryFaultScenario\) \{[\s\S]*?\['sql_hold', 'unknown_schema', 'passthrough'\]/);
  assert.doesNotMatch(serve, /else if \(queryFaultScenario\) \{[\s\S]*?illegal_facts/);
  assert.doesNotMatch(serve, /queryScenario \? 'backend\.tests/);
  assert.equal((serve.match(/backend\.analytics_runtime/g) || []).length, 1);
  assert.match(serve, /queryFamily = queryScenario \|\| queryFaultScenario/);
});
