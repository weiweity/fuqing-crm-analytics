/** Native Agent page-package intake. Production generate never uses SAMPLE_PACKAGE. */

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

export function createNativePageGenerate({ submitPrompt } = {}) {
  return async function nativeGenerate(prompt, extras = {}) {
    const injected = extractPagePackage(extras?.package);
    if (injected) {
      if (typeof submitPrompt === 'function') await submitPrompt(prompt, extras);
      return injected;
    }
    if (typeof submitPrompt !== 'function') throw nativeGenerateUnavailable();
    const reply = await submitPrompt(prompt, extras);
    const pkg = extractPagePackage(reply);
    if (!pkg) throw nativeGenerateUnavailable();
    return pkg;
  };
}
