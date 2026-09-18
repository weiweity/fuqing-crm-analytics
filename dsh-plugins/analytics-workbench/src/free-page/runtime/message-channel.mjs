import {
  BRIDGE_PROTOCOL, FORBIDDEN_OPS, HANDSHAKE_FIELDS, PAGE_TO_HOST_OPS,
  exactKeys, fail, isIdentity,
} from '../resource/frozen-contract.mjs';

const OPTIONAL_REQUEST = ['request_id', 'op', 'payload'];
const OPTIONAL_EVENT = ['request_id', 'event', 'payload', 'error'];

function envelope(fields) {
  return { protocol: BRIDGE_PROTOCOL, ...fields };
}

function handshakeShape(value) {
  return exactKeys(value, ['protocol', 'type', ...HANDSHAKE_FIELDS.filter((k) => k !== 'protocol')], OPTIONAL_REQUEST)
    && value.protocol === BRIDGE_PROTOCOL
    && isIdentity(value.instance_id)
    && isIdentity(value.page_id)
    && Number.isSafeInteger(value.version) && value.version >= 1
    && isIdentity(value.nonce);
}

/**
 * Versioned MessageChannel host. Consumes frozen-contract-v0 handshake/ops.
 * data.read is forwarded to an optional adapter (Lane C); this lane does not add SQL/save.
 */
export function createHostChannel({
  instanceId, pageId, version, nonce, adapter, onEvent, onError,
} = {}) {
  let port = null;
  let alive = true;
  const seen = new Set();

  function expire(code, message) {
    alive = false;
    try { port?.close(); } catch { /* already closed */ }
    port = null;
    const result = fail(code, message);
    onError?.(result.error);
    return result;
  }

  function bindPort(nextPort) {
    if (!alive) return fail('BRIDGE_EXPIRED_INSTANCE', '会话已过期，需要重新握手');
    if (port && port !== nextPort) {
      try { port.close(); } catch { /* already closed */ }
    }
    port = nextPort;
    port.start?.();
    port.addEventListener('message', (event) => { void onMessage(event.data); });
    port.postMessage(envelope({
      type: 'handshake',
      instance_id: instanceId,
      page_id: pageId,
      version,
      nonce,
    }));
    return { ok: true };
  }

  function postToPage(message) {
    if (!alive || !port) return fail('BRIDGE_EXPIRED_INSTANCE', '会话已过期，需要重新握手');
    port.postMessage(envelope({
      instance_id: instanceId,
      page_id: pageId,
      version,
      nonce,
      ...message,
    }));
    return { ok: true };
  }

  async function onMessage(data) {
    if (!alive) {
      onError?.(fail('BRIDGE_EXPIRED_INSTANCE', '刷新后旧端口已作废').error);
      return;
    }
    if (!handshakeShape(data) && !exactKeys(data, ['protocol', 'type', 'instance_id', 'page_id', 'version', 'nonce'], [...OPTIONAL_REQUEST, ...OPTIONAL_EVENT, 'event'])) {
      onError?.(fail('INVALID_PAGE', '桥消息结构非法').error);
      return;
    }
    if (data.protocol !== BRIDGE_PROTOCOL) {
      onError?.(fail('INVALID_PAGE', '桥协议不匹配').error);
      return;
    }
    if (data.instance_id !== instanceId) {
      onError?.(fail('BRIDGE_EXPIRED_INSTANCE', '实例已过期').error);
      return;
    }
    if (data.nonce !== nonce) {
      onError?.(fail('BRIDGE_NONCE', 'nonce 无效').error);
      return;
    }
    if (data.page_id !== pageId || data.version !== version) {
      onError?.(fail('BRIDGE_EXPIRED_INSTANCE', '页面版本与当前会话不一致').error);
      return;
    }
    if (data.type === 'hello' || data.type === 'pong' || data.type === 'page.error') {
      onEvent?.(data);
      return;
    }
    if (data.type !== 'request') {
      onError?.(fail('BRIDGE_UNKNOWN_OP', `未知消息类型 ${String(data.type)}`).error);
      return;
    }
    if (!isIdentity(data.request_id)) {
      postToPage({
        type: 'error', error: fail('INVALID_PAGE', '桥请求缺少 request_id').error,
      });
      return;
    }
    const requestId = data.request_id;
    if (seen.has(requestId)) return;
    seen.add(requestId);
    if (FORBIDDEN_OPS.includes(data.op)) {
      postToPage({
        type: 'error', request_id: requestId, error: fail('FORBIDDEN', '页面不能调用该操作').error,
      });
      return;
    }
    if (!PAGE_TO_HOST_OPS.includes(data.op)) {
      postToPage({
        type: 'error', request_id: requestId, error: fail('BRIDGE_UNKNOWN_OP', '未知桥操作').error,
      });
      return;
    }
    if (data.op === 'data.cancel') {
      adapter?.cancel?.(data.payload ?? {});
      postToPage({ type: 'event', event: 'data.end', request_id: requestId, payload: { cancelled: true } });
      return;
    }
    if (!adapter?.read) {
      postToPage({
        type: 'error',
        request_id: requestId,
        error: fail('RESULT_UNAVAILABLE', '数据桥尚未接入；本运行时不提供 SQL 或页面保存').error,
      });
      return;
    }
    try {
      const reply = await adapter.read(data.payload ?? {});
      postToPage({ type: 'event', event: 'data.chunk', request_id: requestId, payload: reply });
      postToPage({ type: 'event', event: 'data.end', request_id: requestId, payload: {} });
    } catch (error) {
      postToPage({
        type: 'error',
        request_id: requestId,
        error: fail('RESULT_UNAVAILABLE', error instanceof Error ? error.message : '读取失败').error,
      });
    }
  }

  function attach(iframe) {
    if (!alive) return fail('BRIDGE_EXPIRED_INSTANCE', '会话已过期，需要重新握手');
    const target = iframe?.contentWindow;
    if (!target || typeof target.postMessage !== 'function') {
      return fail('INVALID_PAGE', '预览窗格尚未就绪');
    }
    const channel = new MessageChannel();
    bindPort(channel.port1);
    target.postMessage(envelope({
      type: 'handshake',
      instance_id: instanceId,
      page_id: pageId,
      version,
      nonce,
    }), '*', [channel.port2]);
    return { ok: true };
  }

  function dispose() {
    return expire('BRIDGE_EXPIRED_INSTANCE', '会话已关闭');
  }

  return {
    instanceId, pageId, version, nonce, attach, bindPort, postToPage, dispose,
    get alive() { return alive; },
  };
}

