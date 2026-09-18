/**
 * P12 live adapters: owner modules from A/B/C/D, not E's in-process mocks.
 * Persistence here uses D's memory store until HTTP page_documents is called.
 * C's createSyntheticAccess is still a fixture result store (declared mock).
 */
import { buildSourceIndex, locateSelection } from '../../free-page/source-index/index.mjs';
import { applyInnerText, createPatchPreview, createMemoryPageStore } from '../../free-page/patch/index.mjs';
import { buildSrcdoc } from '../../free-page/preview/srcdoc-builder.mjs';
import { FREE_PAGE_SANDBOX } from '../../free-page/runtime/isolation-policy.mjs';
import { createSyntheticAccess, defaultSyntheticSnapshot, FORBIDDEN_OPS } from '../../free-page/bridge/index.mjs';
import { SAMPLE_PACKAGE, escapeHtml } from './mock-adapters.mjs';
import { buildGenerateContext } from './generate-context.mjs';

function clone(value) {
  return structuredClone(value);
}

export const PAGE_DOCUMENTS_PREFIX = '/api/v1/analytics/page-documents';

export function createLivePageAdapters({ now = () => Date.now(), actorId = 'actor_alice', documentsHttp = null } = {}) {
  const pages = new Map();
  const store = createMemoryPageStore({ now });
  const access = createSyntheticAccess({ actor: { actor_id: actorId } });
  access.putSnapshot(defaultSyntheticSnapshot());
  const nativePrompts = [];
  let seq = 0;
  const nextId = prefix => {
    seq += 1;
    return `${prefix}_${seq}`;
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

  const bridge = Object.freeze({
    kind: 'live-c-bridge',
    forbidden: [...FORBIDDEN_OPS],
    async readBinding(page) {
      const state = page?.binding_state ?? 'UNBOUND_SAMPLE';
      const bindings = page?.binding_manifest?.bindings ?? [];
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
      return access.read({
        op: 'data.read',
        request_id: request?.request_id ?? nextId('req'),
        result_ref: request?.result_ref ?? 'result_fixture_1',
        mode: request?.mode ?? 'summary',
      }, { actor: { actor_id: actorId } });
    },
  });

  const pending = new Map();

  function selectionRequest(selection) {
    if (!selection) return {};
    if (selection.kind === 'whole_page') {
      return { kind: 'whole_page', user_switched: selection.user_switched === true };
    }
    return { kind: selection.kind, node_id: selection.node_id, mapping: selection.mapping };
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
    previewPatch({ pkg, selection, instruction }) {
      const index = buildSourceIndex(pkg);
      const request = selectionRequest(selection);
      const located = locateSelection(index, request);
      if (!located?.ok) {
        const error = new Error('MAPPING_STALE');
        error.code = 'MAPPING_STALE';
        throw error;
      }
      let proposed = clone(pkg);
      if (located.scope === 'exact_source_range') {
        const applied = applyInnerText(pkg, located, instruction || '已修改标题');
        if (!applied.ok) {
          const error = new Error(applied.error.code);
          error.code = applied.error.code;
          throw error;
        }
        proposed = applied.package;
      } else if (located.scope === 'whole_package') {
        proposed = { ...proposed, html: `${proposed.html}<!-- ${escapeHtml(instruction || '')} -->` };
      }
      const made = createPatchPreview({
        index,
        pagePackage: pkg,
        selection: request,
        proposed,
        page_id: 'page_live',
        session_id: 'native_session_fixture',
        base_version: 1,
        idempotency_key: nextId('idem'),
        preview_id: nextId('preview'),
        now_ms: now(),
      });
      if (!made.ok) {
        const error = new Error(made.error.code);
        error.code = made.error.code;
        error.preview = made;
        throw error;
      }
      const record = {
        preview_id: made.preview.preview_id,
        operation: 'PATCH',
        status: 'PENDING',
        snapshot: made.preview.proposed_package,
        idempotency_key: made.preview.idempotency_key,
        preview: made.preview,
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

  const assets = Object.freeze({
    kind: 'live-a-assets',
    note: 'JS index plus D memory store. Server SSOT is page_documents HTTP.',
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

  async function documentsGet(path) {
    if (!documentsHttp?.fetchImpl || !documentsHttp.base) {
      return { ok: false, reason: 'http_not_configured' };
    }
    const url = `${String(documentsHttp.base).replace(/\/$/, '')}${PAGE_DOCUMENTS_PREFIX}${path}`;
    if (url.includes(':6677')) {
      const error = new Error('PAGE_DOCUMENTS_HTTP');
      error.code = 'REFUSED_LIVE_PORT';
      throw error;
    }
    const res = await documentsHttp.fetchImpl(url, {
      headers: documentsHttp.token ? { Authorization: `Bearer ${documentsHttp.token}` } : {},
    });
    if (!res.ok) {
      const error = new Error('PAGE_DOCUMENTS_HTTP');
      error.code = 'PAGE_DOCUMENTS_HTTP';
      error.status = res.status;
      throw error;
    }
    return { ok: true, body: await res.json() };
  }

  const documents = Object.freeze({
    prefix: PAGE_DOCUMENTS_PREFIX,
    async pullList() {
      const got = await documentsGet('/pages');
      if (!got.ok) return got;
      const items = Array.isArray(got.body?.items) ? got.body.items : [];
      for (const item of items) {
        if (item?.page_id) pages.set(item.page_id, { ...(pages.get(item.page_id) ?? {}), ...item });
      }
      return { ok: true, count: items.length };
    },
    async pullPage(pageId) {
      if (typeof pageId !== 'string' || !pageId) {
        return { ok: false, reason: 'invalid_page_id' };
      }
      const got = await documentsGet(`/pages/${encodeURIComponent(pageId)}`);
      if (!got.ok) return got;
      const item = got.body;
      if (!item?.page_id) return { ok: false, reason: 'empty_snapshot' };
      pages.set(item.page_id, { ...(pages.get(item.page_id) ?? {}), ...item });
      return { ok: true, page_id: item.page_id };
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
      submitGeneratePrompt(prompt, extras = {}) {
        nativePrompts.push({ prompt, context: buildGenerateContext({ prompt, ...extras }), at: now() });
        return { accepted: true, runtime: 'dsh-native-agent-only' };
      },
      open() { return { reachable: true }; },
    }),
    samplePackage: () => clone(SAMPLE_PACKAGE),
    nextId,
  });
}
