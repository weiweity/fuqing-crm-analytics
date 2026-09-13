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
  if (!isObj(value) || !['competition-result/v1', 'competition-computed-result/v1'].includes(value.schema_version)) return null;
  if (!opaque(value.result_id) || !COMPLETENESS.has(value.completeness)) return null;
  if (value.data_mode !== 'SNAPSHOT' || value.contains_real_data !== false) return null;
  if (typeof value.query_id !== 'string' || typeof value.query_version !== 'string') return null;
  if (!Array.isArray(value.limitations) || value.limitations.length < 1) return null;
  if (!isObj(value.resolved_condition) || value.resolved_condition.metric_type !== 'GSV') return null;
  if (value.resolved_condition.timezone !== 'Asia/Shanghai') return null;
  if (value.schema_version === 'competition-computed-result/v1' && !validComputedResult(value)) return null;
  return value;
}

function validPurchaseFrequency(facts) {
  const data = facts.current_purchase_frequency;
  if (!isObj(data) || keysOf(data).join(',') !== 'basis,entity,stages,status,unavailable_reason'
    || data.basis !== 'CURRENT_PERIOD_EFFECTIVE_ORDERS' || data.entity !== 'USER_ID' || !Array.isArray(data.stages)) return false;
  const unavailable = facts.current.through_date === null;
  const reason = unavailable ? 'PERIOD_UNAVAILABLE' : facts.current.customer_count_unavailable_reason;
  if (data.status === 'UNAVAILABLE') return data.stages.length === 0
    && ['PERIOD_UNAVAILABLE', 'AMBIGUOUS_ORDER_CUSTOMER', 'INVALID_CUSTOMER'].includes(data.unavailable_reason)
    && data.unavailable_reason === reason;
  if (data.status !== 'AVAILABLE' || reason !== null || data.unavailable_reason !== null || data.stages.length !== 3) return false;
  const counts = data.stages.map(stage => stage?.customer_count);
  return data.stages.every((stage, index) => isObj(stage) && keysOf(stage).join(',') === 'customer_count,minimum_orders'
    && stage.minimum_orders === index + 1 && Number.isSafeInteger(stage.customer_count) && stage.customer_count >= 0
    && (index === 0 || stage.customer_count <= counts[index - 1]))
    && counts[0] === facts.current.customer_count && counts.reduce((sum, count) => sum + count, 0) <= facts.current.order_count;
}

