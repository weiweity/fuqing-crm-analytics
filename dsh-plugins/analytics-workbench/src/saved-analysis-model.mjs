/** Decode/display saved SNAPSHOT analyses. No metric compute, no HTTP, no session. */
import { decodeQueryRequest } from './query-model.mjs';
import { formatEmptyReason, formatFenYuan, formatRatioPercent } from './query-format.mjs';

export const SAVED_ANALYSIS_SCHEMA = 'analytics-saved-analysis/v1';
export const VISUAL_SCHEMA = 'analytics-visual-table/v1';
export const QUERY_SCHEMA = 'analytics-channel-followup/v1';
export const JS_MAX_SAFE_INTEGER = 9007199254740991;
export const FINITE_MOCK = true;
export const HTTP_API = 'NOT_CONNECTED';

export const COPY = Object.freeze({
  heading: '已保存分析',
  snapshot: '历史快照',
  saveHint: '保存当前口径和本次快照',
  saved: '已保存',
  join: '加入我的驾驶舱',
  joinUnavailable: 'HTTP 未接通，不能加入驾驶舱',
  empty: '开始一次分析',
  noSession: '无活动会话、模型不可用时仍可查看已保存快照',
  synthetic: 'SYNTHETIC · 有限 mock，不是真实业务数据。',
  unauthorized: '分析不存在或当前身份不可见。',
  cannotSave: '未完成的运行不能保存',
  noApproval: '不附带营销批准',
  http: 'HTTP/OpenAPI 未接通',
  refreshable: '可刷新',
  finiteMock: 'finite mock',
});

const OPAQUE = /^[A-Za-z0-9_.:-]{1,128}$/;
const SHA = /^[0-9a-f]{64}$/;
const RFC3339 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
const ANALYSIS_ID = /^analysis_[a-f0-9]{32}$/;
const ANALYSIS_KEYS = Object.freeze([
  'schema_version', 'analysis_id', 'version', 'title', 'query_ref', 'metric_refs',
  'filters', 'visual_spec', 'created_from_run_id', 'owner_id', 'visibility',
  'endorsement', 'data_mode', 'snapshot', 'facts', 'data_version', 'filter_hash',
  'limitations', 'refresh_candidate', 'created_at', 'finite_mock', 'http_api',
]);
const SNAPSHOT_KEYS = Object.freeze([
  'run_id', 'evidence_digest', 'resolved_filters', 'data_snapshot_ref', 'as_of',
]);
const QUERY_REF_KEYS = Object.freeze(['query_id', 'query_version']);
const METRIC_REF_KEYS = Object.freeze(['metric_id', 'metric_version']);
const VISUAL_KEYS = Object.freeze(['schema_version', 'kind']);
const LIST_KEYS = Object.freeze([
  'schema_version', 'analysis_id', 'version', 'title', 'query_id', 'observation_days',
  'cohort_window', 'as_of', 'data_mode', 'visibility', 'refreshable', 'finite_mock', 'http_api',
]);
const FILTER_KEYS = Object.freeze([
  'schema_version', 'query_id', 'query_version', 'metric_id', 'metric_version', 'data_version',
  'hash_version', 'cohort_window_kind', 'resolved_cohort_start', 'resolved_cohort_end',
  'observation_days', 'data_snapshot_ref', 'as_of', 'timezone', 'channel_ids', 'cohort_ref',
  'product_ids', 'exclude_low_price', 'comparison', 'permission_scope', 'data_digest', 'filter_hash',
]);
const COUNT_KEYS = Object.freeze([
  'channel_mature_cohort_count', 'channel_immature_count', 'channel_repeat_count',
  'channel_cross_channel_count', 'channel_repeat_ratio', 'channel_cross_channel_ratio',
  'channel_window_net_paid_minor', 'channel_empty_reason',
]);
const FACT_KEYS = Object.freeze([
  'display_name', 'currency', 'amount_unit', 'amount_precision', 'observation_days', 'channels', 'totals',
]);
const CANDIDATE_KEYS = Object.freeze(['run_id', 'evidence_digest']);

