import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeRequest, evidenceFor, requestForTool } from '../src/native-evidence.mjs';

const e = (type, data) => ({ type, data });
const user = id => ({ id, source: { kind: 'user', rpcId: id } });
const turn = (id, number, reason = 'completed') => [e('turn/start', { turn: number }), e('user/message', user(id)),
  e('tool/call', { turn: number, callId: `call-${id}`, name: 'analytics_b0_query' }),
  e('tool/result', { turn: number, message: { role: 'tool', content: [{ type: 'tool-result', toolCallId: `call-${id}`, isError: false, content: [] }] } }),
  e('turn/end', { turn: number, reason: { kind: reason } })];
const intent = { run_id: 'run-1', attempt_id: 'attempt-1', session_id: 'session-1', request_id: 'first' };

test('native journal turn/end without actual exit cannot finish a run', () => {
  const summary = summarizeRequest(turn('first', 1), 'first');
  assert.equal(evidenceFor(intent, summary, false).outcome, 'RUNNING');
  assert.equal(evidenceFor(intent, summary, false).execution_exited, false);
  assert.equal(evidenceFor(intent, summary, true).outcome, 'SUCCEEDED');
});

test('second question and old late result remain correlated to their own turn', () => {
  const events = [...turn('first', 1), ...turn('second', 2, 'error')];
  const first = summarizeRequest(events, 'first');
  assert.deepEqual(first.successful_call_ids, ['call-first']);
  assert.equal(first.reason.kind, 'completed');
  const second = summarizeRequest(events, 'second');
  assert.deepEqual(second.successful_call_ids, ['call-second']);
  assert.equal(second.reason.kind, 'error');
  assert.equal(second.currentRequestId, 'second');
  assert.equal(requestForTool(events, 'call-first'), 'first');
  assert.equal(requestForTool(events, 'call-second'), 'second');
  assert.equal(requestForTool(events, 'missing'), undefined);
});

test('discarded pending prompt needs native idle before cancellation proof', () => {
  const events = [e('agent/inbox/spliced', { target: 'next-turn', start: 0, inserted: [user('first')] }),
    e('agent/inbox/spliced', { target: 'next-turn', start: 0, removedCount: 1, inserted: [], outcome: 'canceled' })];
  const summary = summarizeRequest(events, 'first');
  assert.equal(evidenceFor(intent, summary, false).execution_exited, false);
  assert.equal(evidenceFor(intent, summary, true).outcome, 'CANCELLED');
});

test('missing or ambiguous request never manufactures completion', () => {
  const missing = evidenceFor(intent, summarizeRequest(turn('other', 1), 'first'), true);
  assert.equal(missing.outcome, 'UNKNOWN');
  assert.equal(missing.execution_exited, false);
  const ambiguous = summarizeRequest([...turn('first', 1), e('user/message', user('second'))], 'first');
  assert.equal(evidenceFor(intent, ambiguous, true).outcome, 'UNKNOWN');
});

test('official interrupted-tail repair is failure only after the resumed driver is idle and durable', () => {
  const summary = summarizeRequest(turn('first', 1, 'interrupted'), 'first');
  const waiting = evidenceFor(intent, summary, false);
  assert.equal(waiting.outcome, 'RUNNING');
  assert.equal(waiting.execution_exited, false);
  const stopped = evidenceFor(intent, summary, true);
  assert.equal(stopped.outcome, 'FAILED');
  assert.equal(stopped.execution_exited, true);
  assert.equal(stopped.error_code, 'EXECUTION_UNKNOWN');
  assert.equal(stopped.request_id, intent.request_id);
});