export function pageBridgeBootstrap({ instanceId, pageId, version, nonce }) {
  const protocol = BRIDGE_PROTOCOL;
  return `(() => {
    const PROTOCOL = ${JSON.stringify(protocol)};
    const expected = {
      instance_id: ${JSON.stringify(instanceId)},
      page_id: ${JSON.stringify(pageId)},
      version: ${JSON.stringify(version)},
      nonce: ${JSON.stringify(nonce)},
    };
    let port = null;
    let lastError = null;
    window.addEventListener('error', (event) => { lastError = event.message || 'page-error'; });
    window.addEventListener('message', (event) => {
      const data = event.data;
      if (!data || data.protocol !== PROTOCOL || data.type !== 'handshake') return;
      if (data.instance_id !== expected.instance_id || data.nonce !== expected.nonce) return;
      if (!event.ports || !event.ports[0]) return;
      port = event.ports[0];
      port.start();
      port.postMessage({ protocol: PROTOCOL, type: 'hello', ...expected });
      if (lastError) port.postMessage({ protocol: PROTOCOL, type: 'page.error', ...expected, payload: { message: lastError } });
      port.addEventListener('message', (incoming) => {
        const msg = incoming.data;
        if (msg && msg.type === 'ping') port.postMessage({ protocol: PROTOCOL, type: 'pong', ...expected });
      });
      window.__freePageBridge = {
        read(payload, request_id) {
          const id = request_id && /^[A-Za-z0-9_.:-]{1,128}$/.test(request_id)
            ? request_id
            : (crypto.randomUUID ? crypto.randomUUID() : ('req-' + Date.now()));
          port.postMessage({ protocol: PROTOCOL, type: 'request', op: 'data.read', request_id: id, payload, ...expected });
        },
        cancel(payload, request_id) {
          const id = request_id && /^[A-Za-z0-9_.:-]{1,128}$/.test(request_id)
            ? request_id
            : (crypto.randomUUID ? crypto.randomUUID() : ('req-' + Date.now()));
          port.postMessage({ protocol: PROTOCOL, type: 'request', op: 'data.cancel', request_id: id, payload, ...expected });
        },
      };
    });
  })();`;
}