const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const opaque = value => typeof value === 'string' && OPAQUE.test(value);
const sha256 = value => typeof value === 'string' && SHA.test(value);
const rfc3339 = value => typeof value === 'string' && RFC3339.test(value);
const count = value => typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= JS_MAX_SAFE_INTEGER;
const ratio = value => value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1);
const net = value => value === null || count(value);
const days = value => value === 30 || value === 60 || value === 90;
const channels = value => Array.isArray(value) && value.every(item => item === 'A' || item === 'B')
  && new Set(value).size === value.length;

export function isB0BusinessFixture(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const schema = value.schema_version;
  if (schema === 'analytics-b0/v1' || schema === 'analytics-run-b0/v1') return true;
  if (Object.hasOwn(value, 'repeat_rate') || Object.hasOwn(value, 'repeat_customers')) return true;
  if (value.customers === 100 && value.repeat_customers === 25) return true;
  return isB0BusinessFixture(value.result) || isB0BusinessFixture(value.facts);
}

function decodeCounts(value, channelId) {
  if (!exact(value, channelId ? ['channel_id', ...COUNT_KEYS] : COUNT_KEYS)
    && !(channelId && exact(value, [...COUNT_KEYS, 'channel_id']))) return null;
  if (channelId && value.channel_id !== 'A' && value.channel_id !== 'B') return null;
  const mature = value.channel_mature_cohort_count;
  if (!count(mature) || !count(value.channel_immature_count) || !count(value.channel_repeat_count)
    || !count(value.channel_cross_channel_count) || !ratio(value.channel_repeat_ratio)
    || !ratio(value.channel_cross_channel_ratio) || !net(value.channel_window_net_paid_minor)) return null;
  if (value.channel_repeat_count > mature || value.channel_cross_channel_count > value.channel_repeat_count) return null;
  if (mature === 0) {
    if (value.channel_repeat_count !== 0 || value.channel_cross_channel_count !== 0) return null;
    if (value.channel_repeat_ratio !== null || value.channel_cross_channel_ratio !== null) return null;
    if (value.channel_window_net_paid_minor !== null) return null;
    if (value.channel_empty_reason !== 'EMPTY_MATURE_COHORT') return null;
    return value;
  }
  if (value.channel_empty_reason !== null) return null;
  if (value.channel_repeat_ratio === null || value.channel_cross_channel_ratio === null) return null;
  if (value.channel_window_net_paid_minor === null) return null;
  return value;
}

function decodeResolvedFilters(value) {
  if (!exact(value, FILTER_KEYS)) return null;
  if (value.schema_version !== QUERY_SCHEMA || value.query_id !== 'channel_first_observed_followup'
    || value.query_version !== 'channel-followup-query/v1'
    || value.metric_id !== 'channel_first_observed_n_day_repeat'
    || value.metric_version !== 'channel-followup-metric/v1'
    || value.data_version !== 'synthetic-channel-followup-data/v1'
    || value.hash_version !== 'channel-followup-filter-hash/v1'
    || value.cohort_window_kind !== 'FIXED' || !days(value.observation_days)
    || value.data_snapshot_ref !== 'synthetic-channel-followup-v1' || value.timezone !== 'Asia/Shanghai'
    || !rfc3339(value.resolved_cohort_start) || !rfc3339(value.resolved_cohort_end) || !rfc3339(value.as_of)
    || !channels(value.channel_ids) || value.channel_ids.length === 0
    || value.cohort_ref !== null || !Array.isArray(value.product_ids) || value.product_ids.length !== 0
    || value.exclude_low_price !== false || value.comparison !== null
    || !opaque(value.permission_scope) || !sha256(value.data_digest) || !sha256(value.filter_hash)) return null;
  return value;
}

