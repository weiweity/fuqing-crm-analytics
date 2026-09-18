/**
 * Lane E mock adapters for C/D/B public seams.
 * Does not copy other lanes' internals. Real adapters are P12 integration.
 */
import { buildGenerateContext } from './generate-context.mjs';

export const IDENTITY = /^[A-Za-z0-9_.:-]{1,128}$/;
export const BINDING_STATES = Object.freeze(['UNBOUND_SAMPLE', 'BOUND_VERIFIED', 'BOUND_STALE']);
export const OPERATIONS = Object.freeze(['GENERATE', 'PATCH', 'SAVE', 'ROLLBACK']);
export const PREVIEW_STATUS = Object.freeze(['PENDING', 'APPLIED', 'CANCELLED']);

export const SAMPLE_PACKAGE = Object.freeze({
  html: '<!doctype html><html lang="zh-CN"><body><h1 data-shine-node="n_title">示例标题</h1><p>页面内可点击内容</p><button type="button" data-shine-node="n_action">页面按钮</button><a href="#detail" data-shine-node="n_link">页面链接</a><section data-shine-region="r_chart" aria-label="动态图表区域"><canvas width="320" height="120"></canvas><table><caption>图表数据摘要</caption><tbody><tr><th>指标</th><td>示例</td></tr></tbody></table></section></body></html>',
  css: 'h1{font:600 28px/1.3 sans-serif}button,a{pointer-events:auto}',
  js: "document.querySelector('canvas')?.getContext('2d'); document.querySelector('[data-shine-node=\"n_action\"]')?.addEventListener('click', () => { window.__pageClicks = (window.__pageClicks || 0) + 1; });",
  resources: [],
  node_map: [
    { node_id: 'n_title', kind: 'static_element', selector: "[data-shine-node='n_title']" },
    { node_id: 'n_action', kind: 'static_element', selector: "[data-shine-node='n_action']" },
    { node_id: 'n_link', kind: 'static_element', selector: "[data-shine-node='n_link']" },
    { node_id: 'r_chart', kind: 'dynamic_region', selector: "[data-shine-region='r_chart']" },
  ],
});

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}

