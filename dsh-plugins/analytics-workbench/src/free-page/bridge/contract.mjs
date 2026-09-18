/** Frozen free-page-bridge/v1 constants. Must stay aligned with fixtures/frozen-contract-v0.json. */

export const PROTOCOL = 'free-page-bridge/v1';
export const SCHEMA_VERSION = 'free-page/v1';
export const TRANSPORT = 'MessageChannel';
export const DATA_SCOPE = 'free-page-result-fixture';
export const IDENTITY = /^[A-Za-z0-9_.:-]{1,128}$/;
export const BINDING_STATES = Object.freeze(['UNBOUND_SAMPLE', 'BOUND_VERIFIED', 'BOUND_STALE']);
export const HANDSHAKE_FIELDS = Object.freeze(['protocol', 'instance_id', 'page_id', 'version', 'nonce']);
export const PAGE_TO_HOST_OPS = Object.freeze(['data.read', 'data.cancel']);
export const HOST_TO_PAGE_EVENTS = Object.freeze(['data.chunk', 'data.end', 'data.error', 'binding.state']);
export const FORBIDDEN_OPS = Object.freeze(['sql', 'save', 'http.fetch', 'credential.read']);
export const FORBIDDEN_FIELDS = Object.freeze([
  'sql', 'token', 'query', 'save', 'credential', 'authorization', 'fetch', 'url', 'headers', 'http', 'password', 'secret',
]);
export const SUMMARY_FIELDS = Object.freeze(['unit', 'time_range', 'queried_at', 'source', 'row_count']);
export const READ_MODES = Object.freeze(['summary', 'page', 'range']);
export const MAX_RESPONSE_BYTES = 65536;
export const MAX_CUMULATIVE_ROWS = 2000;
export const MAX_PAGE_LIMIT = 50;
export const SUMMARY_PREVIEW_ROWS = 5;
export const ERRORS = Object.freeze({
  VERSION_CONFLICT: 409,
  NOT_FOUND: 404,
  FORBIDDEN: 403,
  PREVIEW_EXPIRED: 409,
  PREVIEW_CANCELLED: 409,
  IDEMPOTENCY_CONFLICT: 409,
  INVALID_PAGE: 422,
  RESULT_UNAVAILABLE: 409,
  RESULT_STALE: 409,
  RESULT_REVOKED: 403,
  MAPPING_STALE: 409,
  SCOPE_REQUIRES_CONFIRMATION: 409,
  RESOURCE_HASH_MISMATCH: 409,
  PACKAGE_TOO_LARGE: 413,
  BRIDGE_UNKNOWN_OP: 400,
  BRIDGE_NONCE: 409,
  BRIDGE_EXPIRED_INSTANCE: 409,
});

export const MESSAGES = Object.freeze({
  FORBIDDEN: '当前身份无权读取该授权结果。',
  NOT_FOUND: '授权结果不存在，或当前身份不可见。',
  RESULT_UNAVAILABLE: '授权结果当前不可用，页面仍可打开；请改走原生问数。',
  RESULT_STALE: '授权结果已过期或单位/时间/版本不符，宿主标记为过期。',
  RESULT_REVOKED: '授权结果已被撤销，不能继续读取。',
  BRIDGE_UNKNOWN_OP: '页面请求了未授权的桥接操作。',
  BRIDGE_NONCE: '桥接 nonce 无效或已使用，请重新握手。',
  BRIDGE_EXPIRED_INSTANCE: '页面实例已过期，请重新握手。',
  INVALID_PAGE: '页面绑定或读取请求不符合合同。',
  PACKAGE_TOO_LARGE: '单次或累计读取超过额度。',
});

export function identity(value) {
  return typeof value === 'string' && IDENTITY.test(value);
}

export function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function exact(value, required, optional = []) {
  if (!record(value)) return false;
  const allowed = new Set([...required, ...optional]);
  return required.every(key => Object.hasOwn(value, key))
    && Object.keys(value).every(key => allowed.has(key));
}

export function bridgeError(code, message) {
  const resolved = MESSAGES[code] ? code : 'BRIDGE_UNKNOWN_OP';
  const error = new Error(message ?? MESSAGES[resolved]);
  error.code = resolved;
  error.status = ERRORS[resolved];
  return error;
}
