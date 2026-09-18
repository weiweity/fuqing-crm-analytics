/** Free-page/v1 package, manifest and bridge validators. Not a BoardSpec catalogue. */

const IDENTITY = /^[A-Za-z0-9_.:-]{1,128}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const BINDING_STATES = new Set(['UNBOUND_SAMPLE', 'BOUND_VERIFIED', 'BOUND_STALE']);
const NODE_KINDS = new Set(['static_element', 'dynamic_region', 'whole_page']);
const PAGE_OPS = new Set(['GENERATE', 'PATCH', 'SAVE', 'ROLLBACK']);
const PAGE_TO_HOST = new Set(['data.read', 'data.cancel']);
const HOST_TO_PAGE = new Set(['data.chunk', 'data.end', 'data.error', 'binding.state']);
const FORBIDDEN_OPS = new Set(['sql', 'save', 'http.fetch', 'credential.read']);
const HTML_MAX = 1_048_576;
const STYLE_MAX = 524_288;
const PACKAGE_MAX = 2_000_000;
const READ_LIMIT_MAX = 50;
const BUDGET_BYTES = 65536;
const BUDGET_ROWS = 2000;
const READ_MODES = new Set(['summary', 'page', 'range']);
const utf8 = new TextEncoder();
const BRIDGE_KEYS = {
  'data.read': new Set(['protocol', 'instance_id', 'request_id', 'nonce', 'seq', 'op', 'result_ref', 'mode', 'cursor', 'limit']),
  'data.cancel': new Set(['protocol', 'instance_id', 'request_id', 'nonce', 'seq', 'op']),
  'data.chunk': new Set(['protocol', 'instance_id', 'request_id', 'nonce', 'seq', 'op', 'unit', 'time_range', 'queried_at', 'source', 'row_count', 'byte_length']),
  'data.end': new Set(['protocol', 'instance_id', 'request_id', 'nonce', 'seq', 'op']),
  'data.error': new Set(['protocol', 'instance_id', 'request_id', 'nonce', 'seq', 'op', 'code', 'message']),
  'binding.state': new Set(['protocol', 'instance_id', 'request_id', 'nonce', 'seq', 'op', 'binding_state']),
};

function utf8Bytes(text) {
  return utf8.encode(text).byteLength;
}

function fail(code, message) {
  return { ok: false, error: { code, message } };
}

