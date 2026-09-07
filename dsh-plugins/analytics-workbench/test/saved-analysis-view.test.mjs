import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  COPY, HTTP_API, buildSavedAnalysisView, decodeSavedAnalysis, decodeSavedAnalysisList,
  isB0BusinessFixture, renderSavedAnalysisHtml, visibleSnapshot,
} from '../src/saved-analysis-model.mjs';

const analysisId = 'analysis_' + 'a'.repeat(32);
const filters = {
  schema_version: 'analytics-channel-followup/v1',
  query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1',
  metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1',
  cohort_window: { kind: 'FIXED', start_date: '2026-06-01', end_date: '2026-09-01' },
  observation_days: 30,
  data_snapshot_ref: 'synthetic-channel-followup-v1',
  timezone: 'Asia/Shanghai',
  channel_ids: ['A'],
  cohort_ref: null,
  product_ids: [],
  exclude_low_price: false,
  comparison: null,
};
const counts = {
  channel_mature_cohort_count: 2,
  channel_immature_count: 0,
  channel_repeat_count: 1,
  channel_cross_channel_count: 0,
  channel_repeat_ratio: 0.5,
  channel_cross_channel_ratio: 0,
  channel_window_net_paid_minor: 100,
  channel_empty_reason: null,
};
const resolved = {
  schema_version: 'analytics-channel-followup/v1',
  query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1',
  metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1',
  data_version: 'synthetic-channel-followup-data/v1',
  hash_version: 'channel-followup-filter-hash/v1',
  cohort_window_kind: 'FIXED',
  resolved_cohort_start: '2026-05-31T16:00:00.000000+00:00',
  resolved_cohort_end: '2026-08-31T16:00:00.000000+00:00',
  observation_days: 30,
  data_snapshot_ref: 'synthetic-channel-followup-v1',
  as_of: '2026-08-31T16:00:00.000000+00:00',
  timezone: 'Asia/Shanghai',
  channel_ids: ['A'],
  cohort_ref: null,
  product_ids: [],
  exclude_low_price: false,
  comparison: null,
  permission_scope: 'scope_1',
  data_digest: 'a'.repeat(64),
  filter_hash: 'b'.repeat(64),
};
const analysis = {
  schema_version: 'analytics-saved-analysis/v1',
  analysis_id: analysisId,
  version: 1,
  title: '首次观察到的渠道 / 30日二单率',
  query_ref: { query_id: 'channel_first_observed_followup', query_version: 'channel-followup-query/v1' },
  metric_refs: [{ metric_id: 'channel_first_observed_n_day_repeat', metric_version: 'channel-followup-metric/v1' }],
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
    data_snapshot_ref: 'synthetic-channel-followup-v1',
    as_of: resolved.as_of,
  },
  facts: {
    display_name: '首次观察到的渠道 / N日二单率',
    currency: 'CNY', amount_unit: 'minor', amount_precision: 'integer_fen',
    observation_days: 30,
    channels: [{ channel_id: 'A', ...counts }],
    totals: counts,
  },
  data_version: 'synthetic-channel-followup-data/v1',
  filter_hash: resolved.filter_hash,
  limitations: ['finite mock: not a live compute; synthetic candidate only.'],
  refresh_candidate: null,
  created_at: '2027-01-15T08:00:00.000000+00:00',
  finite_mock: true,
  http_api: 'NOT_CONNECTED',
};
const b0 = {
  schema_version: 'analytics-b0/v1',
  answer_mode: 'STUB',
  data_source: 'SYNTHETIC_FIXTURE',
  fixture_id: 'b0-channel-repeat-2026-09-01',
  data_as_of: '2026-09-01',
  channel: '合成渠道 A',
  customers: 100,
  repeat_customers: 25,
  repeat_rate: 0.25,
};

test('saved analysis decodes without a session and does not recompute ratios', () => {
  const decoded = decodeSavedAnalysis(analysis);
  assert.equal(decoded.analysis_id, analysisId);
  assert.equal(decoded.data_mode, 'SNAPSHOT');
  assert.equal(visibleSnapshot(decoded).run_id, analysis.snapshot.run_id);
  const view = buildSavedAnalysisView({ analysis, sessionId: null, modelAvailable: false });
  assert.equal(view.sessionRequired, false);
  assert.equal(view.modelRequired, false);
  assert.equal(view.httpConnected, false);
  assert.equal(view.badge, COPY.snapshot);
  assert.match(view.totals, /50%/);
  assert.doesNotMatch(view.totals, /25%/);
  const html = renderSavedAnalysisHtml(view);
  assert.match(html, /历史快照/);
  assert.match(html, /无活动会话/);
  assert.match(html, /data-session=""/);
  assert.match(html, /data-model="0"/);
  assert.doesNotMatch(html, /25%/);
});