function decodeFacts(value, observationDays, channelIds) {
  if (!exact(value, FACT_KEYS) || value.display_name !== '首次观察到的渠道 / N日二单率'
    || value.currency !== 'CNY' || value.amount_unit !== 'minor' || value.amount_precision !== 'integer_fen'
    || value.observation_days !== observationDays || !Array.isArray(value.channels)) return null;
  const totals = decodeCounts(value.totals);
  if (!totals) return null;
  const ids = [];
  for (const row of value.channels) {
    const decoded = decodeCounts(row, true);
    if (!decoded || ids.includes(decoded.channel_id)) return null;
    ids.push(decoded.channel_id);
  }
  if (ids.length !== channelIds.length || ids.some(id => !channelIds.includes(id))) return null;
  return value;
}

export function visibleSnapshot(analysis) {
  if (!analysis || analysis.data_mode !== 'SNAPSHOT') return null;
  return analysis.snapshot;
}

export function decodeSavedAnalysis(value) {
  if (isB0BusinessFixture(value) || !exact(value, ANALYSIS_KEYS)) return null;
  if (value.schema_version !== SAVED_ANALYSIS_SCHEMA || !ANALYSIS_ID.test(value.analysis_id)
    || !Number.isInteger(value.version) || value.version < 1
    || typeof value.title !== 'string' || !value.title || value.title.length > 120
    || !exact(value.query_ref, QUERY_REF_KEYS)
    || value.query_ref.query_id !== 'channel_first_observed_followup'
    || value.query_ref.query_version !== 'channel-followup-query/v1'
    || !Array.isArray(value.metric_refs) || value.metric_refs.length !== 1
    || !exact(value.metric_refs[0], METRIC_REF_KEYS)
    || value.metric_refs[0].metric_id !== 'channel_first_observed_n_day_repeat'
    || value.metric_refs[0].metric_version !== 'channel-followup-metric/v1'
    || decodeQueryRequest(value.filters) == null
    || !exact(value.visual_spec, VISUAL_KEYS) || value.visual_spec.schema_version !== VISUAL_SCHEMA
    || value.visual_spec.kind !== 'TABLE' || !opaque(value.created_from_run_id)
    || !opaque(value.owner_id) || value.visibility !== 'PRIVATE' || value.endorsement !== 'PERSONAL'
    || value.data_mode !== 'SNAPSHOT' || !exact(value.snapshot, SNAPSHOT_KEYS)
    || value.snapshot.run_id !== value.created_from_run_id || !sha256(value.snapshot.evidence_digest)
    || value.snapshot.data_snapshot_ref !== 'synthetic-channel-followup-v1'
    || !rfc3339(value.snapshot.as_of) || value.data_version !== 'synthetic-channel-followup-data/v1'
    || !sha256(value.filter_hash) || !Array.isArray(value.limitations) || value.limitations.length < 1
    || value.limitations.some(item => typeof item !== 'string' || !item)
    || !rfc3339(value.created_at) || value.finite_mock !== true || value.http_api !== HTTP_API) return null;
  const filters = decodeResolvedFilters(value.snapshot.resolved_filters);
  if (!filters || filters.filter_hash !== value.filter_hash || filters.as_of !== value.snapshot.as_of) return null;
  const facts = decodeFacts(value.facts, filters.observation_days, filters.channel_ids);
  if (!facts) return null;
  if (value.refresh_candidate !== null) {
    if (!exact(value.refresh_candidate, CANDIDATE_KEYS) || !opaque(value.refresh_candidate.run_id)
      || !sha256(value.refresh_candidate.evidence_digest)
      || value.refresh_candidate.run_id === value.snapshot.run_id) return null;
  }
  return value;
}

