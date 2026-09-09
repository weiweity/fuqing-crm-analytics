/** First-purchase native request/receipt codec. Does not recompute hashes or invent口径. */
export const FIRST_PURCHASE_TOOL_NAME = 'analytics_first_purchase_query';
export const FIRST_PURCHASE_SCHEMA = 'analytics-first-purchase-path/v1';
export const FIRST_PURCHASE_RECEIPT_SCHEMA = 'analytics-run-first-purchase-native-receipt/v1';
export const FIRST_PURCHASE_KERNEL_URL = 'http://127.0.0.1:4315/internal/native/first-purchase';
export const FIRST_PURCHASE_RECEIPT_LIMIT = 1048576 + 4096;
export const JS_MAX_SAFE_INTEGER = 9007199254740991;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const RFC3339 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
const OPAQUE = /^[A-Za-z0-9_.:-]{1,128}$/;
const SHA = /^[0-9a-f]{64}$/;
const REQUEST_KEYS = Object.freeze([
  'schema_version', 'query_id', 'query_version', 'metric_id', 'metric_version',
  'cohort_window', 'observation_days', 'data_snapshot_ref', 'timezone',
  'channel_ids', 'cohort_ref', 'product_ids', 'exclude_low_price', 'comparison',
]);
const WINDOW_KEYS = Object.freeze(['kind', 'start_date', 'end_date']);
const RECEIPT_KEYS = Object.freeze([
  'schema_version', 'run_id', 'request_id', 'call_id', 'attempt_id', 'step_id',
  'disposition', 'run_status', 'result',
]);
const RESULT_KEYS = Object.freeze([
  'schema_version', 'answer_mode', 'query_id', 'query_version', 'metric_id', 'metric_version',
  'data_version', 'hash_version', 'contains_real_data', 'data_source', 'data_snapshot_ref',
  'as_of', 'resolved_filters', 'filter_hash', 'status', 'reason_code', 'missing_product_ids',
  'facts', 'limitations',
]);
const FILTER_KEYS = Object.freeze([
  'schema_version', 'query_id', 'query_version', 'metric_id', 'metric_version', 'data_version',
  'hash_version', 'cohort_window_kind', 'resolved_cohort_start', 'resolved_cohort_end',
  'observation_days', 'data_snapshot_ref', 'as_of', 'timezone', 'channel_ids', 'cohort_ref',
  'product_ids', 'exclude_low_price', 'comparison', 'permission_scope', 'data_digest', 'filter_hash',
]);
const ROW_KEYS = Object.freeze([
  'product_id', 'role', 'enrolled_count', 'mature_count', 'immature_count',
  'finished_conversion_count', 'finished_conversion_ratio', 'empty_reason',
]);
const FACT_KEYS = Object.freeze([
  'display_name', 'currency', 'amount_unit', 'amount_precision', 'observation_days',
  'cohort_enrolled_count', 'cohort_mature_count', 'cohort_immature_count', 'products',
]);
const STATUSES = new Set(['QUEUED', 'RUNNING', 'NEEDS_INPUT', 'SUCCEEDED', 'FAILED', 'CANCELLING', 'CANCELLED', 'UNKNOWN']);
const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const opaque = value => typeof value === 'string' && OPAQUE.test(value);
const sha256 = value => typeof value === 'string' && SHA.test(value);
const isoDate = value => typeof value === 'string' && DATE.test(value);
const rfc3339 = value => typeof value === 'string' && RFC3339.test(value);
const count = value => typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= JS_MAX_SAFE_INTEGER;
const ratio = value => value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1);
const days = value => value === 30 || value === 60 || value === 90;
const channels = value => Array.isArray(value) && value.every(item => item === 'A' || item === 'B')
  && new Set(value).size === value.length;

