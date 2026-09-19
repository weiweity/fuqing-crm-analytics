/**
 * P12 live adapters: A/B/C/D owner modules.
 * Generate consumes a native Agent page package. Persist and result reads
 * go through isolated HTTP; they do not stay on the in-memory store or
 * C's synthetic fixture when HTTP is configured.
 */
import { buildSourceIndex, locateSelection } from '../../free-page/source-index/index.mjs';
import { createMemoryPageStore } from '../../free-page/patch/index.mjs';
import { buildSrcdoc } from '../../free-page/preview/srcdoc-builder.mjs';
import { FREE_PAGE_SANDBOX } from '../../free-page/runtime/isolation-policy.mjs';
import { FORBIDDEN_OPS } from '../../free-page/bridge/index.mjs';
import { SAMPLE_PACKAGE } from './mock-adapters.mjs';
import { previewLiteralText } from './html-edit-kernel.mjs';
import { buildGenerateContext } from './generate-context.mjs';
import { PAGE_DOCUMENTS_PREFIX, PAGE_RESULT_PREFIX, refuseLivePort } from './page-http.mjs';
import { nativeGenerateUnavailable, normalizePagePackage } from './native-generate.mjs';

function clone(value) {
  return structuredClone(value);
}

function unwrapSpec(body) {
  if (body?.spec?.page_id) return body.spec;
  if (body?.snapshot?.spec?.page_id) return body.snapshot.spec;
  if (body?.page_id) return body;
  return null;
}

function hydrateSpec(spec, prev, now) {
  const pkg = spec.package
    ? clone(spec.package)
    : clone(prev?.package ?? { html: '<html></html>', css: '', js: '', resources: [], node_map: [] });
  const entry = { version: spec.version, title: spec.title, at: now(), package: clone(pkg) };
  const history = [...(prev?.history ?? [])];
  if (spec.page_id && prev?.page_id === spec.page_id && !history.some(item => item.version === spec.version)) {
    history.push(entry);
  }
  const nextHistory = history.length ? history : [entry];
  return {
    page_id: spec.page_id,
    session_id: spec.session_id,
    title: spec.title,
    version: spec.version,
    base_version: spec.version,
    binding_state: spec.binding_state,
    binding_manifest: spec.binding_manifest ?? { bindings: [], result_refs: [] },
    origin_path: spec.origin_path ?? prev?.origin_path,
    package: pkg,
    savedPackage: clone(pkg),
    dirty: false,
    updated_at: now(),
    history: nextHistory,
  };
}

export { PAGE_DOCUMENTS_PREFIX, PAGE_RESULT_PREFIX };

