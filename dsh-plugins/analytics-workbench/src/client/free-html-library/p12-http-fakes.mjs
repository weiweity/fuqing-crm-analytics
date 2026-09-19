/** Isolated documents/result HTTP dispatcher for tests. Not the Python SSOT. */

import { PAGE_DOCUMENTS_PREFIX, PAGE_RESULT_PREFIX } from './page-http.mjs';

export const AGENT_PACKAGE = Object.freeze({
  html: '<!doctype html><html lang="zh-CN"><body><h1 data-shine-node="n_title">原生Agent标题</h1><p>页面内可点击内容</p><button type="button" data-shine-node="n_action">页面按钮</button><section data-shine-region="r_chart"><canvas width="320" height="120"></canvas><table><caption>摘要</caption></table></section></body></html>',
  css: 'h1{font:600 28px/1.3 sans-serif}',
  js: 'window.__fromNativeAgent=true',
  resources: [],
  node_map: [
    { node_id: 'n_title', kind: 'static_element', selector: "[data-shine-node='n_title']" },
    { node_id: 'n_action', kind: 'static_element', selector: "[data-shine-node='n_action']" },
    { node_id: 'r_chart', kind: 'dynamic_region', selector: "[data-shine-region='r_chart']" },
  ],
});

function clone(value) {
  return structuredClone(value);
}

function json(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => clone(body),
  };
}

export function createDocumentsState() {
  return {
    seq: 0,
    pages: new Map(),
    previews: new Map(),
    receipts: new Map(),
  };
}

function nextId(state, prefix) {
  state.seq += 1;
  return `${prefix}_${state.seq}`;
}

function listItem(spec) {
  const item = {
    page_id: spec.page_id,
    title: spec.title,
    version: spec.version,
    session_id: spec.session_id,
    binding_state: spec.binding_state,
  };
  if (spec.origin_path) item.origin_path = spec.origin_path;
  return item;
}

