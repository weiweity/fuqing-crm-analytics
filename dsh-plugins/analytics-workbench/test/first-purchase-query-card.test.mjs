import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FIRST_PURCHASE_RECEIPT_SCHEMA, FIRST_PURCHASE_TOOL_NAME } from '../src/first-purchase-query-model.mjs';

function findRepoFixture(name) {
  const starts = [dirname(fileURLToPath(import.meta.url)), process.cwd()];
  for (const start of starts) {
    let dir = start;
    for (let i = 0; i < 8; i++) {
      const candidate = join(dir, 'backend/tests/fixtures', name);
      if (existsSync(candidate)) return candidate;
      const parent = dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }
  throw new Error(`missing first-purchase fixture ${name}`);
}

const expected = JSON.parse(await readFile(findRepoFixture('analytics_first_purchase_v1_expected.json'), 'utf8'));
const missing = JSON.parse(await readFile(findRepoFixture('analytics_first_purchase_v1_missing_role_expected.json'), 'utf8'));

function block(meta, extra = {}) {
  return {
    kind: 'tool-result', seq: 2, time: 1, callId: 'fp-1',
    call: { name: FIRST_PURCHASE_TOOL_NAME, argsRaw: '{}' }, callTime: 0, content: [], isError: false, subCalls: [],
    meta, ...extra,
  };
}

function receipt(result, extra = {}) {
  return {
    schema_version: FIRST_PURCHASE_RECEIPT_SCHEMA,
    run_id: 'run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', request_id: 'req-1', call_id: 'fp-1',
    attempt_id: 'attempt_1', step_id: 'step_1', disposition: 'EXECUTE', run_status: 'SUCCEEDED',
    result, ...extra,
  };
}

test('compiled first-purchase card covers states without skipping the renderer', async () => {
  const { loadCardHarness } = await import('./tool-card-harness.mjs');
  const harness = await loadCardHarness();
  assert.equal(typeof harness.renderFirstPurchase, 'function');

  const running = { callId: 'fp-run', name: FIRST_PURCHASE_TOOL_NAME, argsRaw: '{}', turn: 1, step: 1, time: 0, subCalls: [] };
  const runningHtml = harness.renderFirstPurchase(running);
  assert.match(runningHtml, /data-query-fault="running"/);
  assert.match(runningHtml, /合成首购查询运行中/);

  const okHtml = harness.renderFirstPurchase(block(receipt(expected.result)));
  assert.match(okHtml, /data-query-fault="ok"/);
  assert.match(okHtml, /data-conversion-metric="1"/);
  assert.match(okHtml, /data-save-source="first-purchase-run"/);

  const emptyResult = structuredClone(expected.result);
  emptyResult.facts.products = [{
    product_id: 'sku-empty', role: 'sample', enrolled_count: 2, mature_count: 0, immature_count: 2,
    finished_conversion_count: 0, finished_conversion_ratio: null, empty_reason: 'EMPTY_MATURE_COHORT',
  }];
  emptyResult.facts.cohort_enrolled_count = 2;
  emptyResult.facts.cohort_mature_count = 0;
  emptyResult.facts.cohort_immature_count = 2;
  const emptyHtml = harness.renderFirstPurchase(block(receipt(emptyResult)));
  assert.match(emptyHtml, /空成熟队列/);
  assert.doesNotMatch(emptyHtml, /data-query-fault="malformed"/);

  const rejectedHtml = harness.renderFirstPurchase(block(receipt(missing.result)));
  assert.match(rejectedHtml, /data-query-fault="contract-rejected"/);
  assert.match(rejectedHtml, /data-conversion-metric="0"/);
  assert.doesNotMatch(rejectedHtml, /data-conversion-metric="1"/);
  assert.match(rejectedHtml, /不展示转化率或 0%/);

  const inflight = receipt(null, { disposition: 'IN_FLIGHT', run_status: 'RUNNING', step_id: null, result: null });
  const inflightHtml = harness.renderFirstPurchase(block(inflight));
  assert.match(inflightHtml, /data-query-fault="in-flight"/);

  const cancelledHtml = harness.renderFirstPurchase(block(undefined, {
    isError: true, content: [{ type: 'text', text: 'first-purchase run was cancelled' }],
  }));
  assert.match(cancelledHtml, /data-query-fault="cancelled"/);

  const failedHtml = harness.renderFirstPurchase(block(undefined, {
    isError: true, content: [{ type: 'text', text: 'first-purchase run failed' }],
  }));
  assert.match(failedHtml, /data-query-fault="tool-error"/);

  const badHtml = harness.renderFirstPurchase(block({ schema_version: FIRST_PURCHASE_RECEIPT_SCHEMA, run_id: 'x' }));
  assert.match(badHtml, /data-query-fault="malformed"/);
});