export function createLivePageAdapters({
  now = () => Date.now(),
  actorId = 'actor_alice',
  documentsHttp = null,
  resultHttp = null,
  nativeGenerate = null,
} = {}) {
  const pages = new Map();
  const store = createMemoryPageStore({ now });
  const nativePrompts = [];
  let seq = 0;
  const nextId = prefix => {
    seq += 1;
    return `${prefix}_${globalThis.crypto.randomUUID()}`;
  };

  const preview = Object.freeze({
    kind: 'live-b-preview',
    sandbox: FREE_PAGE_SANDBOX,
    srcdoc(pkg) {
      return buildSrcdoc({
        html: pkg?.html ?? '',
        css: pkg?.css ?? '',
        js: pkg?.js ?? '',
        resources: pkg?.resources ?? [],
        instanceId: 'inst_preview',
        pageId: 'page_preview',
        version: 1,
        nonce: 'nonce_preview',
      });
    },
    pointerEvents(mode) {
      return mode === 'edit' ? 'none' : 'auto';
    },
  });

  async function httpCall(http, prefix, method, path, { body, idempotencyKey } = {}) {
    if (!http?.fetchImpl || !http.base) {
      return { ok: false, reason: 'http_not_configured' };
    }
    const url = refuseLivePort(`${String(http.base).replace(/\/$/, '')}${prefix}${path}`);
    const headers = {};
    if (http.token) headers.Authorization = `Bearer ${http.token}`;
    if (body != null) headers['content-type'] = 'application/json';
    if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
    const res = await http.fetchImpl(url, {
      method,
      headers,
      body: body != null ? JSON.stringify(body) : undefined,
    });
    let json = {};
    try { json = await res.json(); } catch { json = {}; }
    if (!res.ok) {
      const error = new Error(json?.error?.message || 'PAGE_HTTP');
      error.code = json?.error?.code || 'PAGE_HTTP';
      error.status = res.status;
      throw error;
    }
    return { ok: true, body: json, status: res.status };
  }

  async function documentsRequest(method, path, opts = {}) {
    return httpCall(documentsHttp, PAGE_DOCUMENTS_PREFIX, method, path, opts);
  }

  async function resultRequest(method, path, opts = {}) {
    const got = await httpCall(resultHttp, PAGE_RESULT_PREFIX, method, path, opts);
    if (!got.ok) {
      const error = new Error('授权结果桥尚未配置隔离 HTTP');
      error.code = 'RESULT_HTTP_NOT_CONFIGURED';
      throw error;
    }
    return got;
  }

  const bridge = Object.freeze({
    kind: 'live-c-bridge',
    forbidden: [...FORBIDDEN_OPS],
    async readBinding(page) {
      const state = page?.binding_state ?? 'UNBOUND_SAMPLE';
      const bindings = page?.binding_manifest?.bindings ?? [];
      if (resultHttp?.fetchImpl && resultHttp.base) {
        const got = await resultRequest('POST', '/binding-state', {
          body: { manifest: page?.binding_manifest ?? { bindings: [], result_refs: [] } },
        });
        return {
          binding_state: got.body?.binding_state ?? state,
          partial: state === 'BOUND_VERIFIED' && bindings.some(item => item.status !== 'verified'),
          source: page?.binding_manifest?.result_refs?.[0] ?? null,
          forbidden: [...FORBIDDEN_OPS],
        };
      }
      return {
        binding_state: state,
        partial: state === 'BOUND_VERIFIED' && bindings.some(item => item.status !== 'verified'),
        source: page?.binding_manifest?.result_refs?.[0] ?? null,
        forbidden: [...FORBIDDEN_OPS],
      };
    },
    async readResult(request) {
      if (FORBIDDEN_OPS.includes(request?.op)) {
        const error = new Error('BRIDGE_UNKNOWN_OP');
        error.code = 'BRIDGE_UNKNOWN_OP';
        throw error;
      }
      const got = await resultRequest('POST', '/read', {
        body: {
          request: {
            op: 'data.read',
            request_id: request?.request_id ?? nextId('req'),
            result_ref: request?.result_ref ?? 'result_fixture_1',
            mode: request?.mode ?? 'summary',
            instance_id: request?.instance_id,
          },
          manifest: request?.manifest ?? {
            result_refs: [request?.result_ref ?? 'result_fixture_1'],
            bindings: [],
          },
        },
      });
      return got.body;
    },
  });

  const pending = new Map();

  function selectionRequest(selection) {
    if (!selection) return {};
    if (selection.kind === 'whole_page') {
      return { kind: 'whole_page', user_switched: selection.user_switched === true };
    }
    return { kind: selection.kind, node_id: selection.node_id, mapping: selection.mapping, mapping_token: selection.mapping_token, version_hash: selection.version_hash };
  }

  const edit = Object.freeze({
    kind: 'live-d-edit',
    locate(pkg, request) {
      const index = buildSourceIndex(pkg ?? SAMPLE_PACKAGE);
      const located = locateSelection(index, selectionRequest(request));
      if (!located.ok) {
        return {
          ok: false,
          error: { code: located.error.code, message: '映射已失效，请重新选择；不会改为整页' },
          widenToPage: false,
          requireReselect: true,
        };
      }
      return {
        ok: true,
        scope: located.scope,
        kind: located.node?.kind ?? request?.kind,
        node_id: located.node?.node_id ?? request?.node_id,
        label: located.scope === 'whole_package' ? '整页源码包' : located.node?.node_id,
        located,
      };
    },
    previewPatch({ pkg, selection, replacementText, instruction, aiInstruction, page_id, session_id, base_version, binding_manifest }) {
      const result = previewLiteralText({
        pkg,
        selection,
        replacementText,
        instruction,
        aiInstruction,
        page_id: page_id ?? 'page_live',
        session_id: session_id ?? 'native_session_fixture',
        base_version: base_version ?? 1,
        preview_id: nextId('preview'),
        idempotency_key: nextId('idem'),
        now_ms: now(),
        binding_manifest,
      });
      if (!result.ok) {
        const error = new Error(result.error.message);
        error.code = result.error.code;
        error.preview = result;
        throw error;
      }
      const record = {
        preview_id: result.preview.preview_id,
        operation: 'PATCH',
        status: 'PENDING',
        snapshot: result.preview.proposed_package,
        idempotency_key: result.preview.idempotency_key,
        preview: result.preview,
      };
      pending.set(record.preview_id, record);
      return record;
    },
    confirmPatch(previewId) {
      const record = pending.get(previewId);
      if (!record) {
        const error = new Error('NOT_FOUND');
        error.code = 'NOT_FOUND';
        throw error;
      }
      record.status = 'APPLIED';
      return record;
    },
    cancelPatch(previewId) {
      const record = pending.get(previewId);
      if (record) record.status = 'CANCELLED';
      return { preview_id: previewId, status: 'CANCELLED' };
    },
  });

  function remember(spec, prev) {
    const page = hydrateSpec(spec, prev, now);
    pages.set(page.page_id, page);
    if (!store.getPage(page.page_id)) {
      store.seedPage({
        page_id: page.page_id,
        session_id: page.session_id ?? 'native_session_fixture',
        version: page.version ?? 1,
        package: page.package,
        binding_manifest: page.binding_manifest ?? { bindings: [], result_refs: [] },
      });
    }
    return page;
  }

  const assets = Object.freeze({
    kind: 'live-a-assets',
    note: 'Local cache. Server SSOT is page_documents HTTP.',
    list() {
      return [...pages.values()].map(page => ({
        page_id: page.page_id, title: page.title, version: page.version,
        binding_state: page.binding_state, updated_at: page.updated_at,
      }));
    },
    get(pageId) {
      return pages.get(pageId) ?? null;
    },
    put(page) {
      pages.set(page.page_id, page);
      if (!store.getPage(page.page_id)) {
        store.seedPage({
          page_id: page.page_id,
          session_id: page.session_id ?? 'native_session_fixture',
          version: page.version ?? 1,
          package: page.package,
          binding_manifest: page.binding_manifest ?? { bindings: [], result_refs: [] },
        });
      }
      return page;
    },
  });

  const documents = Object.freeze({
    prefix: PAGE_DOCUMENTS_PREFIX,
    async pullList() {
      const got = await documentsRequest('GET', '/pages');
      if (!got.ok) return got;
      if (!Array.isArray(got.body?.items)) throw new Error('页面列表响应不完整，请重试');
      const items = got.body.items;
      for (const item of items) {
        if (item?.page_id) pages.set(item.page_id, { ...(pages.get(item.page_id) ?? {}), ...item });
      }
      return { ok: true, count: items.length };
    },
    async pullPage(pageId) {
      if (typeof pageId !== 'string' || !pageId) {
        return { ok: false, reason: 'invalid_page_id' };
      }
      const got = await documentsRequest('GET', `/pages/${encodeURIComponent(pageId)}`);
      if (!got.ok) return got;
      const spec = unwrapSpec(got.body);
      if (!spec?.page_id || spec.page_id !== pageId) return { ok: false, reason: 'mismatched_snapshot' };
      remember(spec, pages.get(spec.page_id));
      return { ok: true, page_id: spec.page_id };
    },
    async pullHistory(pageId) {
      const got = await documentsRequest('GET', `/pages/${encodeURIComponent(pageId)}/versions`);
      if (!got.ok) return got;
      return { ok: true, items: Array.isArray(got.body) ? got.body : got.body?.items ?? [] };
    },
    async generatePreview(draft) {
      const body = {
        title: draft.title,
        session_id: draft.session_id,
        package: draft.package,
        binding_manifest: draft.binding_manifest ?? { bindings: [], result_refs: [] },
      };
      if (typeof draft.origin_path === 'string' && draft.origin_path) body.origin_path = draft.origin_path;
      return documentsRequest('POST', '/previews', { body });
    },
    async confirmPreview(previewId, idempotencyKey) {
      return documentsRequest('POST', `/previews/${encodeURIComponent(previewId)}/confirm`, { idempotencyKey });
    },
    async cancelPreview(previewId) {
      return documentsRequest('POST', `/previews/${encodeURIComponent(previewId)}/cancel`);
    },
    async patchPreview({ page_id, base_version, package: pagePackage, title }) {
      const body = { base_version, package: pagePackage };
      if (title != null) body.title = title;
      return documentsRequest('POST', `/pages/${encodeURIComponent(page_id)}/patch-preview`, { body });
    },
    async savePreview({ page_id, base_version, title, package: pagePackage, binding_manifest }) {
      return documentsRequest('POST', `/pages/${encodeURIComponent(page_id)}/save-preview`, {
        body: {
          base_version,
          title,
          package: pagePackage,
          binding_manifest: binding_manifest ?? { bindings: [], result_refs: [] },
        },
      });
    },
    async rollbackPreview({ page_id, base_version, to_version }) {
      return documentsRequest('POST', `/pages/${encodeURIComponent(page_id)}/rollback-preview`, {
        body: { base_version, to_version },
      });
    },
    async generateAndConfirm(draft) {
      const made = await documents.generatePreview(draft);
      if (!made.ok) return made;
      const confirmed = await documents.confirmPreview(made.body.preview_id, draft.idempotency_key);
      const spec = unwrapSpec(confirmed.body);
      if (!spec) return { ok: false, reason: 'empty_snapshot' };
      const page = remember(spec, null);
      return { ok: true, spec, page, preview_id: made.body.preview_id };
    },
  });

  return Object.freeze({
    kind: 'p12-live',
    preview,
    bridge,
    edit,
    assets,
    documents,
    nativeChat: Object.freeze({
      kind: 'native-dsh-session',
      prompts: nativePrompts,
      async submitGeneratePrompt(prompt, extras = {}) {
        nativePrompts.push({ prompt, context: buildGenerateContext({ prompt, ...extras }), at: now() });
        if (typeof nativeGenerate !== 'function') throw nativeGenerateUnavailable();
        const pkg = normalizePagePackage(await nativeGenerate(prompt, extras));
        if (!pkg) throw nativeGenerateUnavailable();
        return { accepted: true, runtime: 'dsh-native-agent-only', package: pkg };
      },
      open() { return { reachable: true }; },
    }),
    samplePackage: () => clone(SAMPLE_PACKAGE),
    nextId,
  });
}