function validComputedResult(value) {
  const number = v => typeof v === 'number' && Number.isFinite(v);
  const count = v => Number.isSafeInteger(v) && v >= 0;
  const day = v => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v);
  const v5 = value.facts?.schema_version === 'competition-gsv-facts/v5';
  const customers = p => v5 && p.customer_count === null
    ? p.through_date !== null && ['AMBIGUOUS_ORDER_CUSTOMER', 'INVALID_CUSTOMER'].includes(p.customer_count_unavailable_reason)
    : count(p.customer_count) && p.customer_count <= p.order_count
      && (v5 ? p.customer_count_unavailable_reason === null : !Object.hasOwn(p, 'customer_count_unavailable_reason'));
  const period = (p, expected) => isObj(p) && isObj(p.requested_period) && isObj(expected)
    && p.requested_period.start_date === expected.start_date && p.requested_period.end_date === expected.end_date
    && count(p.order_count) && customers(p)
    && (p.through_date === null ? p.gsv === null && p.order_count === 0 && p.customer_count === 0
      : day(p.through_date) && p.through_date >= expected.start_date && p.through_date <= expected.end_date && number(p.gsv) && p.gsv >= 0);
  const facts = value.facts;
  const version = facts?.schema_version;
  const factsRef = version === 'competition-gsv-facts/v5'
    ? 'backend.contracts.competition_computed.CompetitionGsvFactsV5'
    : version === 'competition-gsv-facts/v4'
    ? 'backend.contracts.competition_computed.CompetitionGsvFactsV4'
    : version === 'competition-gsv-facts/v3'
    ? 'backend.contracts.competition_computed.CompetitionGsvFactsV3'
    : version === 'competition-gsv-facts/v2'
    ? 'backend.contracts.competition_computed.CompetitionGsvFactsV2'
    : version === 'competition-gsv-facts/v1' ? 'backend.contracts.competition_computed.CompetitionGsvFacts' : null;
  if (!factsRef || value.facts_schema_ref !== factsRef || value.existing_result_schema !== version) return false;
  if (version !== 'competition-gsv-facts/v1' ? !validMoneyUnit(facts.money_unit) : Object.hasOwn(facts, 'money_unit')) return false;
  if (value.execution_kind !== 'TOOL_COMPUTATION' || value.query_id !== 'competition_gsv_comparison'
    || value.query_version !== 'competition-gsv-query/v1' || value.metric_version !== 'competition-gsv-metric/v1'
    || !opaque(value.run_id)
    || (value.analysis_id != null && !opaque(value.analysis_id)) || !sha256(value.data_digest) || !sha256(value.evidence_digest)
    || value.primary_result_ref !== value.result_id || !isObj(facts)
    || facts.metric_type !== 'GSV' || !period(facts.current, value.resolved_condition.current_period)
    || !period(facts.comparison, value.resolved_condition.comparison_period)) return false;
  if (['competition-gsv-facts/v3', 'competition-gsv-facts/v4', 'competition-gsv-facts/v5'].includes(version) ? !validDailySeries(facts.current_daily, facts.current)
    : Object.hasOwn(facts, 'current_daily')) return false;
  if (['competition-gsv-facts/v4', 'competition-gsv-facts/v5'].includes(version) ? !validChannelBridge(facts) : Object.hasOwn(facts, 'channel_bridge')) return false;
  if (version === 'competition-gsv-facts/v5' ? !validPurchaseFrequency(facts) : Object.hasOwn(facts, 'current_purchase_frequency')) return false;
  const c = facts.current.gsv; const p = facts.comparison.gsv;
  if (c === null || p === null) return value.completeness === 'EMPTY' && value.row_count === 0 && value.page === null
    && ['NO_CURRENT_MONTH_DATA', 'PERIOD_AFTER_AS_OF'].includes(value.empty_reason)
    && facts.difference === null && facts.change_ratio === null && facts.change_ratio_unavailable_reason === 'PERIOD_UNAVAILABLE';
  if (value.completeness !== 'COMPLETE' || value.row_count !== 2 || value.empty_reason !== null
    || value.page?.total !== 2 || value.page?.complete !== true || value.page?.checksum !== value.evidence_digest
    // The producer publishes the period difference as Python's round(current - comparison, 4),
    // exactly as each channel difference is published, so the same rounding rule decides it.
    // The whole-period window this replaces also accepted a neighbouring four-decimal value.
    || !number(facts.difference) || facts.difference !== round4(c - p)) return false;
  return p === 0 ? facts.change_ratio === null && facts.change_ratio_unavailable_reason === 'ZERO_COMPARISON_GSV'
    : number(facts.change_ratio) && facts.change_ratio_unavailable_reason === null
      && Math.abs(facts.change_ratio - (c - p) / p) <= 1e-12 * Math.max(1, Math.abs((c - p) / p));
}

// Parts and total are rounded to four decimals independently and then held as IEEE
// doubles, so each carries a representation error of at most half an ULP of its own
// magnitude; summing the parts can therefore differ from the total by a few ULPs of
// the largest magnitudes involved, never by a fixed amount. A difference of two large
// totals amplifies that error, so the delta decomposition passes its operands: the
// bound must scale with the magnitudes that produced the differences, not with the
// (possibly tiny) reconciled result itself. Mirrors backend contracts.reconciles.
const FLOAT_SLACK = 2 ** -50;

const preciseSum = values => {
  let sum = 0, compensation = 0;
  for (const value of values) {
    const next = sum + value;
    compensation += Math.abs(sum) >= Math.abs(value) ? (sum - next) + value : (value - next) + sum;
    sum = next;
  }
  return sum + compensation;
};

const reconciles = (parts, total, operands = []) => {
  const scale = preciseSum([...parts, ...operands].map(Math.abs));
  return Math.abs(preciseSum(parts) - total) <= Math.max(Math.abs(total), scale, 1) * FLOAT_SLACK;
};

