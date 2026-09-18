import { isIdentity } from '../resource/frozen-contract.mjs';
import { mergeBudgets } from './budgets.mjs';
import { createHostChannel } from './message-channel.mjs';

let liveSessions = 0;

function token(prefix) {
  const id = (crypto.randomUUID?.() ?? `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`)
    .replace(/[^A-Za-z0-9_.:-]/g, '-');
  return `${prefix}-${id}`.slice(0, 128);
}

export function livePageSessionCount() {
  return liveSessions;
}

export function createPageSession({
  pageId, version, adapter, onEvent, onError, budgets, now = () => Date.now(),
} = {}) {
  if (!isIdentity(pageId) || !Number.isSafeInteger(version) || version < 1) {
    throw new Error('page session requires page_id and version');
  }
  const limits = mergeBudgets(budgets);
  if (liveSessions >= limits.maxInstances) {
    throw new Error('页面实例超过额度');
  }
  liveSessions += 1;
  let released = false;
  const instanceId = token('inst');
  const nonce = token('nonce');
  let handshakeTimer = null;
  let watchdogTimer = null;
  let helloAt = 0;
  let lastPong = 0;

  function clearTimers() {
    if (handshakeTimer) clearTimeout(handshakeTimer);
    if (watchdogTimer) clearInterval(watchdogTimer);
    handshakeTimer = null;
    watchdogTimer = null;
  }

  const channel = createHostChannel({
    instanceId,
    pageId,
    version,
    nonce,
    adapter,
    onError,
    onEvent(event) {
      if (event?.type === 'hello') {
        helloAt = now();
        lastPong = helloAt;
        if (handshakeTimer) {
          clearTimeout(handshakeTimer);
          handshakeTimer = null;
        }
      }
      if (event?.type === 'pong') lastPong = now();
      onEvent?.(event);
    },
  });

  function attach(iframe) {
    clearTimers();
    helloAt = 0;
    lastPong = 0;
    const attached = channel.attach(iframe);
    if (!attached.ok) return attached;
    const helloTimeout = Math.min(limits.handshakeTimeoutMs, limits.initTimeoutMs);
    handshakeTimer = setTimeout(() => {
      if (!helloAt) onError?.({ code: 'PAGE_INIT_TIMEOUT', message: '页面初始化超时，已保留宿主恢复入口。' });
    }, helloTimeout);
    watchdogTimer = setInterval(() => {
      if (!helloAt) return;
      channel.postToPage({ type: 'ping' });
      if (lastPong && now() - lastPong > limits.unresponsiveTimeoutMs) {
        onError?.({
          code: 'PAGE_UNRESPONSIVE',
          message: '页面对 watchdog 无响应；将终止当前 iframe。watchdog 不能打断 while(true)。',
        });
      }
    }, Math.max(500, Math.floor(limits.unresponsiveTimeoutMs / 2)));
    return attached;
  }

  function dispose() {
    clearTimers();
    channel.dispose();
    if (!released) {
      released = true;
      liveSessions -= 1;
    }
  }

  return {
    instanceId,
    nonce,
    pageId,
    version,
    attach,
    dispose,
    postToPage: (message) => channel.postToPage(message),
    get alive() { return channel.alive; },
  };
}