function ok(value) {
  return { ok: true, value };
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function extraKeys(value, allowed) {
  return Object.keys(value).filter((key) => !allowed.has(key));
}

function opaque(value, label) {
  if (typeof value !== 'string' || !IDENTITY.test(value)) {
    return `${label} 不是合法标识`;
  }
  return null;
}

/**
 * @param {unknown} raw
 * @returns {{ ok: true, value: object } | { ok: false, error: { code: string, message: string } }}
 */
export function parsePagePackage(raw) {
  if (!isPlainObject(raw)) return fail('INVALID_PAGE', '源码包必须是对象');
  const unknown = extraKeys(raw, new Set(['html', 'css', 'js', 'resources', 'node_map']));
  if (unknown.length) return fail('INVALID_PAGE', `源码包含未知字段: ${unknown.join(',')}`);
  if (typeof raw.html !== 'string' || !raw.html.trim() || raw.html.length > HTML_MAX) {
    return fail('INVALID_PAGE', 'html 必须是非空源码');
  }
  const css = raw.css ?? '';
  const js = raw.js ?? '';
  if (typeof css !== 'string' || css.length > STYLE_MAX) return fail('INVALID_PAGE', 'css 超限或类型错误');
  if (typeof js !== 'string' || js.length > STYLE_MAX) return fail('INVALID_PAGE', 'js 超限或类型错误');
  const resources = raw.resources ?? [];
  const nodeMap = raw.node_map ?? [];
  if (!Array.isArray(resources) || resources.length > 32) return fail('INVALID_PAGE', 'resources 非法');
  if (!Array.isArray(nodeMap) || nodeMap.length > 2000) return fail('INVALID_PAGE', 'node_map 非法');
  const resourceIds = new Set();
  let bytes = utf8Bytes(raw.html) + utf8Bytes(css) + utf8Bytes(js);
  for (const item of resources) {
    if (!isPlainObject(item)) return fail('INVALID_PAGE', 'resource 必须是对象');
    if (extraKeys(item, new Set(['resource_id', 'content_type', 'sha256', 'byte_length'])).length) {
      return fail('INVALID_PAGE', 'resource 含未知字段');
    }
    if (opaque(item.resource_id, 'resource_id') || resourceIds.has(item.resource_id)) {
      return fail('INVALID_PAGE', 'resource_id 非法或重复');
    }
    resourceIds.add(item.resource_id);
    if (typeof item.content_type !== 'string' || !item.content_type.includes('/')) {
      return fail('INVALID_PAGE', 'content_type 非法');
    }
    if (typeof item.sha256 !== 'string' || !SHA256.test(item.sha256)) return fail('INVALID_PAGE', '资源 hash 非法');
    if (!Number.isInteger(item.byte_length) || item.byte_length < 0 || item.byte_length > PACKAGE_MAX) {
      return fail('INVALID_PAGE', 'byte_length 非法');
    }
    bytes += item.byte_length;
  }
  const nodeIds = new Set();
  for (const item of nodeMap) {
    if (!isPlainObject(item)) return fail('INVALID_PAGE', 'node_map 项必须是对象');
    if (extraKeys(item, new Set(['node_id', 'kind', 'selector'])).length) return fail('INVALID_PAGE', 'node_map 含未知字段');
    if (opaque(item.node_id, 'node_id') || nodeIds.has(item.node_id)) return fail('INVALID_PAGE', 'node_id 非法或重复');
    nodeIds.add(item.node_id);
    if (!NODE_KINDS.has(item.kind)) return fail('INVALID_PAGE', 'node kind 非法');
    if (typeof item.selector !== 'string' || !item.selector.trim()) return fail('INVALID_PAGE', 'selector 非法');
  }
  if (bytes > PACKAGE_MAX) return fail('PACKAGE_TOO_LARGE', '页面源码包超过大小上限');
  return ok({ html: raw.html, css, js, resources, node_map: nodeMap });
}

/**
 * @param {unknown} raw
 */
export function parseBindingManifest(raw) {
  if (!isPlainObject(raw)) return fail('INVALID_PAGE', 'binding manifest 必须是对象');
  if (extraKeys(raw, new Set(['bindings', 'result_refs'])).length) return fail('INVALID_PAGE', 'manifest 含未知字段');
  const bindings = raw.bindings ?? [];
  const resultRefs = raw.result_refs ?? [];
  if (!Array.isArray(bindings) || !Array.isArray(resultRefs)) return fail('INVALID_PAGE', 'manifest 数组非法');
  const declared = new Set();
  for (const ref of resultRefs) {
    if (opaque(ref, 'result_ref') || declared.has(ref)) return fail('INVALID_PAGE', 'result_ref 非法或重复');
    declared.add(ref);
  }
  const bindingIds = new Set();
  for (const item of bindings) {
    if (!isPlainObject(item)) return fail('INVALID_PAGE', 'binding 必须是对象');
    if (extraKeys(item, new Set(['binding_id', 'result_ref', 'node_id', 'data_ref', 'mode'])).length) {
      return fail('INVALID_PAGE', 'binding 含未知字段');
    }
    if (opaque(item.binding_id, 'binding_id') || bindingIds.has(item.binding_id)) {
      return fail('INVALID_PAGE', 'binding_id 非法或重复');
    }
    bindingIds.add(item.binding_id);
    if (item.mode != null && !READ_MODES.has(item.mode)) return fail('INVALID_PAGE', 'binding mode 非法');
    if (!declared.has(item.result_ref)) return fail('INVALID_PAGE', 'binding result_ref 未声明');
  }
  return ok({ bindings, result_refs: resultRefs });
}

/**
 * @param {unknown} raw
 */
export function parsePageDocument(raw) {
  if (!isPlainObject(raw)) return fail('INVALID_PAGE', '页面文档必须是对象');
  if ('blocks' in raw || 'board_id' in raw) return fail('INVALID_PAGE', '不能把 BoardSpec 当作页面资产');
  const allowed = new Set(['schema_version', 'page_id', 'session_id', 'title', 'version',
    'binding_state', 'package', 'binding_manifest']);
  if (extraKeys(raw, allowed).length) return fail('INVALID_PAGE', '页面文档含未知字段');
  if (raw.schema_version !== 'free-page/v1') return fail('INVALID_PAGE', 'schema_version 必须是 free-page/v1');
  for (const key of ['page_id', 'session_id']) {
    const message = opaque(raw[key], key);
    if (message) return fail('INVALID_PAGE', message);
  }
  if (typeof raw.title !== 'string' || !raw.title.trim()) return fail('INVALID_PAGE', 'title 非法');
  if (!Number.isInteger(raw.version) || raw.version < 1) return fail('INVALID_PAGE', 'version 非法');
  if (!BINDING_STATES.has(raw.binding_state)) return fail('INVALID_PAGE', 'binding_state 非法');
  const pack = parsePagePackage(raw.package);
  if (!pack.ok) return pack;
  const manifest = parseBindingManifest(raw.binding_manifest ?? { bindings: [], result_refs: [] });
  if (!manifest.ok) return manifest;
  const unbound = manifest.value.result_refs.length === 0;
  if (unbound && raw.binding_state !== 'UNBOUND_SAMPLE') {
    return fail('INVALID_PAGE', '无 result_refs 时只能是 UNBOUND_SAMPLE');
  }
  if (!unbound && raw.binding_state === 'UNBOUND_SAMPLE') {
    return fail('INVALID_PAGE', '未绑定页不能声明 result_refs');
  }
  return ok({
    schema_version: 'free-page/v1',
    page_id: raw.page_id,
    session_id: raw.session_id,
    title: raw.title,
    version: raw.version,
    binding_state: raw.binding_state,
    package: pack.value,
    binding_manifest: manifest.value,
  });
}

/**
 * @param {unknown} raw
 * @param {{ instance_id?: string, nonce?: string, expired?: boolean }} [session]
 */
export function parseBridgeMessage(raw, session = {}) {
  if (!isPlainObject(raw)) return fail('BRIDGE_UNKNOWN_OP', '桥消息必须是对象');
  if (typeof raw.op !== 'string') return fail('BRIDGE_UNKNOWN_OP', '缺少 op');
  if (FORBIDDEN_OPS.has(raw.op) || !(PAGE_TO_HOST.has(raw.op) || HOST_TO_PAGE.has(raw.op))) {
    return fail('BRIDGE_UNKNOWN_OP', `未知或禁止的桥操作: ${raw.op}`);
  }
  if (extraKeys(raw, BRIDGE_KEYS[raw.op]).length) return fail('INVALID_PAGE', '桥消息含未知字段');
  if (raw.protocol !== 'free-page-bridge/v1') return fail('BRIDGE_UNKNOWN_OP', '协议版本不匹配');
  if (session.expired) return fail('BRIDGE_EXPIRED_INSTANCE', '桥接实例已过期');
  if (session.nonce != null && raw.nonce !== session.nonce) return fail('BRIDGE_NONCE', 'nonce 无效');
  if (session.instance_id != null && raw.instance_id !== session.instance_id) {
    return fail('BRIDGE_EXPIRED_INSTANCE', '实例不匹配');
  }
  if (!Number.isInteger(raw.seq) || raw.seq < 0) return fail('INVALID_PAGE', 'seq 非法');
  if (raw.op === 'data.read') {
    if (opaque(raw.result_ref, 'result_ref')) return fail('INVALID_PAGE', 'result_ref 非法');
    if (raw.mode != null && !READ_MODES.has(raw.mode)) return fail('INVALID_PAGE', 'read mode 非法');
    const limit = raw.limit ?? 50;
    if (!Number.isInteger(limit) || limit < 1 || limit > READ_LIMIT_MAX) return fail('INVALID_PAGE', 'limit 超限');
  }
  if (raw.op === 'data.chunk') {
    if (raw.byte_length != null && (raw.byte_length < 0 || raw.byte_length > BUDGET_BYTES)) {
      return fail('PACKAGE_TOO_LARGE', '桥响应超过额度');
    }
    if (raw.row_count != null && (raw.row_count < 0 || raw.row_count > BUDGET_ROWS)) {
      return fail('PACKAGE_TOO_LARGE', '桥累计行数超过额度');
    }
  }
  return ok(raw);
}

export const PAGE_OPERATIONS = [...PAGE_OPS];
export const BINDING_STATE_VALUES = [...BINDING_STATES];
export const FORBIDDEN_BRIDGE_OPS = [...FORBIDDEN_OPS];