// The producer publishes each channel difference as Python's round(current - comparison, 4):
// the exact binary64 subtraction rounded to the nearest multiple of 10^-4, ties going to the
// even digit. Reproducing that rule needs the exact rational value of the difference, because
// Math.round and toFixed break ties away from zero and disagree on exactly representable
// midpoints: 0.03125 is 0.0312 in Python and 0.0313 there. BigInt holds the value exactly, and
// the rounded decimal is parsed back to the same binary64 the producer published, so an honest
// delta compares equal bit for bit while every neighbouring four-decimal value fails.
const FLOAT_VIEW = new DataView(new ArrayBuffer(8));

function round4(value) {
  if (!Number.isFinite(value)) return NaN;
  FLOAT_VIEW.setFloat64(0, value);
  const bits = FLOAT_VIEW.getBigUint64(0);
  const exponent = Number((bits >> 52n) & 2047n);
  const mantissa = (exponent === 0 ? 0n : 1n << 52n) | (bits & ((1n << 52n) - 1n));
  // value = mantissa * 2 ** shift, with the subnormal form carrying no implicit leading bit.
  const shift = exponent === 0 ? -1074 : exponent - 1075;
  const scaled = mantissa * 10000n;
  let rounded;
  if (shift >= 0) {
    rounded = scaled << BigInt(shift);
  } else {
    const divisor = 1n << BigInt(-shift);
    rounded = scaled / divisor;
    const remainder = 2n * (scaled % divisor);
    if (remainder > divisor || (remainder === divisor && rounded % 2n !== 0n)) rounded += 1n;
  }
  const sign = bits >> 63n !== 0n ? '-' : '';
  return Number(`${sign}${rounded / 10000n}.${String(rounded % 10000n).padStart(4, '0')}`);
}

function validChannelBridge(facts) {
  // Python publishes code-point order; UTF-16 default ordering differs for astral labels.
  const compare = (left, right) => {
    const a = [...left], b = [...right];
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      const difference = a[i].codePointAt(0) - b[i].codePointAt(0);
      if (difference) return difference;
    }
    return a.length - b.length;
  };
  const bridge = facts.channel_bridge;
  if (!isObj(bridge) || keysOf(bridge).join(',') !== 'contributions,dimension,status,unavailable_reason'
    || bridge.dimension !== 'SALES_CHANNEL' || !Array.isArray(bridge.contributions) || bridge.contributions.length > 200) return false;
  const expected = facts.current.gsv === null || facts.comparison.gsv === null ? 'PERIOD_UNAVAILABLE'
    : facts.money_unit.status !== 'KNOWN' ? 'MONEY_UNIT_UNKNOWN' : null;
  if (bridge.status === 'UNAVAILABLE') return bridge.contributions.length === 0
    && (expected ? bridge.unavailable_reason === expected
      : ['AMBIGUOUS_ORDER_CHANNEL', 'INVALID_CHANNEL', 'CHANNEL_LIMIT_EXCEEDED'].includes(bridge.unavailable_reason));
  if (bridge.status !== 'AVAILABLE' || expected || bridge.unavailable_reason !== null) return false;
  const currents = [], comparisons = [], deltas = [];
  let previous = null;
  for (const item of bridge.contributions) {
    if (!isObj(item) || keysOf(item).join(',') !== 'channel,comparison_gsv,current_gsv,delta'
      || typeof item.channel !== 'string' || !item.channel.trim() || [...item.channel].length > 160
      || (previous !== null && compare(previous, item.channel) >= 0)
      || [item.current_gsv, item.comparison_gsv, item.delta].some(v => typeof v !== 'number' || !Number.isFinite(v))
      || item.current_gsv < 0 || item.comparison_gsv < 0
      // The producer publishes round(current_gsv - comparison_gsv, 4), so an honest delta is
      // exactly that rounding of this very subtraction - not a value near it. This is a
      // per-channel rule and must not borrow the operand-scaled budget the aggregate
      // reconciliation needs: that budget absorbs the error of summing many large terms, and
      // spending it here would accept a fabricated split whose parts still sum to the parent.
      || item.delta !== round4(item.current_gsv - item.comparison_gsv)) return false;
    currents.push(item.current_gsv); comparisons.push(item.comparison_gsv); deltas.push(item.delta);
    previous = item.channel;
  }
  return reconciles(currents, facts.current.gsv) && reconciles(comparisons, facts.comparison.gsv)
    && reconciles(deltas, facts.difference, [...currents, ...comparisons]);
}

