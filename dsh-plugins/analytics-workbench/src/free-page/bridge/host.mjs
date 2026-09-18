/** Host-owned MessageChannel session. Pages never receive SQL, tokens, or save. */
import {
  FORBIDDEN_FIELDS, FORBIDDEN_OPS, HANDSHAKE_FIELDS, HOST_TO_PAGE_EVENTS, PAGE_TO_HOST_OPS,
  PROTOCOL, bridgeError, exact, identity, record,
} from './contract.mjs';

function errorEvent(requestId, error, instanceId) {
  return {
    protocol: PROTOCOL,
    instance_id: instanceId ?? null,
    event: 'data.error',
    request_id: requestId ?? null,
    code: error.code ?? 'BRIDGE_UNKNOWN_OP',
    status: error.status ?? 400,
    message: error.message,
  };
}

function bindingEvent(state, instanceId, pageId) {
  return {
    protocol: PROTOCOL,
    instance_id: instanceId,
    event: 'binding.state',
    page_id: pageId,
    binding_state: state.binding_state,
    verified: state.verified === true,
    refs: state.refs ?? [],
    reasons: state.reasons ?? [],
    host_source: state.host_source,
  };
}

export function createBridgeHost({
  access,
  actor,
  pageId,
  version,
  manifest,
} = {}) {
  if (!access || !actor || !identity(pageId) || !Number.isSafeInteger(version) || version < 1) {
    throw bridgeError('INVALID_PAGE');
  }
  let session = null;
  const inflight = new Map();
  const aborted = new Map();

  function markAborted(instanceId, requestId) {
    let bucket = aborted.get(instanceId);
    if (!bucket) {
      bucket = new Set();
      aborted.set(instanceId, bucket);
    }
    bucket.add(requestId);
  }

  function isAborted(instanceId, requestId) {
    return aborted.get(instanceId)?.has(requestId) === true;
  }

  function abortSessionReads(target) {
    if (!target) return;
    target.expired = true;
    for (const requestId of target.liveReads) markAborted(target.instance_id, requestId);
  }

  function requireSession(message) {
    if (!session || session.expired) throw bridgeError('BRIDGE_EXPIRED_INSTANCE');
    if (!record(message) || message.protocol !== PROTOCOL) throw bridgeError('INVALID_PAGE');
    if (message.instance_id !== session.instance_id) throw bridgeError('BRIDGE_EXPIRED_INSTANCE');
    if (message.nonce !== session.nonce) throw bridgeError('BRIDGE_NONCE');
    if (message.page_id != null && message.page_id !== session.page_id) throw bridgeError('INVALID_PAGE');
    if (message.version != null && message.version !== session.version) throw bridgeError('INVALID_PAGE');
  }

  function handshake(message) {
    if (!exact(message, HANDSHAKE_FIELDS)) throw bridgeError('INVALID_PAGE');
    if (message.protocol !== PROTOCOL) throw bridgeError('INVALID_PAGE');
    if (!identity(message.instance_id) || !identity(message.page_id) || !identity(message.nonce)) {
      throw bridgeError('INVALID_PAGE');
    }
    if (!Number.isSafeInteger(message.version) || message.version < 1) throw bridgeError('INVALID_PAGE');
    if (message.page_id !== pageId || message.version !== version) throw bridgeError('INVALID_PAGE');
    if (session && !session.expired && message.nonce === session.nonce) throw bridgeError('BRIDGE_NONCE');
    if (session && session.instance_id === message.instance_id && session.expired) {
      throw bridgeError('BRIDGE_EXPIRED_INSTANCE');
    }
    if (session) abortSessionReads(session);
    session = {
      instance_id: message.instance_id,
      page_id: message.page_id,
      version: message.version,
      nonce: message.nonce,
      expired: false,
      liveReads: new Set(),
    };
    return bindingEvent(access.bindingState(actor, manifest), session.instance_id, pageId);
  }

  function expireInstance() {
    abortSessionReads(session);
  }

  async function read(message) {
    requireSession(message);
    if (FORBIDDEN_FIELDS.some(field => Object.hasOwn(message, field))) throw bridgeError('BRIDGE_UNKNOWN_OP');
    const allowed = new Set([
      ...HANDSHAKE_FIELDS, 'op', 'request_id', 'result_ref', 'data_ref', 'mode', 'cursor', 'limit', 'start', 'end',
    ]);
    if (Object.keys(message).some(key => !allowed.has(key))) throw bridgeError('INVALID_PAGE');
    const requestId = message.request_id;
    if (!identity(requestId)) throw bridgeError('INVALID_PAGE');
    if (isAborted(session.instance_id, requestId)) throw bridgeError('RESULT_UNAVAILABLE');
    const owned = session;
    const instanceId = owned.instance_id;
    owned.liveReads.add(requestId);
    const request = {
      op: 'data.read',
      request_id: requestId,
      instance_id: instanceId,
    };
    if (Object.hasOwn(message, 'result_ref')) request.result_ref = message.result_ref;
    if (Object.hasOwn(message, 'data_ref')) request.data_ref = message.data_ref;
    if (Object.hasOwn(message, 'mode')) request.mode = message.mode;
    if (Object.hasOwn(message, 'cursor')) request.cursor = message.cursor;
    if (Object.hasOwn(message, 'limit')) request.limit = message.limit;
    if (Object.hasOwn(message, 'start')) request.start = message.start;
    if (Object.hasOwn(message, 'end')) request.end = message.end;
    let key;
    let pending;
    try {
      await access.authorize(actor, request, manifest);
      key = JSON.stringify({
        result_ref: request.result_ref ?? null,
        data_ref: request.data_ref ?? null,
        mode: request.mode ?? 'summary',
        cursor: request.cursor ?? null,
        limit: request.limit ?? null,
        start: request.start ?? null,
        end: request.end ?? null,
      });
      pending = inflight.get(key);
      if (!pending) {
        pending = Promise.resolve(access.read(request, { actor, manifest }));
        inflight.set(key, pending);
      } else {
        await access.authorize(actor, request, manifest);
      }
      const body = await pending;
      if (isAborted(instanceId, requestId) || owned.expired || session !== owned) {
        throw bridgeError('RESULT_UNAVAILABLE');
      }
      return [
        {
          protocol: PROTOCOL,
          instance_id: instanceId,
          event: 'data.chunk',
          request_id: requestId,
          mode: body.mode,
          result_ref: body.result_ref,
          data_ref: body.data_ref,
          result_version: body.result_version,
          summary: body.summary,
          rows: body.rows,
          cursor: body.cursor,
          host_source: body.host_source,
        },
        {
          protocol: PROTOCOL,
          instance_id: instanceId,
          event: 'data.end',
          request_id: requestId,
          result_ref: body.result_ref,
          data_ref: body.data_ref,
          binding_state: body.binding_state,
        },
      ];
    } finally {
      owned.liveReads.delete(requestId);
      if (key && pending && inflight.get(key) === pending) inflight.delete(key);
    }
  }

  function cancel(message) {
    requireSession(message);
    if (!identity(message.request_id)) throw bridgeError('INVALID_PAGE');
    markAborted(session.instance_id, message.request_id);
    const accepted = access.cancel({ op: 'data.cancel', request_id: message.request_id, instance_id: session.instance_id }, actor);
    return [{
      protocol: PROTOCOL,
      instance_id: session.instance_id,
      event: 'data.end',
      request_id: message.request_id,
      status: accepted.status,
      op: 'data.cancel',
    }];
  }

  async function dispatch(message) {
    try {
      if (record(message) && exact(message, HANDSHAKE_FIELDS)) return [handshake(message)];
      if (!record(message)) throw bridgeError('INVALID_PAGE');
      if (FORBIDDEN_OPS.includes(message.op) || FORBIDDEN_FIELDS.some(field => Object.hasOwn(message, field))) {
        throw bridgeError('BRIDGE_UNKNOWN_OP');
      }
      if (!PAGE_TO_HOST_OPS.includes(message.op)) throw bridgeError('BRIDGE_UNKNOWN_OP');
      if (message.op === 'data.cancel') return cancel(message);
      return await read(message);
    } catch (error) {
      return [errorEvent(message?.request_id, error, message?.instance_id ?? session?.instance_id)];
    }
  }

  function attach(port) {
    let queue = Promise.resolve();
    port.onmessage = event => {
      queue = queue.then(async () => {
        const events = await dispatch(event.data);
        for (const item of events) port.postMessage(item);
      }).catch(error => {
        try {
          port.postMessage(errorEvent(
            event.data?.request_id,
            error,
            event.data?.instance_id ?? session?.instance_id,
          ));
        } catch {
          return undefined;
        }
      });
    };
    return () => {
      port.onmessage = null;
    };
  }

  return {
    handshake,
    dispatch,
    attach,
    expireInstance,
    events: HOST_TO_PAGE_EVENTS,
    get session() {
      return session;
    },
  };
}

