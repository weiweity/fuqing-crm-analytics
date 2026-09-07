/** Query request/receipt codec. Shape/numeric/null only; does not recompute backend hashes. */
export const QUERY_TOOL_NAME = 'analytics_channel_followup_query';
export const QUERY_SCHEMA = 'analytics-channel-followup/v1';
export const QUERY_RECEIPT_SCHEMA = 'analytics-run-channel-followup-native-receipt/v1';
export const QUERY_KERNEL_URL = 'http://127.0.0.1:4315/internal/native/channel-followup';
export const QUERY_RECEIPT_LIMIT = 1048576 + 4096;
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
const RECEIPT_KEYS = Object.freeze(['schema_version', 'run_id', 'attempt_id', 'step_id', 'disposition', 'result']);
const RESULT_KEYS = Object.freeze([
  'schema_version', 'answer_mode', 'query_id', 'query_version', 'metric_id', 'metric_version',
  'data_version', 'hash_version', 'contains_real_data', 'data_source', 'data_snapshot_ref',
  'as_of', 'resolved_filters', 'filter_hash', 'facts', 'limitations',
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
const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const opaque = value => typeof value === 'string' && OPAQUE.test(value);
const sha256 = value => typeof value === 'string' && SHA.test(value);
const isoDate = value => typeof value === 'string' && DATE.test(value);
const rfc3339 = value => typeof value === 'string' && RFC3339.test(value);
const count = value => typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= JS_MAX_SAFE_INTEGER;
const ratio = value => value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1);
const net = value => value === null || count(value);
const days = value => value === 30 || value === 60 || value === 90;
const channels = value => Array.isArray(value) && value.every(item => item === 'A' || item === 'B')
  && new Set(value).size === value.length;

function decodeCounts(value, channelId) {
  if (!exact(value, channelId ? ['channel_id', ...COUNT_KEYS] : COUNT_KEYS)) return null;
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

function decodeFilters(value) {
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

function decodeResult(value) {
  if (!exact(value, RESULT_KEYS)) return null;
  if (value.schema_version !== QUERY_SCHEMA || value.answer_mode !== 'DETERMINISTIC_TOOL'
    || value.query_id !== 'channel_first_observed_followup' || value.query_version !== 'channel-followup-query/v1'
    || value.metric_id !== 'channel_first_observed_n_day_repeat' || value.metric_version !== 'channel-followup-metric/v1'
    || value.data_version !== 'synthetic-channel-followup-data/v1' || value.hash_version !== 'channel-followup-filter-hash/v1'
    || value.contains_real_data !== false || value.data_source !== 'SYNTHETIC_SNAPSHOT'
    || value.data_snapshot_ref !== 'synthetic-channel-followup-v1' || !rfc3339(value.as_of)
    || !sha256(value.filter_hash) || !Array.isArray(value.limitations) || value.limitations.length < 1
    || value.limitations.some(item => typeof item !== 'string' || !item)) return null;
  const filters = decodeFilters(value.resolved_filters);
  if (!filters || filters.filter_hash !== value.filter_hash || filters.as_of !== value.as_of) return null;
  const facts = value.facts;
  if (!exact(facts, FACT_KEYS) || facts.display_name !== '首次观察到的渠道 / N日二单率'
    || facts.currency !== 'CNY' || facts.amount_unit !== 'minor' || facts.amount_precision !== 'integer_fen'
    || facts.observation_days !== filters.observation_days || !Array.isArray(facts.channels)) return null;
  const totals = decodeCounts(facts.totals);
  if (!totals) return null;
  const ids = [];
  for (const row of facts.channels) {
    const decoded = decodeCounts(row, true);
    if (!decoded || ids.includes(decoded.channel_id)) return null;
    ids.push(decoded.channel_id);
  }
  if (ids.length !== filters.channel_ids.length || ids.some(id => !filters.channel_ids.includes(id))) return null;
  return value;
}

export function decodeQueryRequest(value) {
  if (!exact(value, REQUEST_KEYS) || value.schema_version !== QUERY_SCHEMA
    || value.query_id !== 'channel_first_observed_followup' || value.query_version !== 'channel-followup-query/v1'
    || value.metric_id !== 'channel_first_observed_n_day_repeat' || value.metric_version !== 'channel-followup-metric/v1'
    || !exact(value.cohort_window, WINDOW_KEYS) || value.cohort_window.kind !== 'FIXED'
    || !isoDate(value.cohort_window.start_date) || !isoDate(value.cohort_window.end_date)
    || value.cohort_window.start_date >= value.cohort_window.end_date || !days(value.observation_days)
    || value.data_snapshot_ref !== 'synthetic-channel-followup-v1' || value.timezone !== 'Asia/Shanghai'
    || !channels(value.channel_ids) || value.cohort_ref !== null
    || !Array.isArray(value.product_ids) || value.product_ids.length !== 0
    || value.exclude_low_price !== false || value.comparison !== null) return null;
  return { ...value, cohort_window: { ...value.cohort_window }, channel_ids: [...value.channel_ids], product_ids: [] };
}

export function decodeQueryReceipt(value) {
  if (!exact(value, RECEIPT_KEYS) || value.schema_version !== QUERY_RECEIPT_SCHEMA
    || !opaque(value.run_id) || !opaque(value.attempt_id) || !opaque(value.step_id)
    || (value.disposition !== 'EXECUTE' && value.disposition !== 'REUSE_RESULT')) return null;
  const result = decodeResult(value.result);
  if (!result) return null;
  return { ...value, result };
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
      if (size > limit) { await reader.cancel(); throw new Error('query receipt exceeds bound'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
