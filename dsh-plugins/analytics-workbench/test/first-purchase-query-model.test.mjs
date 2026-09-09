import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  FIRST_PURCHASE_RECEIPT_LIMIT, decodeFirstPurchaseRequest, decodeFirstPurchaseReceipt,
  firstPurchaseSaveBinding, readBoundedJson, receiptMatchesRequest,
} from '../src/first-purchase-query-model.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const expected = JSON.parse(await readFile(join(here, '../../../backend/tests/fixtures/analytics_first_purchase_v1_expected.json'), 'utf8'));
const missing = JSON.parse(await readFile(join(here, '../../../backend/tests/fixtures/analytics_first_purchase_v1_missing_role_expected.json'), 'utf8'));

const request = expected.request;

function okReceipt(result = expected.result, extra = {}) {
  return {
    schema_version: 'analytics-run-first-purchase-native-receipt/v1',
    run_id: 'run_1', request_id: 'req-1', call_id: 'call-1', attempt_id: 'attempt_1',
    step_id: 'step_1', disposition: 'EXECUTE', run_status: 'SUCCEEDED', result, ...extra,
  };
}

test('decodeFirstPurchaseRequest accepts registered request and rejects owner/scope', () => {
  assert.ok(decodeFirstPurchaseRequest(request));
  assert.equal(decodeFirstPurchaseRequest({ ...request, owner: 'eve' }), null);
  assert.equal(decodeFirstPurchaseRequest({ ...request, permission_scope: 'x' }), null);
  assert.equal(decodeFirstPurchaseRequest({ ...request, observation_days: 7 }), null);
});

test('decodeFirstPurchaseReceipt requires complete filters and ratio consistency', () => {
  const decoded = decodeFirstPurchaseReceipt(okReceipt());
  assert.ok(decoded);
  assert.equal(decoded.result.status, 'OK');
  const incomplete = structuredClone(okReceipt());
  incomplete.result.resolved_filters = { observation_days: 30 };
  assert.equal(decodeFirstPurchaseReceipt(incomplete), null);
  const badRatio = structuredClone(okReceipt());
  badRatio.result.facts.products[1].finished_conversion_ratio = 0.99;
  assert.equal(decodeFirstPurchaseReceipt(badRatio), null);
});

test('empty mature denominator stays null', () => {
  const empty = structuredClone(okReceipt());
  empty.result.facts.products = [{
    product_id: 'sku-empty', role: 'sample', enrolled_count: 2, mature_count: 0, immature_count: 2,
    finished_conversion_count: 0, finished_conversion_ratio: null, empty_reason: 'EMPTY_MATURE_COHORT',
  }];
  empty.result.facts.cohort_enrolled_count = 2;
  empty.result.facts.cohort_mature_count = 0;
  empty.result.facts.cohort_immature_count = 2;
  const decoded = decodeFirstPurchaseReceipt(empty);
  assert.ok(decoded);
  assert.equal(decoded.result.facts.products[0].finished_conversion_ratio, null);
  const zero = structuredClone(empty);
  zero.result.facts.products[0].finished_conversion_ratio = 0;
  assert.equal(decodeFirstPurchaseReceipt(zero), null);
});

test('decodeFirstPurchaseReceipt maps REJECTED without conversion fields', () => {
  const receipt = okReceipt(missing.result);
  const decoded = decodeFirstPurchaseReceipt(receipt);
  assert.ok(decoded);
  assert.equal(decoded.result.status, 'REJECTED');
  const zero = structuredClone(receipt);
  zero.result.facts = { finished_conversion_ratio: 0 };
  assert.equal(decodeFirstPurchaseReceipt(zero), null);
});

test('in-flight receipt is accepted without a result', () => {
  const inflight = {
    schema_version: 'analytics-run-first-purchase-native-receipt/v1',
    run_id: 'run_1', request_id: 'req-1', call_id: 'call-1', attempt_id: 'attempt_1',
    step_id: null, disposition: 'IN_FLIGHT', run_status: 'RUNNING', result: null,
  };
  const decoded = decodeFirstPurchaseReceipt(inflight);
  assert.ok(decoded);
  assert.equal(decoded.disposition, 'IN_FLIGHT');
});

test('receiptMatchesRequest binds request_id call_id and query window', () => {
  const receipt = decodeFirstPurchaseReceipt(okReceipt());
  assert.ok(receiptMatchesRequest(receipt, decodeFirstPurchaseRequest(request), { requestId: 'req-1', callId: 'call-1' }));
  assert.equal(receiptMatchesRequest(receipt, decodeFirstPurchaseRequest(request), { requestId: 'other', callId: 'call-1' }), false);
  const otherN = decodeFirstPurchaseRequest({ ...request, observation_days: 60 });
  assert.equal(receiptMatchesRequest(receipt, otherN, { requestId: 'req-1', callId: 'call-1' }), false);
});

test('save binding is run-id only', () => {
  assert.deepEqual(firstPurchaseSaveBinding('run-9'), {
    created_from_run_id: 'run-9', source: 'first-purchase-run',
  });
  assert.equal(firstPurchaseSaveBinding(''), null);
});

test('overflow stream is cancelled', async () => {
  const payload = new Uint8Array(16).fill(1);
  let cancelled = false;
  const stream = new ReadableStream({
    start(controller) { controller.enqueue(payload); },
    cancel() { cancelled = true; },
  });
  const response = new Response(stream, { headers: { 'content-type': 'application/json' } });
  await assert.rejects(() => readBoundedJson(response, 4), /too large/);
  assert.equal(cancelled, true);
  assert.ok(FIRST_PURCHASE_RECEIPT_LIMIT > 0);
});
