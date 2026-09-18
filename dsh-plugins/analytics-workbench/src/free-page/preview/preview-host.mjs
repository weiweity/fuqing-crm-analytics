import { FREE_PAGE_REFERRER_POLICY, FREE_PAGE_SANDBOX, describeIsolation } from '../runtime/isolation-policy.mjs';
import { createPageSession } from '../runtime/session.mjs';
import { createErrorBoundary, hostRecoveryCopy } from '../runtime/error-boundary.mjs';
import { normalizePagePackage } from '../resource/package-normalize.mjs';
import { createResourceCache } from '../resource/resource-cache.mjs';
import { fail, isIdentity } from '../resource/frozen-contract.mjs';
import { buildSrcdoc, previewResourceUrls } from './srcdoc-builder.mjs';

function el(doc, tag, attrs = {}, text) {
  const node = doc.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'onclick') node.addEventListener('click', value);
    else if (value !== undefined && value !== null) node.setAttribute(key, String(value));
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

/**
 * Preview host for Lane E to mount. Vanilla DOM; does not own library business state.
 * Saved restore uses the caller-supplied saved package (Lane A persists).
 */
export function mountPreviewHost(root, options = {}) {
  const doc = root?.ownerDocument;
  if (!doc) throw new Error('preview host requires a DOM element');
  const pageId = isIdentity(options.pageId) ? options.pageId : 'page_fixture_unbound';
  const actorId = isIdentity(options.actorId) ? options.actorId : 'actor_fixture';
  const cache = options.cache ?? createResourceCache();
  const boundary = createErrorBoundary({ pageId, version: options.version ?? 1 });
  const objectUrls = [];
  let session = null;
  let iframe = null;
  let currentPackage = null;
  let currentVersion = options.version ?? 1;
  let saved = options.savedPackage ? { version: options.savedVersion ?? 1, package: options.savedPackage } : null;

  const chrome = el(doc, 'section', { class: 'fp-preview-host', 'data-testid': 'fp-preview-host' });
  const status = el(doc, 'p', { class: 'fp-preview-status', role: 'status', 'data-testid': 'fp-preview-status' }, '未加载页面');
  const actions = el(doc, 'div', { class: 'fp-preview-actions' });
  const stopBtn = el(doc, 'button', { type: 'button', 'data-testid': 'fp-stop' }, '停止页面');
  const restartBtn = el(doc, 'button', { type: 'button', 'data-testid': 'fp-restart' }, '重启');
  const restoreBtn = el(doc, 'button', { type: 'button', 'data-testid': 'fp-restore' }, '恢复已保存版本');
  const frameSlot = el(doc, 'div', { class: 'fp-preview-frame-slot', 'data-testid': 'fp-frame-slot' });
  const showChrome = options.chrome !== false;
  actions.append(stopBtn, restartBtn, restoreBtn);
  if (showChrome) chrome.append(status, actions, frameSlot);
  else chrome.append(status, frameSlot);
  root.append(chrome);

  function paint() {
    status.textContent = hostRecoveryCopy(boundary.getState()) || (session?.alive ? '页面运行中' : '页面已停止');
    chrome.dataset.status = boundary.getState().status;
  }
  boundary.subscribe(paint);

  function revokeUrls() {
    for (const url of objectUrls.splice(0)) {
      try { URL.revokeObjectURL(url); } catch { /* ignore */ }
    }
  }

  function dropFrame() {
    session?.dispose();
    session = null;
    iframe?.remove();
    iframe = null;
    revokeUrls();
  }

  function bindFrame(srcdoc) {
    iframe = el(doc, 'iframe', {
      sandbox: FREE_PAGE_SANDBOX,
      referrerpolicy: FREE_PAGE_REFERRER_POLICY,
      title: '自由页面预览',
      'data-testid': options.frameTestId ?? 'fp-preview-frame',
    });
    iframe.srcdoc = srcdoc;
    frameSlot.append(iframe);
    const frame = iframe;
    iframe.addEventListener('load', () => {
      if (iframe !== frame) return;
      session?.attach(iframe);
    });
  }

  async function loadPackage(pkg, version) {
    if (!Number.isSafeInteger(version) || version < 1) {
      const failed = fail('INVALID_PAGE', 'version 须为 >= 1 的整数');
      boundary.fail(failed.error.code, failed.error.message);
      paint();
      return failed;
    }
    const normalized = await normalizePagePackage(pkg, { budgets: options.budgets });
    if (!normalized.ok) {
      boundary.fail(normalized.error.code, normalized.error.message);
      paint();
      return normalized;
    }
    for (const resource of normalized.value.resources) {
      const written = cache.put({
        actorId, pageId, version, resource,
      });
      if (!written.ok) {
        boundary.fail(written.error.code, written.error.message);
        paint();
        return written;
      }
      const allowed = cache.get({
        actorId, pageId, version, resourceId: resource.resource_id, sha256: resource.sha256,
      });
      if (!allowed.ok) {
        boundary.fail(allowed.error.code, allowed.error.message);
        paint();
        return allowed;
      }
    }
    dropFrame();
    currentPackage = normalized.value;
    currentVersion = version;
    const createUrl = typeof URL !== 'undefined' && URL.createObjectURL
      ? (blob) => {
        const url = URL.createObjectURL(blob);
        objectUrls.push(url);
        return url;
      }
      : null;
    const resources = previewResourceUrls(normalized.value.resources, createUrl);
    try {
      session = createPageSession({
        pageId,
        version,
        adapter: options.adapter,
        budgets: options.budgets,
        onEvent: options.onEvent,
        onError(error) {
          boundary.fail(error.code, error.message);
          if (error.code === 'PAGE_UNRESPONSIVE' || error.code === 'PAGE_INIT_TIMEOUT') stop('页面已停止');
          options.onError?.(error);
        },
      });
    } catch (error) {
      const failed = fail('INVALID_PAGE', error instanceof Error ? error.message : '无法创建页面会话');
      boundary.fail(failed.error.code, failed.error.message);
      paint();
      return failed;
    }
    const srcdoc = buildSrcdoc({
      html: normalized.value.html,
      css: normalized.value.css,
      js: normalized.value.js,
      resources,
      instanceId: session.instanceId,
      pageId,
      version,
      nonce: session.nonce,
    });
    bindFrame(srcdoc);
    boundary.running({ pageId, version });
    paint();
    return { ok: true, instanceId: session.instanceId, isolation: describeIsolation(options.isolationEvidence) };
  }

  function stop(reason) {
    dropFrame();
    boundary.stopped(reason);
    paint();
    return { ok: true };
  }

  async function restart() {
    if (!currentPackage) return fail('NOT_FOUND', '没有可重启的页面');
    return loadPackage(currentPackage, currentVersion);
  }

  async function restoreSaved() {
    if (!saved) return fail('NOT_FOUND', '没有已保存版本');
    boundary.restoring({ version: saved.version });
    const result = await loadPackage(saved.package, saved.version);
    if (result.ok) boundary.restored({ version: saved.version });
    paint();
    return result;
  }

  if (showChrome) {
    stopBtn.addEventListener('click', () => { stop('页面已停止'); });
    restartBtn.addEventListener('click', () => { void restart(); });
    restoreBtn.addEventListener('click', () => { void restoreSaved(); });
  }

  return {
    loadPackage,
    stop,
    restart,
    restoreSaved,
    rememberSaved(pkg, version) {
      saved = { package: pkg, version };
    },
    getState: boundary.getState,
    isolation: () => describeIsolation(options.isolationEvidence),
    dispose() {
      dropFrame();
      chrome.remove();
    },
  };
}
