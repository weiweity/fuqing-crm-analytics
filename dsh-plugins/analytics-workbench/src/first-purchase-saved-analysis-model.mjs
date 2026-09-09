/** Decode/display first-purchase SNAPSHOT analyses. No metric compute, no HTTP, no session. */
import { formatEmptyReason, formatRatioPercent } from './query-format.mjs';

export const SAVED_ANALYSIS_SCHEMA = 'analytics-first-purchase-saved-analysis/v1';
export const VISUAL_SCHEMA = 'analytics-visual-table/v1';
export const QUERY_SCHEMA = 'analytics-first-purchase-path/v1';
export const JS_MAX_SAFE_INTEGER = 9007199254740991;
export const FINITE_MOCK = true;
export const HTTP_API = 'NOT_CONNECTED';

export const COPY = Object.freeze({
  heading: '已保存首购分析',
  snapshot: '历史快照',
  saveHint: '保存当前口径和本次快照',
  saved: '已保存',
  join: '加入我的驾驶舱',
  joinUnavailable: 'HTTP 未接通，不能加入驾驶舱',
  empty: '开始一次首购分析',
  noSession: '无活动会话、模型不可用时仍可查看已保存快照',
  synthetic: 'SYNTHETIC · 有限 mock，不是真实业务数据。',
  unauthorized: '分析不存在或当前身份不可见。',
  cannotSave: '未完成或被拒绝的运行不能保存',
  noApproval: '不附带营销批准',
  http: 'HTTP/OpenAPI 未接通',
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
  'limitations', 'created_at', 'finite_mock', 'http_api',
]);
const SNAPSHOT_KEYS = Object.freeze([
  'run_id', 'evidence_digest', 'resolved_filters', 'data_snapshot_ref', 'as_of',
]);
const FACT_KEYS = Object.freeze([
  'display_name', 'currency', 'amount_unit', 'amount_precision', 'observation_days',
  'cohort_enrolled_count', 'cohort_mature_count', 'cohort_immature_count', 'products',
]);

const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const opaque = value => typeof value === 'string' && OPAQUE.test(value);
const sha256 = value => typeof value === 'string' && SHA.test(value);
const rfc3339 = value => typeof value === 'string' && RFC3339.test(value);
const count = value => typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= JS_MAX_SAFE_INTEGER;
const days = value => value === 30 || value === 60 || value === 90;

export function isForeignFamily(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const schema = value.schema_version;
  if (schema === 'analytics-b0/v1' || schema === 'analytics-run-b0/v1') return true;
  if (schema === 'analytics-channel-followup/v1' || schema === 'analytics-saved-analysis/v1') return true;
  if (value.query_id === 'channel_first_observed_followup') return true;
  return isForeignFamily(value.result) || isForeignFamily(value.facts);
}

function decodeFacts(value, observationDays) {
  if (!exact(value, FACT_KEYS) || value.display_name !== '首购商品路径 / N日正装转化'
    || value.currency !== 'CNY' || value.amount_unit !== 'minor' || value.amount_precision !== 'integer_fen'
    || value.observation_days !== observationDays || !Array.isArray(value.products)) return null;
  if (!count(value.cohort_enrolled_count) || !count(value.cohort_mature_count) || !count(value.cohort_immature_count)) return null;
  if (value.cohort_enrolled_count !== value.cohort_mature_count + value.cohort_immature_count) return null;
  return value;
}

export function decodeSavedAnalysis(value) {
  if (isForeignFamily(value) || !exact(value, ANALYSIS_KEYS)) return null;
  if (value.schema_version !== SAVED_ANALYSIS_SCHEMA || !ANALYSIS_ID.test(value.analysis_id)
    || !Number.isInteger(value.version) || value.version < 1
    || typeof value.title !== 'string' || !value.title || value.title.length > 120
    || value.query_ref?.query_id !== 'first_purchase_product_path'
    || value.query_ref?.query_version !== 'first-purchase-path-query/v1'
    || !Array.isArray(value.metric_refs) || value.metric_refs.length !== 1
    || value.metric_refs[0]?.metric_id !== 'first_purchase_product_n_day_finished'
    || value.data_mode !== 'SNAPSHOT' || !exact(value.snapshot, SNAPSHOT_KEYS)
    || value.snapshot.run_id !== value.created_from_run_id || !sha256(value.snapshot.evidence_digest)
    || value.snapshot.data_snapshot_ref !== 'synthetic-first-purchase-v1'
    || !rfc3339(value.snapshot.as_of) || value.data_version !== 'synthetic-first-purchase-data/v1'
    || !sha256(value.filter_hash) || !Array.isArray(value.limitations) || value.limitations.length < 1
    || !rfc3339(value.created_at) || value.finite_mock !== true || value.http_api !== HTTP_API
    || value.visibility !== 'PRIVATE' || value.endorsement !== 'PERSONAL'
    || !opaque(value.created_from_run_id) || !opaque(value.owner_id)
    || value.visual_spec?.schema_version !== VISUAL_SCHEMA || value.visual_spec?.kind !== 'TABLE') return null;
  const facts = decodeFacts(value.facts, value.filters?.observation_days);
  if (!facts || !days(value.filters.observation_days)) return null;
  return value;
}

