/** Decode C0 board/result/error documents. Reject extra keys and illegal patches. */

const OPAQUE = /^[A-Za-z0-9_.:-]{1,128}$/;
const SHA = /^[0-9a-f]{64}$/;
const LAYOUT_MODES = new Set(['ONE_BOARD_MULTI_BLOCK', 'BATCH_MULTI_BOARD']);
const NAMESPACES = new Set(['analytics-cockpit/v1', 'competition-board/v1']);
const COMPAT = new Set(['READ_OLD_SNAPSHOT', 'ISOLATED_NEW', 'REJECT_UNSUPPORTED_VERSION']);
const INTENTS = new Set(['STYLE_ONLY', 'FILTER_CHANGE', 'STRUCTURE']);
const COMPLETENESS = new Set(['COMPLETE', 'EMPTY', 'INSUFFICIENT', 'UNSUPPORTED', 'FAILED', 'PARTIAL']);
const RECEIPT_STATUS = new Set(['SUCCEEDED', 'FAILED', 'CONFLICT']);
const BATCH_STATUS = new Set(['SUCCEEDED', 'PARTIAL', 'FAILED']);

const isObj = value => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
const opaque = value => typeof value === 'string' && OPAQUE.test(value);
const sha256 = value => typeof value === 'string' && SHA.test(value);
const intGte1 = value => typeof value === 'number' && Number.isInteger(value) && value >= 1;
const keysOf = value => Object.keys(value).sort();
const has = (value, keys) => keys.every(key => Object.hasOwn(value, key));

export function decodeCompetitionError(value) {
  const error = isObj(value) && isObj(value.error) ? value.error : value;
  if (!isObj(error) || error.schema_version !== 'competition-error/v1') return null;
  if (typeof error.code !== 'string' || !error.code) return null;
  if (typeof error.message !== 'string' || !error.message) return null;
  if (typeof error.request_id !== 'string' || !error.request_id) return null;
  if (typeof error.retryable !== 'boolean') return null;
  if (typeof error.http_status !== 'number') return null;
  if (error.maps_to !== 'backend.contracts.analytics.AnalyticsErrorDetail') return null;
  return error;
}

export function decodeCompetitionResultRef(value) {
  if (!isObj(value) || value.schema_version !== 'competition-result/v1') return null;
  if (!opaque(value.result_id) || !COMPLETENESS.has(value.completeness)) return null;
  if (value.data_mode !== 'SNAPSHOT' || value.contains_real_data !== false) return null;
  if (typeof value.query_id !== 'string' || typeof value.query_version !== 'string') return null;
  if (!Array.isArray(value.limitations) || value.limitations.length < 1) return null;
  if (!isObj(value.resolved_condition) || value.resolved_condition.metric_type !== 'GSV') return null;
  if (value.resolved_condition.timezone !== 'Asia/Shanghai') return null;
  return value;
}

export function canEndorse(result) {
  return Boolean(result && result.completeness === 'COMPLETE' && result.contains_real_data === false
    && opaque(result.result_id) && opaque(result.run_id) && sha256(result.evidence_digest));
}

export function toEndorsedResultRef(result) {
  if (!canEndorse(result)) return null;
  return {
    analysis_id: result.analysis_id ?? null,
    completeness: 'COMPLETE',
    evidence_digest: result.evidence_digest,
    result_id: result.result_id,
    run_id: result.run_id,
  };
}

export function decodeCompetitionBoardSpec(value) {
  if (!isObj(value) || value.schema_version !== 'competition-board/v1') return null;
  if (!opaque(value.board_id) || !intGte1(value.version) || !intGte1(value.base_version)) return null;
  if (typeof value.title !== 'string' || !opaque(value.owner_id)) return null;
  if (value.visibility !== 'PRIVATE' || value.data_mode !== 'SNAPSHOT') return null;
  if (value.existing_dashboard_schema !== 'analytics-cockpit/v1') return null;
  if (!LAYOUT_MODES.has(value.layout_mode) || !NAMESPACES.has(value.data_namespace)) return null;
  if (!COMPAT.has(value.snapshot_compat)) return null;
  if (typeof value.preview !== 'boolean' || typeof value.persisted !== 'boolean') return null;
  if (!Array.isArray(value.block_ids) || !value.block_ids.every(opaque)) return null;
  if (!Array.isArray(value.affected_block_ids) || !value.affected_block_ids.every(opaque)) return null;
  if (!Array.isArray(value.limitations) || value.limitations.length < 1) return null;
  return value;
}