function decodeProductRow(value) {
  if (!exact(value, ROW_KEYS)) return null;
  if (!opaque(value.product_id) || (value.role !== 'sample' && value.role !== 'finished')) return null;
  if (!count(value.enrolled_count) || !count(value.mature_count) || !count(value.immature_count)
    || !count(value.finished_conversion_count) || !ratio(value.finished_conversion_ratio)) return null;
  if (value.enrolled_count !== value.mature_count + value.immature_count) return null;
  if (value.finished_conversion_count > value.mature_count) return null;
  if (value.mature_count === 0) {
    if (value.finished_conversion_count !== 0 || value.finished_conversion_ratio !== null) return null;
    if (value.empty_reason !== 'EMPTY_MATURE_COHORT') return null;
    return value;
  }
  if (value.empty_reason !== null || value.finished_conversion_ratio === null) return null;
  if (value.finished_conversion_ratio !== value.finished_conversion_count / value.mature_count) return null;
  return value;
}

function decodeFacts(value, observationDays) {
  if (!exact(value, FACT_KEYS)) return null;
  if (value.display_name !== '首购商品路径 / N日正装转化' || value.currency !== 'CNY'
    || value.amount_unit !== 'minor' || value.amount_precision !== 'integer_fen'
    || value.observation_days !== observationDays
    || !count(value.cohort_enrolled_count) || !count(value.cohort_mature_count)
    || !count(value.cohort_immature_count) || !Array.isArray(value.products)) return null;
  if (value.cohort_enrolled_count !== value.cohort_mature_count + value.cohort_immature_count) return null;
  const ids = [];
  for (const row of value.products) {
    const decoded = decodeProductRow(row);
    if (!decoded || ids.includes(decoded.product_id)) return null;
    ids.push(decoded.product_id);
  }
  return value;
}

function decodeFilters(value) {
  if (!exact(value, FILTER_KEYS)) return null;
  if (value.schema_version !== FIRST_PURCHASE_SCHEMA || value.query_id !== 'first_purchase_product_path'
    || value.query_version !== 'first-purchase-path-query/v1'
    || value.metric_id !== 'first_purchase_product_n_day_finished'
    || value.metric_version !== 'first-purchase-path-metric/v1'
    || value.data_version !== 'synthetic-first-purchase-data/v1'
    || value.hash_version !== 'first-purchase-path-filter-hash/v1'
    || value.cohort_window_kind !== 'FIXED' || !days(value.observation_days)
    || value.data_snapshot_ref !== 'synthetic-first-purchase-v1' || value.timezone !== 'Asia/Shanghai'
    || !rfc3339(value.resolved_cohort_start) || !rfc3339(value.resolved_cohort_end) || !rfc3339(value.as_of)
    || !channels(value.channel_ids) || value.channel_ids.length === 0
    || value.cohort_ref !== null || !Array.isArray(value.product_ids) || value.product_ids.length !== 0
    || value.exclude_low_price !== false || value.comparison !== null
    || !opaque(value.permission_scope) || !sha256(value.data_digest) || !sha256(value.filter_hash)) return null;
  return value;
}

function decodeResult(value) {
  if (!exact(value, RESULT_KEYS)) return null;
  if (value.schema_version !== FIRST_PURCHASE_SCHEMA || value.answer_mode !== 'DETERMINISTIC_TOOL'
    || value.query_id !== 'first_purchase_product_path' || value.query_version !== 'first-purchase-path-query/v1'
    || value.metric_id !== 'first_purchase_product_n_day_finished' || value.metric_version !== 'first-purchase-path-metric/v1'
    || value.data_version !== 'synthetic-first-purchase-data/v1' || value.hash_version !== 'first-purchase-path-filter-hash/v1'
    || value.contains_real_data !== false || value.data_source !== 'SYNTHETIC_SNAPSHOT'
    || value.data_snapshot_ref !== 'synthetic-first-purchase-v1' || !rfc3339(value.as_of)
    || !sha256(value.filter_hash) || !Array.isArray(value.limitations) || value.limitations.length < 1
    || value.limitations.some(item => typeof item !== 'string' || !item)) return null;
  const filters = decodeFilters(value.resolved_filters);
  if (!filters || filters.filter_hash !== value.filter_hash || filters.as_of !== value.as_of) return null;
  if (value.status === 'REJECTED') {
    if (value.reason_code !== 'MISSING_PRODUCT_ROLE' || value.facts !== null) return null;
    if (!Array.isArray(value.missing_product_ids) || value.missing_product_ids.length < 1) return null;
    const dumped = JSON.stringify(value);
    if (dumped.includes('finished_conversion_ratio') || dumped.includes('finished_conversion_count')) return null;
    return value;
  }
  if (value.status !== 'OK' || value.reason_code !== null) return null;
  if (!Array.isArray(value.missing_product_ids) || value.missing_product_ids.length !== 0) return null;
  const facts = decodeFacts(value.facts, filters.observation_days);
  if (!facts) return null;
  return value;
}

