/** Projection of the pinned native journal, NOT another run state machine. */

export function requestIdOf(message) {
  return message?.source?.kind === 'user' ? message.source.rpcId : undefined;
}

export function emptyJournal() {
  return {
    queues: { 'next-turn': [], 'next-step': [] },
    turn: undefined,
    currentRequestId: undefined,
    requestByTurn: new Map(),
    toolToRequest: new Map(),
    byRequest: new Map(),
  };
}

function requestSlot(state, requestId) {
  let slot = state.byRequest.get(requestId);
  if (!slot) {
    slot = { received: false, discarded: false, targetTurn: undefined, reason: undefined, successful_call_ids: [], ambiguous: false };
    state.byRequest.set(requestId, slot);
  }
  return slot;
}

/** Incremental fold. Does not retain the event list. */
export function applyJournal(state, event) {
  const next = {
    queues: {
      'next-turn': state.queues['next-turn'].slice(),
      'next-step': state.queues['next-step'].slice(),
    },
    turn: state.turn,
    currentRequestId: state.currentRequestId,
    requestByTurn: new Map(state.requestByTurn),
    toolToRequest: new Map(state.toolToRequest),
    byRequest: new Map([...state.byRequest].map(([id, slot]) => [id, { ...slot, successful_call_ids: slot.successful_call_ids.slice() }])),
  };
  const data = event.data;
  if (event.type === 'agent/inbox/spliced') {
    const queue = next.queues[data.target];
    if (queue) {
      const removed = queue.splice(data.start, data.removedCount ?? 0, ...data.inserted);
      for (const message of data.inserted) {
        const id = requestIdOf(message);
        if (id) requestSlot(next, id).received = true;
      }
      if (data.outcome === 'canceled') {
        for (const message of removed) {
          const id = requestIdOf(message);
          if (id) requestSlot(next, id).discarded = true;
        }
      }
    }
  }
  if (event.type === 'turn/start') {
    next.turn = data.turn;
    next.currentRequestId = undefined;
  }
  if (event.type === 'user/message' && requestIdOf(data)) {
    const id = requestIdOf(data);
    if (next.currentRequestId && next.currentRequestId !== id) {
      requestSlot(next, next.currentRequestId).ambiguous = true;
      requestSlot(next, id).ambiguous = true;
    }
    next.currentRequestId = id;
    next.requestByTurn.set(next.turn, id);
    const slot = requestSlot(next, id);
    slot.received = true;
    slot.targetTurn = next.turn;
  }
  if (event.type === 'tool/call' && data.callId != null && data.turn === next.turn && next.currentRequestId) {
    next.toolToRequest.set(data.callId, next.currentRequestId);
  }
  if (event.type === 'turn/end' && data.turn != null) {
    for (const slot of next.byRequest.values()) {
      if (slot.targetTurn === data.turn) slot.reason = data.reason;
    }
  }
  if (event.type === 'tool/result' && data.turn != null) {
    for (const slot of next.byRequest.values()) {
      if (slot.targetTurn !== data.turn) continue;
      for (const block of data.message.content) {
        if (block.type === 'tool-result' && block.isError === false) slot.successful_call_ids.push(block.toolCallId);
      }
    }
  }
  return next;
}

export function journalFromEvents(events) {
  let state = emptyJournal();
  for (const event of events) state = applyJournal(state, event);
  return state;
}

const journals = new WeakMap();

export function nativeJournal(ctx) {
  let api = journals.get(ctx);
  if (api) return api;
  if (typeof ctx?.on !== 'function') {
    api = { of() { return emptyJournal(); } };
    journals.set(ctx, api);
    return api;
  }
  const bySession = new WeakMap();
  ctx.on('session/created', (session) => { bySession.set(session, emptyJournal()); }, { global: true });
  ctx.on('session/event', (session, event) => {
    bySession.set(session, applyJournal(bySession.get(session) ?? emptyJournal(), event));
  }, { global: true });
  ctx.on('session/disposed', (session) => { bySession.delete(session); }, { global: true });
  api = {
    of(session) {
      return bySession.get(session) ?? emptyJournal();
    },
  };
  journals.set(ctx, api);
  return api;
}

export function summarizeJournal(state, requestId) {
  const slot = state.byRequest.get(requestId) ?? {
    received: false, discarded: false, targetTurn: undefined, reason: undefined, successful_call_ids: [], ambiguous: false,
  };
  return {
    received: slot.received,
    discarded: slot.discarded,
    targetTurn: slot.targetTurn,
    currentRequestId: state.currentRequestId,
    reason: slot.reason,
    ambiguous: slot.ambiguous,
    successful_call_ids: slot.successful_call_ids,
  };
}

/** Test helper: fold a complete event list. Production uses nativeJournal(ctx). */
export function summarizeRequest(events, requestId) {
  return summarizeJournal(journalFromEvents(events), requestId);
}

export function requestForTool(events, callId) {
  return journalFromEvents(events).toolToRequest.get(callId);
}

export function requestForToolIn(state, callId) {
  return state.toolToRequest.get(callId);
}

/** First pre-step's inbox is not journaled yet; later steps use the projected turn. */
export function requestForStep(events, messages, turn) {
  return requestForStepIn(journalFromEvents(events), messages, turn);
}

export function requestForStepIn(state, messages, turn) {
  const ids = new Set();
  const fromTurn = state.requestByTurn.get(turn);
  if (fromTurn) ids.add(fromTurn);
  for (const message of messages) if (requestIdOf(message)) ids.add(requestIdOf(message));
  return ids.size === 1 ? [...ids][0] : undefined;
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
