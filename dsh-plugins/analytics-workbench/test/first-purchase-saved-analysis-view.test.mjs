import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  COPY, HTTP_API, buildSavedAnalysisView, decodeSavedAnalysis, isForeignFamily, renderSavedAnalysisHtml,
} from '../src/first-purchase-saved-analysis-model.mjs';

const analysisId = 'analysis_' + 'a'.repeat(32);
const filters = {
  schema_version: 'analytics-first-purchase-path/v1',
  query_id: 'first_purchase_product_path',
  query_version: 'first-purchase-path-query/v1',
  metric_id: 'first_purchase_product_n_day_finished',
  metric_version: 'first-purchase-path-metric/v1',
  cohort_window: { kind: 'FIXED', start_date: '2026-06-01', end_date: '2026-09-01' },
  observation_days: 30,
  data_snapshot_ref: 'synthetic-first-purchase-v1',
  timezone: 'Asia/Shanghai',
  channel_ids: ['A', 'B'],
  cohort_ref: null,
  product_ids: [],
  exclude_low_price: false,
  comparison: null,
};
const resolved = {
  schema_version: 'analytics-first-purchase-path/v1',
  query_id: 'first_purchase_product_path',
  query_version: 'first-purchase-path-query/v1',
  metric_id: 'first_purchase_product_n_day_finished',
  metric_version: 'first-purchase-path-metric/v1',
  data_version: 'synthetic-first-purchase-data/v1',
  hash_version: 'first-purchase-path-filter-hash/v1',
  cohort_window_kind: 'FIXED',
  resolved_cohort_start: '2026-05-31T16:00:00.000000+00:00',
  resolved_cohort_end: '2026-08-31T16:00:00.000000+00:00',
  observation_days: 30,
  data_snapshot_ref: 'synthetic-first-purchase-v1',
  as_of: '2026-08-31T16:00:00.000000+00:00',
  timezone: 'Asia/Shanghai',
  channel_ids: ['A', 'B'],
  cohort_ref: null,
  product_ids: [],
  exclude_low_price: false,
  comparison: null,
  permission_scope: 'scope_1',
  data_digest: 'a'.repeat(64),
  filter_hash: 'b'.repeat(64),
};
const analysis = {
  schema_version: 'analytics-first-purchase-saved-analysis/v1',
  analysis_id: analysisId,
  version: 1,
  title: '首购商品路径 / 30日正装转化',
  query_ref: { query_id: 'first_purchase_product_path', query_version: 'first-purchase-path-query/v1' },
  metric_refs: [{ metric_id: 'first_purchase_product_n_day_finished', metric_version: 'first-purchase-path-metric/v1' }],
  filters,
  visual_spec: { schema_version: 'analytics-visual-table/v1', kind: 'TABLE' },
  created_from_run_id: 'run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  owner_id: 'alice',
  visibility: 'PRIVATE',
  endorsement: 'PERSONAL',
  data_mode: 'SNAPSHOT',
  snapshot: {
    run_id: 'run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    evidence_digest: 'c'.repeat(64),
    resolved_filters: resolved,
    data_snapshot_ref: 'synthetic-first-purchase-v1',
    as_of: resolved.as_of,
  },
  facts: {
    display_name: '首购商品路径 / N日正装转化',
    currency: 'CNY',
    amount_unit: 'minor',
    amount_precision: 'integer_fen',
    observation_days: 30,
    cohort_enrolled_count: 10,
    cohort_mature_count: 9,
    cohort_immature_count: 1,
    products: [{
      product_id: 'sku-s1', role: 'sample', enrolled_count: 6, mature_count: 5, immature_count: 1,
      finished_conversion_count: 3, finished_conversion_ratio: 0.6, empty_reason: null,
    }],
  },
  data_version: 'synthetic-first-purchase-data/v1',
  filter_hash: 'b'.repeat(64),
  limitations: ['synthetic'],
  created_at: '2026-09-08T00:00:00.000000+00:00',
  finite_mock: true,
  http_api: HTTP_API,
};

test('decodes first-purchase SNAPSHOT and rejects channel/B0', () => {
  assert.equal(decodeSavedAnalysis(analysis)?.analysis_id, analysisId);
  assert.equal(isForeignFamily({ schema_version: 'analytics-saved-analysis/v1' }), true);
  assert.equal(isForeignFamily({ query_id: 'channel_first_observed_followup' }), true);
  const view = buildSavedAnalysisView({ analysis, sessionId: null, modelAvailable: false });
  assert.equal(view.kind, 'detail');
  assert.match(view.totals, /入组 10/);
  assert.equal(view.joinHint, COPY.joinUnavailable);
  const html = renderSavedAnalysisHtml(view);
  assert.match(html, /首购商品路径/);
});

test('save panel stays disabled without SUCCEEDED', () => {
  const panel = buildSavedAnalysisView({ runStatus: 'RUNNING' });
  assert.equal(panel.kind, 'save-panel');
  assert.equal(panel.canSave, false);
  const ready = buildSavedAnalysisView({ runStatus: 'SUCCEEDED' });
  assert.equal(ready.canSave, true);
});

test('view source exports FirstPurchaseSavedAnalysisView and stays NOT_CONNECTED', () => {
  const path = fileURLToPath(new URL('../src/first-purchase-saved-analysis-view.tsx', import.meta.url));
  const src = readFileSync(path, 'utf8');
  assert.match(src, /export function FirstPurchaseSavedAnalysisView/);
  assert.match(src, /data-testid="analytics-first-purchase-saved-analysis-view"/);
  assert.match(src, /data-http="NOT_CONNECTED"/);
  assert.match(src, /disabled/);
});
