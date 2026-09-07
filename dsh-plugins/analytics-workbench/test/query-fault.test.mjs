import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { decodeQueryReceipt } from '../src/query-model.mjs';
import {
  CHANNEL_FACT_LEAK, HISTORICAL_SUPERVISOR_EXITS, QUERY_FAULT_COPY,
  classifyQueryReceipt, classifyQueryToolBlock, historicalSupervisorRemainsUnknown,
  peerUntouchedByCancel, queryFaultAllowsFacts, refreshInventoryEqual,
  singleTerminal, successSurvivesCancel, textLeaksQueryFacts, workerReleased,
} from '../src/query-fault.mjs';
import {
  FAIL_CARD_MARKERS, historicalSupervisorRecord, otherSessionNotCancelled,
} from '../../../scripts/dsh-b0/native-query-fault-scenario.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const counts = {
  channel_mature_cohort_count: 2, channel_immature_count: 0, channel_repeat_count: 1,
  channel_cross_channel_count: 0, channel_repeat_ratio: 0.5, channel_cross_channel_ratio: 0,
  channel_window_net_paid_minor: 100, channel_empty_reason: null,
};
const filters = {
  schema_version: 'analytics-channel-followup/v1', query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1', metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1', data_version: 'synthetic-channel-followup-data/v1',
  hash_version: 'channel-followup-filter-hash/v1', cohort_window_kind: 'FIXED',
  resolved_cohort_start: '2026-05-31T16:00:00.000000+00:00', resolved_cohort_end: '2026-08-31T16:00:00.000000+00:00',
  observation_days: 30, data_snapshot_ref: 'synthetic-channel-followup-v1',
  as_of: '2026-08-31T16:00:00.000000+00:00', timezone: 'Asia/Shanghai', channel_ids: ['A'],
  cohort_ref: null, product_ids: [], exclude_low_price: false, comparison: null,
  permission_scope: 'scope_1', data_digest: 'a'.repeat(64), filter_hash: 'b'.repeat(64),
};
const result = {
  schema_version: 'analytics-channel-followup/v1', answer_mode: 'DETERMINISTIC_TOOL',
  query_id: 'channel_first_observed_followup', query_version: 'channel-followup-query/v1',
  metric_id: 'channel_first_observed_n_day_repeat', metric_version: 'channel-followup-metric/v1',
  data_version: 'synthetic-channel-followup-data/v1', hash_version: 'channel-followup-filter-hash/v1',
  contains_real_data: false, data_source: 'SYNTHETIC_SNAPSHOT',
  data_snapshot_ref: 'synthetic-channel-followup-v1', as_of: filters.as_of,
  resolved_filters: filters, filter_hash: filters.filter_hash,
  facts: {
    display_name: '首次观察到的渠道 / N日二单率', currency: 'CNY', amount_unit: 'minor',
    amount_precision: 'integer_fen', observation_days: 30,
    channels: [{ channel_id: 'A', ...counts }], totals: counts,
  },
  limitations: ['synthetic only'],
};
const receipt = {
  schema_version: 'analytics-run-channel-followup-native-receipt/v1',
  run_id: 'run_1', attempt_id: 'attempt_1', step_id: 'step_1', disposition: 'EXECUTE', result,
};

test('valid receipt is ok and may show facts', () => {
  const classified = classifyQueryReceipt(receipt);
  assert.equal(classified.kind, 'ok');
  assert.equal(queryFaultAllowsFacts(classified.kind), true);
  assert.equal(decodeQueryReceipt(receipt).result.facts.totals.channel_repeat_count, 1);
});