export function decodeSavedAnalysisList(value) {
  if (!Array.isArray(value) || value.length > 50) return null;
  const items = [];
  for (const row of value) {
    if (isForeignFamily(row) || row.schema_version !== SAVED_ANALYSIS_SCHEMA
      || !ANALYSIS_ID.test(row.analysis_id) || row.query_id !== 'first_purchase_product_path'
      || !days(row.observation_days) || row.data_mode !== 'SNAPSHOT' || row.http_api !== HTTP_API) {
      return null;
    }
    items.push(row);
  }
  return items;
}

export function renderSavedAnalysisHtml(view) {
  const heading = `<h2>${view.heading}</h2>`;
  if (view.kind === 'error' || view.kind === 'empty') return heading + `<p>${view.message}</p>`;
  if (view.kind === 'list') {
    const items = (view.items || []).map(item => `<li data-analysis-id="${item.analysis_id}">${item.title}</li>`).join('');
    return heading + `<ul data-testid="analytics-first-purchase-saved-analysis-list">${items}</ul>`;
  }
  if (view.kind === 'detail') {
    return heading + `<h3>${view.title}</h3><p>${view.totals}</p><small>${view.evidence}</small>`;
  }
  return heading + `<p>${view.saveHint}</p>`;
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
  const base = {
    heading: COPY.heading,
    sessionId: sessionId ?? null,
    modelAvailable: modelAvailable === true,
    http: COPY.http,
    noSession: COPY.noSession,
  };
  if (error && (error.status === 403 || error.status === 404)) {
    return { ...base, kind: 'error', message: COPY.unauthorized, canSave: false, joinEnabled: false };
  }
  if (analysis != null && decoded == null) {
    return { ...base, kind: 'error', message: '结果无法识别或版本不支持；不推断分析成功。', canSave: false, joinEnabled: false };
  }
  if (decoded) {
    const conversion = decoded.facts.products[0]
      ? formatRatioPercent(decoded.facts.products[0].finished_conversion_ratio)
      : '—';
    const empty = formatEmptyReason(decoded.facts.products[0]?.empty_reason ?? null) || { code: null, text: '' };
    return {
      ...base,
      kind: 'detail',
      title: decoded.title,
      badge: COPY.snapshot,
      version: decoded.version,
      condition: `FIXED ${decoded.filters.cohort_window.start_date} → ${decoded.filters.cohort_window.end_date} · N=${decoded.filters.observation_days}`,
      evidence: `run ${decoded.snapshot.run_id} · digest ${decoded.snapshot.evidence_digest}`,
      totals: `入组 ${decoded.facts.cohort_enrolled_count} / 成熟 ${decoded.facts.cohort_mature_count} · 正装转化 ${conversion}`,
      empty,
      saveState: saveState === 'saved' ? 'saved' : 'idle',
      joinHint: COPY.joinUnavailable,
      synthetic: COPY.synthetic,
      canSave: runStatus === 'SUCCEEDED',
    };
  }
  if (items && items.length === 0) return { ...base, kind: 'empty', message: COPY.empty };
  if (items) {
    return {
      ...base,
      kind: 'list',
      items: items.map(item => ({
        analysis_id: item.analysis_id,
        title: item.title,
        version: item.version,
        badge: COPY.snapshot,
        summary: `N=${item.observation_days}`,
      })),
    };
  }
  return {
    ...base,
    kind: 'save-panel',
    saveState: saveState === 'saved' ? 'saved' : 'idle',
    saveHint: runStatus === 'SUCCEEDED' ? COPY.saveHint : COPY.cannotSave,
    canSave: runStatus === 'SUCCEEDED',
  };
}
