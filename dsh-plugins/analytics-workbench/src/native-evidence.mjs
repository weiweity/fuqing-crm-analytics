/** Projection of the pinned native journal, NOT another run state machine. */
export function requestIdOf(message) {
  return message?.source?.kind === 'user' ? message.source.rpcId : undefined;
}

/** First pre-step's inbox is not journaled yet; later steps use only this turn. */
export function requestForStep(events, messages, turn) {
  const ids = new Set();
  let current;
  for (const event of events) {
    if (event.type === 'turn/start') current = event.data.turn;
    if (current === turn && event.type === 'user/message' && requestIdOf(event.data)) ids.add(requestIdOf(event.data));
  }
  for (const message of messages) if (requestIdOf(message)) ids.add(requestIdOf(message));
  return ids.size === 1 ? [...ids][0] : undefined;
}

export function requestForTool(events, callId) {
  let turn, requestId;
  let result;
  for (const event of events) {
    if (event.type === 'turn/start') { turn = event.data.turn; requestId = undefined; }
    if (event.type === 'user/message' && requestIdOf(event.data)) requestId = requestIdOf(event.data);
    if (event.type === 'tool/call' && event.data.callId === callId && event.data.turn === turn) result = requestId;
  }
  return result;
}

export function summarizeRequest(events, requestId) {
  const queues = { 'next-turn': [], 'next-step': [] };
  let turn, targetTurn, received = false, discarded = false, reason, currentRequestId;
  let ambiguous = false;
  const calls = [];
  for (const event of events) {
    const data = event.data;
    if (event.type === 'agent/inbox/spliced') {
      const queue = queues[data.target];
      if (!queue) continue;
      const removed = queue.splice(data.start, data.removedCount ?? 0, ...data.inserted);
      if (data.inserted.some(message => requestIdOf(message) === requestId)) received = true;
      if (data.outcome === 'canceled' && removed.some(message => requestIdOf(message) === requestId)) discarded = true;
    }
    if (event.type === 'turn/start') { turn = data.turn; currentRequestId = undefined; }
    if (event.type === 'user/message' && requestIdOf(data)) {
      if (currentRequestId && currentRequestId !== requestIdOf(data)) ambiguous = true;
      currentRequestId = requestIdOf(data);
      if (currentRequestId === requestId) { targetTurn = turn; received = true; }
    }
    if (event.type === 'turn/end' && data.turn === targetTurn) reason = data.reason;
    if (event.type === 'tool/result' && data.turn === targetTurn) {
      for (const block of data.message.content) {
        if (block.type === 'tool-result' && block.isError === false) calls.push(block.toolCallId);
      }
    }
  }
  return { received, discarded, targetTurn, currentRequestId, reason, ambiguous, successful_call_ids: calls };
}

export function evidenceFor(intent, summary, executionExited) {
  let outcome = 'UNKNOWN';
  if (!summary.ambiguous && summary.received) {
    if (!executionExited) outcome = 'RUNNING';
    else if (summary.discarded && !summary.targetTurn) outcome = 'CANCELLED';
    else outcome = ({ completed: 'SUCCEEDED', aborted: 'CANCELLED', blocked: 'NEEDS_INPUT',
      error: 'FAILED', interrupted: 'FAILED', 'max-tokens': 'FAILED' })[summary.reason?.kind] ?? 'UNKNOWN';
  }
  return { run_id: intent.run_id, attempt_id: intent.attempt_id, session_id: intent.session_id,
    request_id: intent.request_id, execution_exited: executionExited && outcome !== 'UNKNOWN', outcome,
    successful_call_ids: summary.successful_call_ids,
    ...(executionExited && outcome === 'FAILED' && summary.reason?.kind === 'interrupted'
      ? { error_code: 'EXECUTION_UNKNOWN' } : {}) };
}