export function decodeSavedAnalysisList(value) {
  if (!Array.isArray(value) || value.length > 50) return null;
  const items = [];
  for (const row of value) {
    if (isB0BusinessFixture(row) || !exact(row, LIST_KEYS) || row.schema_version !== SAVED_ANALYSIS_SCHEMA
      || !ANALYSIS_ID.test(row.analysis_id) || !Number.isInteger(row.version) || row.version < 1
      || typeof row.title !== 'string' || !row.title || row.query_id !== 'channel_first_observed_followup'
      || !days(row.observation_days) || !row.cohort_window || row.cohort_window.kind !== 'FIXED'
      || !rfc3339(row.as_of) || row.data_mode !== 'SNAPSHOT' || row.visibility !== 'PRIVATE'
      || typeof row.refreshable !== 'boolean' || row.finite_mock !== true || row.http_api !== HTTP_API) {
      return null;
    }
    items.push(row);
  }
  return items;
}

export function buildSavedAnalysisView({
  analysis = null,
  list = null,
  error = null,
  runStatus = null,
  saveState = 'idle',
  sessionId = null,
  modelAvailable = false,
} = {}) {
  const decoded = analysis == null ? null : decodeSavedAnalysis(analysis);
  const items = list == null ? null : decodeSavedAnalysisList(list);
  if (error && (error.status === 403 || error.status === 404)) {
    return {
      kind: 'error',
      heading: COPY.heading,
      message: COPY.unauthorized,
      sessionRequired: false,
      modelRequired: false,
      sessionId: sessionId ?? null,
      modelAvailable: modelAvailable === true,
      httpConnected: false,
      canSave: false,
      joinEnabled: false,
    };
  }
  if (analysis != null && decoded == null) {
    return {
      kind: 'error',
      heading: COPY.heading,
      message: '结果无法识别或版本不支持；不推断分析成功。',
      sessionRequired: false,
      modelRequired: false,
      sessionId: sessionId ?? null,
      modelAvailable: modelAvailable === true,
      httpConnected: false,
      canSave: false,
      joinEnabled: false,
    };
  }
  if (decoded) {
    const snapshot = visibleSnapshot(decoded);
    const totals = decoded.facts.totals;
    const repeat = formatRatioPercent(totals.channel_repeat_ratio);
    const paid = formatFenYuan(totals.channel_window_net_paid_minor);
    const empty = formatEmptyReason(totals.channel_empty_reason);
    const canSave = runStatus === 'SUCCEEDED';
    return {
      kind: 'detail',
      heading: COPY.heading,
      title: decoded.title,
      badge: COPY.snapshot,
      version: decoded.version,
      condition: `FIXED ${decoded.filters.cohort_window.start_date} → ${decoded.filters.cohort_window.end_date} · N=${decoded.filters.observation_days} · as_of ${snapshot.as_of}`,
      evidence: `run ${snapshot.run_id} · digest ${snapshot.evidence_digest}`,
      totals: `成熟 ${totals.channel_mature_cohort_count} / 二单 ${totals.channel_repeat_count} · 二单率 ${repeat} · 净支付 ${paid}`,
      empty,
      limitations: decoded.limitations,
      refreshCandidate: decoded.refresh_candidate,
      snapshotRunId: snapshot.run_id,
      sessionRequired: false,
      modelRequired: false,
      sessionId: sessionId ?? null,
      modelAvailable: modelAvailable === true,
      httpConnected: false,
      canSave,
      saveHint: canSave ? COPY.saveHint : COPY.cannotSave,
      saveState: saveState === 'saved' ? 'saved' : 'idle',
      joinEnabled: false,
      joinHint: COPY.joinUnavailable,
      synthetic: COPY.synthetic,
      noSession: COPY.noSession,
      http: COPY.http,
    };
  }
  if (items && items.length === 0) {
    return {
      kind: 'empty',
      heading: COPY.heading,
      message: COPY.empty,
      sessionRequired: false,
      modelRequired: false,
      sessionId: sessionId ?? null,
      modelAvailable: modelAvailable === true,
      httpConnected: false,
      canSave: false,
      joinEnabled: false,
      noSession: COPY.noSession,
    };
  }
  if (items) {
    return {
      kind: 'list',
      heading: COPY.heading,
      items: items.map(row => ({
        analysis_id: row.analysis_id,
        title: row.title,
        version: row.version,
        summary: `FIXED ${row.cohort_window.start_date} → ${row.cohort_window.end_date} · N=${row.observation_days} · as_of ${row.as_of}`,
        badge: row.refreshable ? `${COPY.snapshot} / ${COPY.refreshable}` : COPY.snapshot,
      })),
      sessionRequired: false,
      modelRequired: false,
      sessionId: sessionId ?? null,
      modelAvailable: modelAvailable === true,
      httpConnected: false,
      canSave: false,
      joinEnabled: false,
      noSession: COPY.noSession,
      http: COPY.http,
    };
  }
  return {
    kind: 'save-panel',
    heading: COPY.heading,
    saveHint: runStatus === 'SUCCEEDED' ? COPY.saveHint : COPY.cannotSave,
    canSave: runStatus === 'SUCCEEDED',
    saveState: saveState === 'saved' ? 'saved' : 'idle',
    joinEnabled: false,
    joinHint: COPY.joinUnavailable,
    sessionRequired: false,
    modelRequired: false,
    sessionId: sessionId ?? null,
    modelAvailable: modelAvailable === true,
    httpConnected: false,
    noSession: COPY.noSession,
    http: COPY.http,
  };
}