export function decodeFirstPurchaseRequest(value) {
  if (!exact(value, REQUEST_KEYS) || value.schema_version !== FIRST_PURCHASE_SCHEMA
    || value.query_id !== 'first_purchase_product_path' || value.query_version !== 'first-purchase-path-query/v1'
    || value.metric_id !== 'first_purchase_product_n_day_finished' || value.metric_version !== 'first-purchase-path-metric/v1'
    || !exact(value.cohort_window, WINDOW_KEYS) || value.cohort_window.kind !== 'FIXED'
    || !isoDate(value.cohort_window.start_date) || !isoDate(value.cohort_window.end_date)
    || value.cohort_window.start_date >= value.cohort_window.end_date || !days(value.observation_days)
    || value.data_snapshot_ref !== 'synthetic-first-purchase-v1' || value.timezone !== 'Asia/Shanghai'
    || !channels(value.channel_ids) || value.cohort_ref !== null
    || !Array.isArray(value.product_ids) || value.product_ids.length !== 0
    || value.exclude_low_price !== false || value.comparison !== null) return null;
  if ('owner' in value || 'permission_scope' in value || 'facts' in value) return null;
  return { ...value, cohort_window: { ...value.cohort_window }, channel_ids: [...value.channel_ids], product_ids: [] };
}

export function receiptMatchesRequest(receipt, request, { requestId, callId } = {}) {
  if (!receipt || !request) return false;
  if (requestId != null && receipt.request_id !== requestId) return false;
  if (callId != null && receipt.call_id !== callId) return false;
  if (receipt.disposition === 'IN_FLIGHT') return true;
  const result = receipt.result;
  if (!result) return false;
  if (result.query_id !== request.query_id || result.query_version !== request.query_version) return false;
  if (result.metric_id !== request.metric_id || result.metric_version !== request.metric_version) return false;
  if (result.data_snapshot_ref !== request.data_snapshot_ref) return false;
  if (result.resolved_filters?.observation_days !== request.observation_days) return false;
  return true;
}

export function decodeFirstPurchaseReceipt(value) {
  if (!exact(value, RECEIPT_KEYS) || value.schema_version !== FIRST_PURCHASE_RECEIPT_SCHEMA
    || !opaque(value.run_id) || !opaque(value.request_id) || !opaque(value.call_id)
    || !opaque(value.attempt_id) || !STATUSES.has(value.run_status)) return null;
  if (value.disposition === 'IN_FLIGHT') {
    if (value.result !== null || value.step_id !== null) return null;
    if (value.run_status !== 'QUEUED' && value.run_status !== 'RUNNING'
      && value.run_status !== 'CANCELLING' && value.run_status !== 'UNKNOWN') return null;
    return { ...value, result: null, step_id: null };
  }
  if (value.disposition !== 'EXECUTE' && value.disposition !== 'REUSE_RESULT') return null;
  if (!opaque(value.step_id)) return null;
  const result = decodeResult(value.result);
  if (!result) return null;
  return { ...value, result };
}

export function firstPurchaseSaveBinding(runId) {
  if (!opaque(runId)) return null;
  return Object.freeze({ created_from_run_id: runId, source: 'first-purchase-run' });
}

export async function readBoundedJson(response, limit) {
  const reader = response.body?.getReader();
  if (!reader) throw new Error('query kernel has no body');
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) { await reader.cancel(); throw new Error('query kernel response too large'); }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  return JSON.parse(new TextDecoder().decode(Buffer.concat(chunks.map(item => Buffer.from(item)))));
}