export function applyTextToShineNode(html, nodeId, text) {
  const escaped = escapeHtml(text);
  const id = String(nodeId ?? '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (!id) return String(html ?? '');
  const re = new RegExp(`(data-shine-node="${id}"[^>]*>)([^<]*)`);
  const source = String(html ?? '');
  if (re.test(source)) return source.replace(re, `$1${escaped}`);
  return source;
}

function identity(value, label) {
  if (typeof value !== 'string' || !IDENTITY.test(value)) throw new Error(`${label} 非法`);
  return value;
}

export function createMockPageAdapters({ now = () => Date.now(), fail = {}, pages = [] } = {}) {
  const nativePrompts = [];
  const previews = new Map();
  let seq = 0;
  const seed = pages.map(page => clone(page));

  function nextId(prefix) {
    seq += 1;
    return `${prefix}_${seq}`;
  }

  const preview = Object.freeze({
    kind: 'mock-b-preview',
    note: 'Mounts srcdoc free HTML. Not Lane B runtime/sandbox implementation.',
    srcdoc(pkg) {
      const css = pkg?.css ? `<style>${pkg.css}</style>` : '';
      const js = pkg?.js ? `<script>${pkg.js}<\/script>` : '';
      return `${css}${pkg?.html ?? ''}${js}`;
    },
    pointerEvents(mode) {
      return mode === 'edit' ? 'none' : 'auto';
    },
  });

  const bridge = Object.freeze({
    kind: 'mock-c-bridge',
    note: 'Read-only result_ref/data_ref. No SQL, token, or page save.',
    async readBinding(page) {
      if (fail.bridge) throw Object.assign(new Error('授权数据桥不可用'), { code: fail.bridge });
      const state = BINDING_STATES.includes(page?.binding_state) ? page.binding_state : 'UNBOUND_SAMPLE';
      const bindings = page?.binding_manifest?.bindings ?? [];
      return {
        binding_state: state,
        partial: state === 'BOUND_VERIFIED' && bindings.some(item => item.status !== 'verified'),
        source: page?.binding_manifest?.result_refs?.[0] ?? null,
        forbidden: ['sql', 'save', 'http.fetch', 'credential.read'],
      };
    },
    async readResult(request) {
      if (['sql', 'save', 'credential.read', 'http.fetch'].includes(request?.op)) {
        const error = new Error('FORBIDDEN');
        error.code = 'FORBIDDEN';
        throw error;
      }
      if (request?.op && request.op !== 'data.read') {
        const error = new Error('BRIDGE_UNKNOWN_OP');
        error.code = 'BRIDGE_UNKNOWN_OP';
        throw error;
      }
      if (fail.result) {
        const error = new Error(fail.result);
        error.code = fail.result;
        throw error;
      }
      return {
        unit: 'CNY',
        time_range: 'fixture',
        queried_at: now(),
        source: 'synthetic-fixture',
        row_count: 0,
        sample: true,
      };
    },
  });

  const edit = Object.freeze({
    kind: 'mock-d-edit',
    note: 'Public locate/preview/confirm seam. Not source-index/patch/edit internals.',
    locate(pkg, request) {
      if (request?.kind === 'whole_page') {
        if (!request.user_switched) {
          const error = new Error('整页范围只有用户主动切换才允许');
          error.code = 'SCOPE_REQUIRES_CONFIRMATION';
          return { ok: false, error, widenToPage: false };
        }
        return { ok: true, scope: 'whole_package', kind: 'whole_page', node_id: 'page', label: '整页源码包' };
      }
      const nodeId = request?.node_id;
      const mapping = request?.mapping ?? 'valid';
      if (mapping === 'stale' || mapping === 'forged' || nodeId === 'n_missing' || nodeId === 'n_forged') {
        const error = new Error('映射已失效，请重新选择；不会改为整页');
        error.code = 'MAPPING_STALE';
        return { ok: false, error, widenToPage: false, requireReselect: true };
      }
      const node = (pkg?.node_map ?? SAMPLE_PACKAGE.node_map).find(item => item.node_id === nodeId);
      if (!node) {
        const error = new Error('找不到可定位节点，请重新选择');
        error.code = 'MAPPING_STALE';
        return { ok: false, error, widenToPage: false, requireReselect: true };
      }
      if (node.kind === 'dynamic_region') {
        return { ok: true, scope: 'declared_region', kind: node.kind, node_id: node.node_id, label: '动态图表/Canvas 所属区域' };
      }
      return { ok: true, scope: 'exact_source_range', kind: node.kind, node_id: node.node_id, label: '静态元素精确范围' };
    },
    previewPatch({ pkg, selection, instruction, affectsShared = false, expiresInMs = 60_000 }) {
      if (fail.patchPreview) {
        const error = new Error(fail.patchPreview);
        error.code = fail.patchPreview;
        throw error;
      }
      if (!selection?.ok) {
        const error = new Error(selection?.error?.message || '没有有效选区');
        error.code = selection?.error?.code || 'MAPPING_STALE';
        throw error;
      }
      const previewId = nextId('preview');
      const snapshot = clone(pkg);
      if (selection.scope === 'exact_source_range') {
        snapshot.html = applyTextToShineNode(snapshot.html, selection.node_id, instruction || '已修改标题');
      } else if (selection.scope === 'declared_region') {
        snapshot.js = `${snapshot.js}; /* region ${selection.node_id} */`;
      } else {
        snapshot.html = `${snapshot.html}<!-- whole page ${escapeHtml(instruction || '')} -->`;
      }
      const expanded = Boolean(affectsShared || selection.affects_shared_css);
      const record = {
        preview_id: previewId,
        operation: 'PATCH',
        status: 'PENDING',
        snapshot,
        base_package: clone(pkg),
        selection,
        expanded_scope: expanded ? 'preview_expanded_range' : selection.scope,
        shared_impact: expanded ? '共享 CSS/JS 会影响未选中区域，需对应确认' : '',
        expires_at_ms: now() + expiresInMs,
        idempotency_key: nextId('idem'),
      };
      previews.set(previewId, record);
      if (expanded && !selection.confirmExpanded) {
        const error = new Error('共享样式影响超出选区，请确认实际范围');
        error.code = 'SCOPE_REQUIRES_CONFIRMATION';
        error.preview = record;
        throw error;
      }
      return record;
    },
    confirmPatch(previewId, { idempotency_key } = {}) {
      const record = previews.get(previewId);
      if (!record) {
        const error = new Error('PREVIEW 不存在');
        error.code = 'NOT_FOUND';
        throw error;
      }
      if (record.status === 'CANCELLED') {
        const error = new Error('PREVIEW_CANCELLED');
        error.code = 'PREVIEW_CANCELLED';
        throw error;
      }
      if (record.expires_at_ms <= now()) {
        const error = new Error('PREVIEW_EXPIRED');
        error.code = 'PREVIEW_EXPIRED';
        throw error;
      }
      if (idempotency_key && idempotency_key !== record.idempotency_key) {
        const error = new Error('IDEMPOTENCY_CONFLICT');
        error.code = 'IDEMPOTENCY_CONFLICT';
        throw error;
      }
      record.status = 'APPLIED';
      return record;
    },
    cancelPatch(previewId) {
      const record = previews.get(previewId);
      if (!record) return { status: 'CANCELLED', preview_id: previewId };
      if (record.status === 'APPLIED') {
        const error = new Error('已确认的补丁不能用取消撤销');
        error.code = 'VERSION_CONFLICT';
        throw error;
      }
      record.status = 'CANCELLED';
      return record;
    },
  });

  const assets = Object.freeze({
    kind: 'mock-a-assets',
    note: 'In-memory pages. Not Lane A page_documents storage.',
    list() { return seed.map(page => ({ page_id: page.page_id, title: page.title, version: page.version, binding_state: page.binding_state, updated_at: page.updated_at })); },
    get(pageId) { return seed.find(page => page.page_id === pageId) ?? null; },
    put(page) {
      identity(page.page_id, 'page_id');
      const index = seed.findIndex(item => item.page_id === page.page_id);
      if (index < 0) seed.push(page);
      else seed[index] = page;
      return page;
    },
  });

  const nativeChat = Object.freeze({
    kind: 'native-dsh-session',
    note: 'Records prompts for the existing Agent. Does not create a second router.',
    prompts: nativePrompts,
    submitGeneratePrompt(prompt, context) {
      if (fail.generate) {
        const error = new Error(typeof fail.generate === 'string' ? fail.generate : '生成失败，已保留输入');
        error.code = 'GENERATE_FAILED';
        throw error;
      }
      nativePrompts.push({ prompt, context: buildGenerateContext({ prompt, ...context }), at: now() });
      return { accepted: true, runtime: 'dsh-native-agent-only' };
    },
    open() { return { reachable: true }; },
  });

  return Object.freeze({
    kind: 'lane-e-mock',
    preview, bridge, edit, assets, nativeChat,
    samplePackage: () => clone(SAMPLE_PACKAGE),
    nextId,
  });
}