export function dispatchDocuments(state, { method, path, body, idempotencyKey, authorized }) {
  if (!authorized) return json(401, { error: { code: 'UNAUTHORIZED', message: '未授权' } });
  const verb = String(method || 'GET').toUpperCase();
  if (verb === 'POST' && path === '/previews') {
    const pageId = nextId(state, 'page');
    const previewId = nextId(state, 'preview');
    const spec = {
      schema_version: 'free-page/v1',
      page_id: pageId,
      session_id: body.session_id,
      title: body.title,
      version: 1,
      binding_state: (body.binding_manifest?.result_refs || []).length ? 'BOUND_VERIFIED' : 'UNBOUND_SAMPLE',
      package: clone(body.package),
      binding_manifest: clone(body.binding_manifest || { bindings: [], result_refs: [] }),
      ...(body.origin_path ? { origin_path: body.origin_path } : {}),
    };
    state.previews.set(previewId, {
      preview_id: previewId, operation: 'GENERATE', status: 'PENDING', page_id: pageId,
      base_version: 0, spec,
    });
    return json(201, {
      preview_id: previewId, status: 'PENDING', operation: 'GENERATE', base_version: 0,
      expires_at_ms: Date.now() + 1_800_000, snapshot: { spec: clone(spec) },
    });
  }
  const confirm = path.match(/^\/previews\/([^/]+)\/confirm$/);
  if (verb === 'POST' && confirm) {
    if (!idempotencyKey) return json(428, { error: { code: 'IDEMPOTENCY_KEY_REQUIRED', message: '需要稳定的 Idempotency-Key。' } });
    if (state.receipts.has(idempotencyKey)) return json(200, { spec: clone(state.receipts.get(idempotencyKey)) });
    const preview = state.previews.get(confirm[1]);
    if (!preview) return json(404, { error: { code: 'NOT_FOUND', message: '草稿不存在' } });
    if (preview.status === 'CANCELLED') return json(409, { error: { code: 'PREVIEW_CANCELLED', message: '草稿已取消' } });
    preview.status = 'APPLIED';
    const record = state.pages.get(preview.spec.page_id) || { spec: null, history: [] };
    record.spec = clone(preview.spec);
    if (!record.history.some(item => item.version === preview.spec.version)) {
      record.history.push({
        version: preview.spec.version, operation: preview.operation, created_at_ms: Date.now(),
        spec: clone(preview.spec),
      });
    }
    state.pages.set(preview.spec.page_id, record);
    state.receipts.set(idempotencyKey, clone(preview.spec));
    return json(200, { spec: clone(preview.spec) });
  }
  const cancel = path.match(/^\/previews\/([^/]+)\/cancel$/);
  if (verb === 'POST' && cancel) {
    const preview = state.previews.get(cancel[1]);
    if (preview) preview.status = 'CANCELLED';
    return json(200, { preview_id: cancel[1], status: 'CANCELLED' });
  }
  if (verb === 'GET' && path === '/pages') {
    return json(200, { items: [...state.pages.values()].map(item => listItem(item.spec)) });
  }
  const versions = path.match(/^\/pages\/([^/]+)\/versions$/);
  if (verb === 'GET' && versions) {
    const record = state.pages.get(decodeURIComponent(versions[1]));
    if (!record) return json(404, { error: { code: 'NOT_FOUND', message: '页面不存在' } });
    return json(200, [...record.history].reverse().map(item => ({
      version: item.version, operation: item.operation, created_at_ms: item.created_at_ms,
    })));
  }
  const pagePath = path.match(/^\/pages\/([^/]+)$/);
  if (verb === 'GET' && pagePath) {
    const record = state.pages.get(decodeURIComponent(pagePath[1]));
    if (!record) return json(404, { error: { code: 'NOT_FOUND', message: '页面不存在' } });
    return json(200, { spec: clone(record.spec) });
  }
  const mutate = path.match(/^\/pages\/([^/]+)\/(patch-preview|save-preview|rollback-preview)$/);
  if (verb === 'POST' && mutate) {
    const pageId = decodeURIComponent(mutate[1]);
    const kind = mutate[2];
    const record = state.pages.get(pageId);
    if (!record) return json(404, { error: { code: 'NOT_FOUND', message: '页面不存在' } });
    if (body.base_version !== record.spec.version) {
      return json(409, { error: { code: 'VERSION_CONFLICT', message: '页面版本已变化' } });
    }
    const previewId = nextId(state, 'preview');
    let spec;
    let operation;
    if (kind === 'rollback-preview') {
      const target = record.history.find(item => item.version === body.to_version);
      if (!target || body.to_version >= body.base_version) {
        return json(422, { error: { code: 'INVALID_PAGE', message: '回滚目标必须早于当前版本' } });
      }
      spec = { ...clone(target.spec), version: record.spec.version + 1 };
      operation = 'ROLLBACK';
    } else {
      spec = clone(record.spec);
      spec.version += 1;
      if (body.title) spec.title = body.title;
      if (body.package) spec.package = clone(body.package);
      if (body.binding_manifest) spec.binding_manifest = clone(body.binding_manifest);
      spec.binding_state = (spec.binding_manifest?.result_refs || []).length ? spec.binding_state : 'UNBOUND_SAMPLE';
      operation = kind === 'patch-preview' ? 'PATCH' : 'SAVE';
    }
    state.previews.set(previewId, {
      preview_id: previewId, operation, status: 'PENDING', page_id: pageId,
      base_version: body.base_version, spec,
    });
    return json(201, {
      preview_id: previewId, status: 'PENDING', operation, base_version: body.base_version,
      expires_at_ms: Date.now() + 1_800_000, snapshot: { spec: clone(spec) },
    });
  }
  return json(404, { error: { code: 'NOT_FOUND', message: '路由不存在' } });
}

export function createResultState() {
  return {
    snapshots: new Map(),
    cancelled: new Set(),
  };
}

export function seedResultFixture(state, snapshot = {}) {
  const item = {
    result_ref: 'result_fixture_1',
    owner: 'alice',
    unit: 'CNY 元',
    time_range: { start: '2026-04-30', end: '2026-07-28' },
    queried_at: '2026-07-28T12:00:00.000+00:00',
    source: '隔离结果 HTTP · result_fixture_1',
    result_version: 1,
    rows: [{ i: 0, label: 'row-0', value: 10 }],
    ...snapshot,
  };
  state.snapshots.set(item.result_ref, item);
  return item;
}

