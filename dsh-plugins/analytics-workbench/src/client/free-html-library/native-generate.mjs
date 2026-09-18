/** Native Agent page-package intake. Production generate never uses SAMPLE_PACKAGE. */

/** Upper bound for one delivery-tool round trip; keeps a refused/lost delivery from pinning busy forever. */
const DEFAULT_DELIVERY_TIMEOUT_MS = 180_000;

export function normalizePagePackage(pkg) {
  if (!pkg || typeof pkg.html !== 'string' || !pkg.html.trim()) return null;
  return {
    html: pkg.html,
    css: typeof pkg.css === 'string' ? pkg.css : '',
    js: typeof pkg.js === 'string' ? pkg.js : '',
    resources: Array.isArray(pkg.resources) ? pkg.resources : [],
    node_map: Array.isArray(pkg.node_map) ? pkg.node_map : [],
  };
}

function asText(source) {
  if (typeof source === 'string') return source;
  if (!source || typeof source !== 'object') return '';
  if (typeof source.text === 'string') return source.text;
  if (typeof source.content === 'string') return source.content;
  try { return JSON.stringify(source); } catch { return ''; }
}

export function extractPagePackage(source) {
  const direct = normalizePagePackage(source);
  if (direct) return direct;
  if (source && typeof source === 'object') {
    const nested = normalizePagePackage(source.package)
      || normalizePagePackage(source.value?.package)
      || normalizePagePackage(source.value);
    if (nested) return nested;
  }
  const text = asText(source);
  const fence = text.match(/\{[\s\S]*"html"\s*:\s*"[\s\S]*\}/);
  if (!fence) return null;
  try {
    return normalizePagePackage(JSON.parse(fence[0]));
  } catch {
    return null;
  }
}

export function nativeGenerateUnavailable(message = '原生 Agent 未返回页面源码包') {
  const error = new Error(message);
  error.code = 'NATIVE_GENERATE_UNAVAILABLE';
  return error;
}

/**
 * Intake for page packages delivered by the native delivery tool. The tool
 * card hands the receipt outcome here; nothing else resolves a waiting
 * generate. An Error outcome reports a refused package, null a lost one.
 */
export function createPagePackageWaiter() {
  const pending = new Map();
  return {
    deliver(requestId, outcome) {
      const waiter = pending.get(requestId);
      if (!waiter) return false;
      pending.delete(requestId);
      waiter(outcome);
      return true;
    },
    wait(requestId, signal, timeoutMs = DEFAULT_DELIVERY_TIMEOUT_MS) {
      return new Promise((resolve, reject) => {
        let timer;
        const cleanup = () => {
          pending.delete(requestId);
          if (signal) signal.removeEventListener('abort', onAbort);
          if (timer !== undefined) clearTimeout(timer);
        };
        const onAbort = () => {
          cleanup();
          reject(signal.reason instanceof Error ? signal.reason : nativeGenerateUnavailable('生成已取消'));
        };
        signal?.throwIfAborted();
        if (signal) signal.addEventListener('abort', onAbort, { once: true });
        if (typeof timeoutMs === 'number' && timeoutMs > 0) {
          timer = setTimeout(() => {
            cleanup();
            reject(nativeGenerateUnavailable('原生 Agent 未在时限内交付页面源码包'));
          }, timeoutMs);
        }
        pending.set(requestId, outcome => {
          cleanup();
          if (outcome instanceof Error) reject(outcome);
          else resolve(outcome);
        });
      });
    },
    cancelAll() {
      for (const waiter of pending.values()) waiter(null);
      pending.clear();
    },
    get pendingCount() { return pending.size; },
  };
}

/**
 * The prompt receipt only acknowledges enqueueing, so a waiter-backed
 * generate mints the page-gen id, asks submitPrompt to submit with it, and
 * then awaits the delivery-tool result. No fallback to sample packages.
 */
export function createNativePageGenerate({ submitPrompt, waiter } = {}) {
  return async function nativeGenerate(prompt, extras = {}) {
    const injected = extractPagePackage(extras?.package);
    if (injected) {
      if (typeof submitPrompt === 'function') await submitPrompt(prompt, extras);
      return injected;
    }
    if (waiter) {
      const requestId = `page-gen-${crypto.randomUUID()}`;
      if (typeof submitPrompt !== 'function') throw nativeGenerateUnavailable();
      await submitPrompt(prompt, { ...extras, requestId });
      const delivered = await waiter.wait(requestId, extras?.signal, extras?.timeoutMs);
      if (!delivered) throw nativeGenerateUnavailable();
      return delivered;
    }
    if (typeof submitPrompt !== 'function') throw nativeGenerateUnavailable();
    const reply = await submitPrompt(prompt, extras);
    const pkg = extractPagePackage(reply);
    if (!pkg) throw nativeGenerateUnavailable();
    return pkg;
  };
}