function validDailySeries(series, period) {
  if (!isObj(series) || keysOf(series).join(',') !== 'grain,points,status,timezone,unavailable_reason'
    || series.grain !== 'DAY' || series.timezone !== 'Asia/Shanghai' || !Array.isArray(series.points)) return false;
  const timestamp = value => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
    const time = Date.parse(`${value}T00:00:00Z`);
    return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time : NaN;
  };
  const start = timestamp(period.requested_period.start_date), end = timestamp(period.requested_period.end_date);
  const length = (end - start) / 86400000 + 1;
  if (!Number.isInteger(length) || length < 1) return false;
  if (length > 366) return series.status === 'UNSUPPORTED_RANGE'
    && series.unavailable_reason === 'RANGE_EXCEEDS_366_DAYS' && series.points.length === 0;
  if (series.status !== 'AVAILABLE' || series.unavailable_reason !== null || series.points.length !== length) return false;
  const gsvs = [];
  let orders = 0;
  for (const [index, point] of series.points.entries()) {
    if (!isObj(point) || keysOf(point).join(',') !== 'date,gsv,order_count'
      || timestamp(point.date) !== start + index * 86400000
      || !Number.isSafeInteger(point.order_count) || point.order_count < 0) return false;
    const covered = period.through_date !== null && point.date <= period.through_date;
    if (!covered ? point.gsv !== null || point.order_count !== 0
      : typeof point.gsv !== 'number' || !Number.isFinite(point.gsv) || point.gsv < 0
        || (point.order_count === 0 && point.gsv !== 0)) return false;
    if (typeof point.gsv === 'number') gsvs.push(point.gsv);
    orders += point.order_count;
  }
  return orders === period.order_count && (period.gsv === null || reconciles(gsvs, period.gsv));
}

function validMoneyUnit(unit) {
  if (!isObj(unit) || keysOf(unit).join(',') !== 'amount_unit,currency,status') return false;
  return unit.status === 'UNKNOWN' ? unit.currency === null && unit.amount_unit === null
    : unit.status === 'KNOWN' && unit.currency === 'CNY' && ['major', 'minor'].includes(unit.amount_unit);
}

export function formatAmountUnit(result) {
  if (result?.facts?.schema_version === 'competition-gsv-facts/v1') return '未记录（旧结果）';
  const unit = result?.facts?.money_unit;
  if (!validMoneyUnit(unit) || unit.status !== 'KNOWN') return '未知（按原始数值展示）';
  return unit.amount_unit === 'minor' ? '人民币分（CNY minor）' : '人民币元（CNY major）';
}

export function canEndorse(result) {
  if (result?.schema_version === 'competition-computed-result/v1'
    && (!decodeCompetitionResultRef(result) || !opaque(result.analysis_id))) return false;
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

function scopeLabel(scope) {
  if (scope?.kind === 'ALL') return '全部';
  const parts = [];
  if (scope?.kind === 'CHANNEL_IDS' || scope?.kind === 'CHANNEL_AND_PRODUCT') {
    parts.push(`渠道 ${scope.channel_ids?.join('、') || '未提供'}`);
  }
  if (scope?.kind === 'PRODUCT_IDS' || scope?.kind === 'CHANNEL_AND_PRODUCT') {
    parts.push(`商品 ${scope.product_ids?.join('、') || '未提供'}`);
  }
  return parts.join('；') || '未提供';
}

export function conditionChips(result) {
  const resolved = result?.resolved_condition;
  if (!resolved) return [];
  return [
    { id: 'metric', label: '指标', value: displayValue(resolved.metric_type) },
    { id: 'current', label: '本期', value: periodRange(resolved.current_period) },
    { id: 'compare', label: '对比', value: `${displayValue(resolved.comparison_mode)} ${periodRange(resolved.comparison_period)}` },
    { id: 'sales', label: '销售范围', value: scopeLabel(resolved.sales_scope) },
    { id: 'history', label: '历史范围', value: scopeLabel(resolved.history_scope) },
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

export { isObj, opaque, sha256, keysOf, has, INTENTS, LAYOUT_MODES, round4 };
