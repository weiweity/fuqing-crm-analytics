/** Finite native-query fault helpers. Mock never fabricates SQL or journals. */
import {
  HISTORICAL_SUPERVISOR_EXITS, QUERY_FAULT_COPY, classifyQueryToolBlock,
  peerUntouchedByCancel, queryFaultAllowsFacts, textLeaksQueryFacts,
} from '../../dsh-plugins/analytics-workbench/src/query-fault.mjs';
import {
  QUESTIONS, QUERY_SESSION_IDS, QUERY_TOOL_NAME, SCENARIO, queryRequest,
} from './query-scenario.mjs';

export { HISTORICAL_SUPERVISOR_EXITS, QUERY_FAULT_COPY, QUERY_SESSION_IDS, QUERY_TOOL_NAME, QUESTIONS };
export const FAULT_SCENARIO = 'native-query-fault';
export const SUCCESS_SCENARIO = SCENARIO;
export const QUERY_FAULT_PROBE_SEQUENCE = Object.freeze(['sql_hold', 'unknown_schema', 'passthrough']);
export const FAULT_QUESTIONS = Object.freeze([
  QUESTIONS[0],
  QUESTIONS[1],
  '合成渠道后续购买第三问：取消后再次查询同一窗口 30 日。',
  '合成渠道后续购买第四问：取消隔离后同一窗口观察 60 日。',
]);

export const FAIL_CARD_MARKERS = Object.freeze({
  toolError: QUERY_FAULT_COPY.toolError,
  unrecognized: QUERY_FAULT_COPY.unrecognized,
});

export function historicalSupervisorRecord() {
  return HISTORICAL_SUPERVISOR_EXITS;
}

export function otherSessionNotCancelled(snapshot) {
  return peerUntouchedByCancel(snapshot);
}

export function cardShowsFault(ui, kind) {
  const cards = Array.isArray(ui?.cards) ? ui.cards : [];
  const faults = Array.isArray(ui?.faults) ? ui.faults : [];
  const text = cards.join('\n');
  if (queryFaultAllowsFacts(kind) || textLeaksQueryFacts(text)) return false;
  if (kind === 'tool-error') return cards.some(row => String(row).includes(FAIL_CARD_MARKERS.toolError));
  if (kind === 'unknown-version' || kind === 'malformed') {
    return cards.some(row => String(row).includes(FAIL_CARD_MARKERS.unrecognized));
  }
  return faults.includes(kind);
}

export function classifiedBlockHidesFacts(block) {
  const classified = classifyQueryToolBlock(block);
  return classified.kind !== 'ok' && !textLeaksQueryFacts(classified.copy);
}

export function cancelTarget(sessionId, runId) {
  return { session_id: sessionId, run_id: runId, reason: 'USER_REQUEST' };
}

export function queryFaultMockScript() {
  const wrap = '合成查询完成：数字来自真实 worker SQL，不是模型编造，不能当作真实经营结论。';
  const fast = Object.freeze({ chunkSize: 32, chunkDelayMs: 0 });
  // A cancel and B unknown_schema skip wrap HTTP, so the first three steps are
  // consecutive tool_calls. A's restore wrap must follow immediately so that
  // turn does not eat a second tool_call (dual N). B's later N=60 success is a
  // new user turn after that wrap.
  return [
    { sequence: ['tool_call_success'], toolName: QUERY_TOOL_NAME,
      toolArguments: JSON.stringify(queryRequest(30)), successText: wrap, ...fast },
    { sequence: ['tool_call_success'], toolName: QUERY_TOOL_NAME,
      toolArguments: JSON.stringify(queryRequest(60)), successText: wrap, ...fast },
    { sequence: ['tool_call_success'], toolName: QUERY_TOOL_NAME,
      toolArguments: JSON.stringify(queryRequest(30)), successText: wrap, ...fast },
    { sequence: ['success'], successText: wrap, ...fast },
    { sequence: ['tool_call_success'], toolName: QUERY_TOOL_NAME,
      toolArguments: JSON.stringify(queryRequest(60)), successText: wrap, ...fast },
    { sequence: ['success'], successText: wrap, ...fast },
    { sequence: ['success'], successText: wrap, ...fast },
  ];
}

export function parseQueryCancelRef(snapshot) {
  const match = String(snapshot ?? '').match(/(@e\d+) \[button\] "停止查询"(?: \[disabled\])?/);
  return match?.[1] ?? null;
}

export function parseStopGeneratingRef(snapshot) {
  const match = String(snapshot ?? '').match(/(@e\d+) \[button\] "Stop generating"/);
  return match?.[1] ?? null;
}

export function sqlHoldObserved(proof, worker, run) {
  return Boolean(proof && worker && run)
    && proof.event === 'SQL_ACTIVE'
    && proof.execution_id === worker.execution_id
    && proof.run_id === run.run_id
    && worker.active_slot === 1
    && run.status === 'RUNNING';
}

export function sessionCancelEnvelope(sessionId, rpcId) {
  return {
    type: 'client-request',
    rpcId,
    method: 'session/cancel',
    payload: { args: { request: { sessionId } } },
  };
}
