import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyCancelOutcome, QUERY_CANCEL_COPY, sessionCancelEnvelope } from '../src/query-cancel.mjs';

test('cancel copy is safe and does not claim CANCELLED', () => {
  assert.equal(QUERY_CANCEL_COPY.submitting.includes('CANCELLED'), false);
  assert.equal(QUERY_CANCEL_COPY.accepted.includes('CANCELLED'), false);
  assert.equal(QUERY_CANCEL_COPY.accepted.includes('已停止'), false);
  assert.ok(QUERY_CANCEL_COPY.error.includes('重试'));
});

test('classifyCancelOutcome reads HTTP and RPC envelope without exposing server text', () => {
  assert.equal(classifyCancelOutcome({ status: 200, body: { result: { ok: true, value: { accepted: true } } } }), 'accepted');
  assert.equal(classifyCancelOutcome({ status: 200, body: { result: { ok: true } } }), 'accepted');
  assert.equal(classifyCancelOutcome({ status: 403, body: { result: { ok: true } } }), 'error');
  assert.equal(classifyCancelOutcome({ status: 409, body: { result: { ok: false, error: { message: 'SECRET' } } } }), 'error');
  assert.equal(classifyCancelOutcome({ status: 503, body: null }), 'error');
  assert.equal(classifyCancelOutcome({ status: 200, body: { result: { ok: false, error: { message: 'SECRET' } } } }), 'error');
  assert.equal(classifyCancelOutcome({ status: 200, body: { result: { ok: 'yes' } } }), 'error');
  assert.equal(classifyCancelOutcome({ network: true }), 'error');
  assert.equal(classifyCancelOutcome(null), 'error');
  const envelope = sessionCancelEnvelope('session-query-synthetic-a', 'query-cancel-1');
  assert.equal(envelope.method, 'session/cancel');
});