test('unknown version and malformed receipts never allow channel facts', () => {
  const unknown = classifyQueryReceipt({ ...receipt, schema_version: 'analytics-run-channel-followup-native-receipt/v99' });
  assert.equal(unknown.kind, 'unknown-version');
  assert.equal(queryFaultAllowsFacts(unknown.kind), false);
  const extra = classifyQueryReceipt({ ...receipt, html: '<img src=x>' });
  assert.equal(extra.kind, 'malformed');
  const nan = structuredClone(receipt);
  nan.result.facts.totals.channel_repeat_ratio = Number.NaN;
  nan.result.facts.channels[0].channel_repeat_ratio = Number.NaN;
  assert.equal(classifyQueryReceipt(nan).kind, 'malformed');
  const missing = classifyQueryReceipt(undefined);
  assert.equal(missing.kind, 'malformed');
  for (const row of [unknown, extra, nan, missing]) {
    assert.equal(textLeaksQueryFacts(row.copy ?? QUERY_FAULT_COPY.unrecognized), false);
  }
});

test('tool-error and running blocks keep the existing copy and hide numbers', () => {
  const running = classifyQueryToolBlock({ callId: 'c1', name: 'analytics_channel_followup_query' });
  assert.equal(running.kind, 'running');
  assert.equal(running.copy, QUERY_FAULT_COPY.running);
  const failed = classifyQueryToolBlock({
    kind: 'tool-result', isError: true, meta: receipt,
    content: [{ type: 'text', text: 'SENSITIVE N=30 1100.00 元' }],
  });
  assert.equal(failed.kind, 'tool-error');
  assert.equal(failed.copy, QUERY_FAULT_COPY.toolError);
  assert.equal(textLeaksQueryFacts(failed.copy), false);
  assert.equal(CHANNEL_FACT_LEAK.test(failed.copy), false);
});

test('cancel A does not rewrite peer B; SUCCEEDED survives a later cancel', () => {
  const peer = { run_id: 'run_b', session_id: 'session-query-synthetic-b', status: 'QUEUED' };
  assert.equal(peerUntouchedByCancel(peer, 'QUEUED'), true);
  assert.equal(peerUntouchedByCancel({ ...peer, status: 'CANCELLED' }, 'QUEUED'), false);
  assert.equal(otherSessionNotCancelled({ status: 'RUNNING' }), true);
  const before = { run_id: 'run_a', status: 'SUCCEEDED', result_json: { facts: { observation_days: 30 } } };
  assert.equal(successSurvivesCancel(before, { ...before, version: 9 }), true);
  assert.equal(successSurvivesCancel(before, { ...before, status: 'CANCELLED', result_json: null }), false);
  assert.equal(singleTerminal('SUCCEEDED') && singleTerminal('CANCELLED'), true);
  assert.equal(singleTerminal('CANCELLING'), false);
});

test('released worker and refresh inventory stay exact', () => {
  assert.equal(workerReleased({ state: 'EXITED', active_slot: null }), true);
  assert.equal(workerReleased({ state: 'EXITED', active_slot: 1 }), false);
  const inventory = { runs: ['run_a', 'run_b'], steps: 2, workers: ['exec_1'] };
  assert.equal(refreshInventoryEqual(inventory, { ...inventory }), true);
  assert.equal(refreshInventoryEqual(inventory, { ...inventory, runs: ['run_a', 'run_b', 'run_c'] }), false);
});

test('historical three supervisor exits stay UNKNOWN and are not closed by EPIPE', async () => {
  assert.equal(historicalSupervisorRemainsUnknown(), true);
  assert.equal(HISTORICAL_SUPERVISOR_EXITS.closed_by_epipe, false);
  assert.deepEqual(historicalSupervisorRecord(), HISTORICAL_SUPERVISOR_EXITS);
  const serve = await readFile(join(here, '../../../scripts/dsh-b0/serve.mjs'), 'utf8');
  assert.match(serve, /stateScenario \? 'backend\.tests\.analytics_native_probe' : 'backend\.analytics_runtime'/);
  assert.doesNotMatch(serve, /queryScenario \? 'backend\.tests/);
});

test('fail-card markers never include channel facts', () => {
  for (const text of Object.values(FAIL_CARD_MARKERS)) {
    assert.equal(textLeaksQueryFacts(text), false);
  }
});
