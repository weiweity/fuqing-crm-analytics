/** Finite native-query fault helpers. Mock never fabricates SQL or journals. */
import {
  HISTORICAL_SUPERVISOR_EXITS, QUERY_FAULT_COPY, classifyQueryToolBlock,
  peerUntouchedByCancel, queryFaultAllowsFacts, textLeaksQueryFacts,
} from '../../dsh-plugins/analytics-workbench/src/query-fault.mjs';
import { QUESTIONS, QUERY_SESSION_IDS, QUERY_TOOL_NAME, SCENARIO } from './query-scenario.mjs';

export { HISTORICAL_SUPERVISOR_EXITS, QUERY_FAULT_COPY, QUERY_SESSION_IDS, QUERY_TOOL_NAME, QUESTIONS };
export const FAULT_SCENARIO = 'native-query-fault';
export const SUCCESS_SCENARIO = SCENARIO;

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