export function renderSavedAnalysisHtml(view) {
  const session = view.sessionId ?? '';
  const model = view.modelAvailable ? '1' : '0';
  const attrs = `class="analytics-b0-dialog analytics-saved-analysis" data-testid="analytics-saved-analysis-view" data-kind="${view.kind}" data-session="${session}" data-model="${model}" data-http="NOT_CONNECTED"`;
  if (view.kind === 'error') {
    return `<div ${attrs} role="status"><h2>${view.heading}</h2><p>${view.message}</p><small>${COPY.noSession}</small></div>`;
  }
  if (view.kind === 'empty') {
    return `<div ${attrs}><h2>${view.heading}</h2><p data-testid="analytics-saved-analysis-empty">${view.message}</p><small>${view.noSession}</small></div>`;
  }
  if (view.kind === 'list') {
    const rows = view.items.map(item => `<li data-analysis-id="${item.analysis_id}"><strong>${item.title}</strong> · v${item.version} · ${item.badge}<br/>${item.summary}</li>`).join('');
    return `<div ${attrs}><h2>${view.heading}</h2><p>${view.noSession}</p><ul data-testid="analytics-saved-analysis-list">${rows}</ul><small>${view.http}</small></div>`;
  }
  if (view.kind === 'detail') {
    const empty = view.empty?.code ? ` · <abbr title="${view.empty.code}">${view.empty.text}</abbr>` : '';
    const saved = view.saveState === 'saved' ? `<p>${COPY.saved}</p>` : '';
    const candidate = view.refreshCandidate
      ? `<p>刷新候选 ${view.refreshCandidate.run_id}；当前仍固定 ${view.snapshotRunId}</p>` : '';
    return `<div ${attrs}><h2>${view.heading}</h2><p>${view.noSession}</p><h3>${view.title}</h3><p>${view.badge} · v${view.version}</p><p>${view.condition}</p><p class="analytics-query-card">${view.totals}${empty}</p><small>${view.evidence}</small>${candidate}${saved}<p><button type="button" disabled>${COPY.join}</button> ${view.joinHint}</p><small>${view.synthetic} ${view.http}</small></div>`;
  }
  const saveLabel = view.saveState === 'saved' ? COPY.saved : view.saveHint;
  return `<div ${attrs}><h2>${view.heading}</h2><p>${view.noSession}</p><label>标题<input maxlength="120" aria-label="分析标题" /></label><p>${saveLabel}；${COPY.noApproval}</p><button type="button" ${view.canSave ? '' : 'disabled'}>${COPY.saveHint}</button><button type="button" disabled>${COPY.join}</button><small>${view.http}</small></div>`;
}