export function createPageBridge(port, handshakeMessage) {
  const pending = new Map();
  const listeners = new Set();
  let handshakeSettled = false;
  let handshakeResolve;
  let handshakeReject;
  const handshakeDone = new Promise((resolve, reject) => {
    handshakeResolve = resolve;
    handshakeReject = reject;
  });
  function settleHandshake(ok, value) {
    if (handshakeSettled) return;
    handshakeSettled = true;
    if (ok) handshakeResolve(value);
    else handshakeReject(value);
  }
  port.onmessage = event => {
    const message = event.data;
    for (const listener of listeners) listener(message);
    if (message?.event === 'binding.state') settleHandshake(true, message);
    if (message?.event === 'data.error' && message.request_id == null) {
      settleHandshake(false, Object.assign(new Error(message.message), message));
    }
    const requestId = message?.request_id;
    const waiter = requestId ? pending.get(requestId) : null;
    if (!waiter) return;
    if (message.event === 'data.error') waiter.reject(Object.assign(new Error(message.message), message));
    else if (message.event === 'data.chunk') waiter.chunks.push(message);
    else if (message.event === 'data.end') {
      pending.delete(requestId);
      waiter.resolve({ chunks: waiter.chunks, end: message });
    }
  };
  port.postMessage(handshakeMessage);
  return {
    handshake: handshakeDone,
    onEvent(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    read(request) {
      return new Promise((resolve, reject) => {
        pending.set(request.request_id, { resolve, reject, chunks: [] });
        port.postMessage({ ...handshakeMessage, ...request, op: 'data.read' });
      });
    },
    cancel(requestId) {
      port.postMessage({ ...handshakeMessage, op: 'data.cancel', request_id: requestId });
    },
  };
}