export function decodeCompetitionPatchRequest(value) {
  if (!isObj(value) || value.schema_version !== 'competition-board-patch/v1') return null;
  if (!opaque(value.board_id) || !opaque(value.attempt_id) || !intGte1(value.base_version)) return null;
  if (typeof value.idempotency_key !== 'string' || !value.idempotency_key) return null;
  if (!INTENTS.has(value.intent)) return null;
  if (value.block_id != null && !opaque(value.block_id)) return null;
  if (value.intent === 'STYLE_ONLY' && value.filter_change) return null;
  if (value.intent === 'FILTER_CHANGE' && !value.filter_change) return null;
  if (looksLikeIllegalScript(value)) return null;
  return value;
}

export function looksLikeIllegalScript(value) {
  const text = JSON.stringify(value ?? '');
  return /<script|javascript:|onerror\s*=|onload\s*=/i.test(text);
}

export function decodeBoardPatchRequest(value) {
  if (value?.schema_version !== 'competition-board-chart-patch/v1') return decodeCompetitionPatchRequest(value);
  const fields = ['schema_version', 'board_id', 'block_id', 'base_version', 'attempt_id', 'idempotency_key', 'intent', 'chart_type'];
  if (!isObj(value) || Object.keys(value).some(key => !fields.includes(key)) || !has(value, fields)) return null;
  if (![value.board_id, value.block_id, value.attempt_id].every(opaque) || !Number.isSafeInteger(value.base_version) || value.base_version < 1) return null;
  if (typeof value.idempotency_key !== 'string' || !value.idempotency_key.length || value.idempotency_key.length > 200) return null;
  if (value.intent !== 'STYLE_ONLY' || !['TABLE', 'BAR', 'LINE', 'METRIC', 'EVIDENCE'].includes(value.chart_type)) return null;
  return value;
}

export function decodeCompetitionBatchRequest(value) {
  if (!isObj(value) || value.schema_version !== 'competition-board-batch/v1') return null;
  if (!opaque(value.batch_id) || !LAYOUT_MODES.has(value.layout_mode)) return null;
  if (!Array.isArray(value.operations) || value.operations.length < 1 || value.operations.length > 20) return null;
  for (const op of value.operations) {
    if (!opaque(op.operation_id) || !opaque(op.idempotency_key)) return null;
    if (!LAYOUT_MODES.has(op.layout_mode) || typeof op.title !== 'string') return null;
    if (!sha256(op.request_fingerprint)) return null;
    if (!Array.isArray(op.endorsed_result_refs) || op.endorsed_result_refs.length < 1) return null;
    if (!op.endorsed_result_refs.every(row => row.completeness === 'COMPLETE' && opaque(row.result_id))) return null;
  }
  return value;
}

export function decodeCompetitionBatchReceipt(value) {
  if (!isObj(value) || value.schema_version !== 'competition-board-batch/v1') return null;
  if (!opaque(value.batch_id) || !BATCH_STATUS.has(value.status)) return null;
  if (!Array.isArray(value.items)) return null;
  if (!value.items.every(row => opaque(row.operation_id) && RECEIPT_STATUS.has(row.status))) return null;
  return value;
}

export function formatResultRowCount(result) {
  if (!result || result.completeness === 'EMPTY') return '—';
  const n = result.row_count ?? result.page?.total;
  return typeof n === 'number' && Number.isFinite(n) ? String(n) : '—';
}

function displayValue(value) {
  if (value == null || value === '') return '—';
  return String(value);
}

function periodRange(period) {
  if (!period?.start_date || !period?.end_date) return '—';
  return `${period.start_date}–${period.end_date}`;
}

export function conditionChips(result) {
  const resolved = result?.resolved_condition;
  if (!resolved) return [];
  return [
    { id: 'metric', label: '指标', value: displayValue(resolved.metric_type) },
    { id: 'current', label: '本期', value: periodRange(resolved.current_period) },
    { id: 'compare', label: '对比', value: `${displayValue(resolved.comparison_mode)} ${periodRange(resolved.comparison_period)}` },
    { id: 'cutoff', label: 'cutoff', value: displayValue(resolved.cutoff) },
    { id: 'sample', label: '小样', value: displayValue(resolved.sample_mode) },
    { id: 'tz', label: '时区', value: displayValue(resolved.timezone) },
  ];
}

export function evidenceFields(result) {
  const resolved = result?.resolved_condition;
  return {
    asOf: resolved?.as_of,
    metricVersion: result?.metric_version ?? resolved?.rule_version,
    dataVersion: resolved?.data_version,
    digest: result?.evidence_digest ?? undefined,
    source: resolved?.source_tense,
    limitations: result?.limitations ?? [],
    unknowns: (resolved?.unknown_flags ?? []).map(row => row.code),
  };
}

export function defaultBlockLayout(index) {
  return { x: (index % 2) * 6, y: Math.floor(index / 2) * 4, w: 6, h: 4 };
}

export { isObj, opaque, sha256, keysOf, has, INTENTS, LAYOUT_MODES };