export function dispatchResult(state, { method, path, body, authorized }) {
  if (!authorized) return json(401, { error: { code: 'UNAUTHORIZED', message: '未授权' } });
  const verb = String(method || 'GET').toUpperCase();
  if (verb === 'POST' && path === '/snapshots') {
    const item = seedResultFixture(state, body);
    return json(201, { result_ref: item.result_ref, result_version: item.result_version, owner: item.owner });
  }
  if (verb === 'POST' && path === '/cancel') {
    const requestId = body?.request?.request_id || body?.request_id;
    if (requestId) state.cancelled.add(requestId);
    return json(200, { request_id: requestId, status: 'CANCELLED' });
  }
  if (verb === 'POST' && path === '/binding-state') {
    const refs = body?.manifest?.result_refs || [];
    if (!refs.length) {
      return json(200, { binding_state: 'UNBOUND_SAMPLE', verified: false, refs: [], reasons: [] });
    }
    return json(200, { binding_state: 'BOUND_VERIFIED', verified: true, refs, reasons: [] });
  }
  if (verb === 'POST' && path === '/read') {
    const request = body?.request || {};
    if (['sql', 'save', 'http.fetch', 'credential.read'].includes(request.op)) {
      return json(400, { error: { code: 'BRIDGE_UNKNOWN_OP', message: '未授权的桥接操作' } });
    }
    if (request.request_id && state.cancelled.has(request.request_id)) {
      return json(409, { error: { code: 'RESULT_UNAVAILABLE', message: '授权结果当前不可用' } });
    }
    const snapshot = state.snapshots.get(request.result_ref);
    if (!snapshot) return json(404, { error: { code: 'NOT_FOUND', message: '授权结果不存在' } });
    return json(200, {
      ok: true,
      op: 'data.read',
      mode: request.mode || 'summary',
      result_ref: snapshot.result_ref,
      data_ref: 'data_http_1',
      result_version: snapshot.result_version,
      summary: {
        unit: snapshot.unit,
        time_range: snapshot.time_range,
        queried_at: snapshot.queried_at,
        source: snapshot.source,
        row_count: snapshot.rows.length,
      },
      rows: snapshot.rows.slice(0, 5),
      cursor: null,
      binding_state: 'BOUND_VERIFIED',
    });
  }
  return json(404, { error: { code: 'NOT_FOUND', message: '路由不存在' } });
}

export function createIsolatedFetch({ token, documents = createDocumentsState(), results = createResultState() } = {}) {
  seedResultFixture(results);
  return {
    documents,
    results,
    fetchImpl: async (url, init = {}) => {
      const target = new URL(url);
      if (target.port === '6677' || url.includes(':6677')) {
        const error = new Error('REFUSED_LIVE_PORT');
        error.code = 'REFUSED_LIVE_PORT';
        throw error;
      }
      const headers = init.headers || {};
      const auth = headers.Authorization || headers.authorization || '';
      const authorized = auth === `Bearer ${token}`;
      const method = init.method || 'GET';
      const body = init.body ? JSON.parse(init.body) : null;
      const idempotencyKey = headers['Idempotency-Key'] || headers['idempotency-key'];
      if (target.pathname.startsWith(PAGE_DOCUMENTS_PREFIX)) {
        return dispatchDocuments(documents, {
          method,
          path: target.pathname.slice(PAGE_DOCUMENTS_PREFIX.length) || '/',
          body,
          idempotencyKey,
          authorized,
        });
      }
      if (target.pathname.startsWith(PAGE_RESULT_PREFIX)) {
        return dispatchResult(results, {
          method,
          path: target.pathname.slice(PAGE_RESULT_PREFIX.length) || '/',
          body,
          authorized,
        });
      }
      return json(404, { error: { code: 'NOT_FOUND', message: '路由不存在' } });
    },
  };
}