test('refresh candidate is not treated as the pinned SNAPSHOT', () => {
  const withCandidate = {
    ...analysis,
    refresh_candidate: { run_id: 'run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', evidence_digest: 'd'.repeat(64) },
  };
  const decoded = decodeSavedAnalysis(withCandidate);
  assert.equal(visibleSnapshot(decoded).run_id, 'run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
  const html = renderSavedAnalysisHtml(buildSavedAnalysisView({ analysis: withCandidate }));
  assert.match(html, /当前仍固定 run_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/);
  assert.match(html, /刷新候选 run_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/);
});

test('B0 25% fixture and extra fields are rejected', () => {
  assert.equal(isB0BusinessFixture(b0), true);
  assert.equal(decodeSavedAnalysis(b0), null);
  assert.equal(decodeSavedAnalysis({ ...analysis, facts: { ...analysis.facts, repeat_rate: 0.25 } }), null);
  assert.equal(decodeSavedAnalysis({ ...analysis, extra: true }), null);
  assert.equal(decodeSavedAnalysisList([b0]), null);
  const html = renderSavedAnalysisHtml(buildSavedAnalysisView({ analysis: b0 }));
  assert.match(html, /无法识别/);
  assert.doesNotMatch(html, /25%/);
});

test('unauthorized view does not require a live session or model', () => {
  const view = buildSavedAnalysisView({
    error: { status: 404, code: 'NOT_FOUND', message: '分析不存在或当前身份不可见。' },
    sessionId: null,
    modelAvailable: false,
  });
  assert.equal(view.kind, 'error');
  assert.equal(view.message, COPY.unauthorized);
  assert.equal(view.sessionRequired, false);
  const html = renderSavedAnalysisHtml(view);
  assert.match(html, /分析不存在或当前身份不可见/);
});

test('empty list offers start-analysis and save panel disables incomplete runs', () => {
  const empty = buildSavedAnalysisView({ list: [] });
  assert.equal(empty.kind, 'empty');
  assert.match(renderSavedAnalysisHtml(empty), /开始一次分析/);
  const panel = buildSavedAnalysisView({ runStatus: 'RUNNING' });
  assert.equal(panel.canSave, false);
  assert.match(renderSavedAnalysisHtml(panel), /disabled/);
  const ready = buildSavedAnalysisView({ runStatus: 'SUCCEEDED', saveState: 'saved' });
  assert.equal(ready.canSave, true);
  assert.match(renderSavedAnalysisHtml(ready), /已保存/);
});

test('list items stay SNAPSHOT and HTTP remains disconnected', () => {
  const items = decodeSavedAnalysisList([{
    schema_version: 'analytics-saved-analysis/v1',
    analysis_id: analysisId,
    version: 1,
    title: analysis.title,
    query_id: 'channel_first_observed_followup',
    observation_days: 30,
    cohort_window: filters.cohort_window,
    as_of: resolved.as_of,
    data_mode: 'SNAPSHOT',
    visibility: 'PRIVATE',
    refreshable: false,
    finite_mock: true,
    http_api: HTTP_API,
  }]);
  assert.equal(items[0].data_mode, 'SNAPSHOT');
  const html = renderSavedAnalysisHtml(buildSavedAnalysisView({ list: items }));
  assert.match(html, /data-testid="analytics-saved-analysis-list"/);
  assert.match(html, /HTTP\/OpenAPI 未接通/);
});

test('view source is a sessionless renderer and does not compute business metrics', () => {
  const path = fileURLToPath(new URL('../src/saved-analysis-view.tsx', import.meta.url));
  const src = readFileSync(path, 'utf8');
  assert.match(src, /export function SavedAnalysisView/);
  assert.match(src, /data-testid="analytics-saved-analysis-view"/);
  assert.match(src, /buildSavedAnalysisView/);
  assert.doesNotMatch(src, /fetch\(|repeat_rate|analytics-run-b0|25%/);
  assert.doesNotMatch(src, /channel_repeat_count\s*\//);
  assert.match(src, /sessionId \?\? null/);
  assert.match(src, /modelAvailable === true/);
});
