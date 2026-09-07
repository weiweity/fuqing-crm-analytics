/** Query-family fault classification. Does not invent SQL results or close UNKNOWN history. */
import { QUERY_RECEIPT_SCHEMA, decodeQueryReceipt } from './query-model.mjs';

export const HISTORICAL_SUPERVISOR_EXITS = Object.freeze({
  count: 3,
  status: 'UNKNOWN',
  closed_by_epipe: false,
  verdict: 'OPEN / 原因未证实',
});

export const QUERY_FAULT_COPY = Object.freeze({
  running: '合成查询运行中…',
  toolError: '查询工具失败；没有可用结果。未执行业务动作。',
  unrecognized: '查询结果格式无法识别或版本不支持；不推断分析成功。',
});

export const CHANNEL_FACT_LEAK = /N=\d+|成熟 \d+|未成熟 \d+|二单 \d+|跨渠道 \d+|二单率 |跨渠道率 |净支付 |\d+\.\d{2} 元|result_ref |EMPTY_MATURE_COHORT/;

const FAULT_KINDS = new Set(['running', 'tool-error', 'unknown-version', 'malformed', 'ok']);

export function classifyQueryReceipt(value) {
  if (decodeQueryReceipt(value)) return { kind: 'ok', receipt: decodeQueryReceipt(value) };
  const version = value && typeof value === 'object' && !Array.isArray(value) && typeof value.schema_version === 'string'
    ? value.schema_version : null;
  if (version && version !== QUERY_RECEIPT_SCHEMA) return { kind: 'unknown-version', receipt: null, schema_version: version };
  return { kind: 'malformed', receipt: null, schema_version: version };
}

export function classifyQueryToolBlock(block) {
  if (!block || typeof block !== 'object' || block.kind !== 'tool-result') {
    return { kind: 'running', copy: QUERY_FAULT_COPY.running };
  }
  if (block.isError) return { kind: 'tool-error', copy: QUERY_FAULT_COPY.toolError };
  const classified = classifyQueryReceipt(block.meta);
  if (classified.kind === 'ok') return classified;
  return { ...classified, copy: QUERY_FAULT_COPY.unrecognized };
}

export function queryFaultAllowsFacts(kind) {
  return kind === 'ok';
}

export function textLeaksQueryFacts(text) {
  return CHANNEL_FACT_LEAK.test(String(text ?? ''));
}

export function peerUntouchedByCancel(peer, beforeStatus) {
  if (!peer || typeof peer !== 'object') return false;
  if (beforeStatus !== undefined && peer.status !== beforeStatus) return false;
  return peer.status !== 'CANCELLED' && peer.status !== 'CANCELLING';
}

export function successSurvivesCancel(before, after) {
  if (!before || !after) return false;
  if (before.status !== 'SUCCEEDED' || after.status !== 'SUCCEEDED') return false;
  if (before.run_id !== after.run_id) return false;
  const beforeResult = before.result_json ?? before.result ?? null;
  const afterResult = after.result_json ?? after.result ?? null;
  if (beforeResult == null || afterResult == null) return false;
  return JSON.stringify(beforeResult) === JSON.stringify(afterResult);
}

export function singleTerminal(status) {
  return status === 'SUCCEEDED' || status === 'CANCELLED' || status === 'FAILED';
}

export function workerReleased(row) {
  return Boolean(row) && row.state === 'EXITED' && row.active_slot == null;
}

export function refreshInventoryEqual(before, after) {
  return JSON.stringify(before) === JSON.stringify(after);
}

export function isQueryFaultKind(kind) {
  return FAULT_KINDS.has(kind);
}

export function historicalSupervisorRemainsUnknown() {
  return HISTORICAL_SUPERVISOR_EXITS.status === 'UNKNOWN' && HISTORICAL_SUPERVISOR_EXITS.closed_by_epipe === false
    && HISTORICAL_SUPERVISOR_EXITS.count === 3;
}
