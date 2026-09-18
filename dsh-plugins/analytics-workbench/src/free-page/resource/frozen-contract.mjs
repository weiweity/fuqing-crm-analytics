/** Lane A freeze target. Do not invent a second bridge protocol. */

export const FROZEN_SCHEMA_VERSION = 'free-page/v1';
export const BRIDGE_PROTOCOL = 'free-page-bridge/v1';
export const BRIDGE_TRANSPORT = 'MessageChannel';
export const IDENTITY_PATTERN = /^[A-Za-z0-9_.:-]{1,128}$/;
export const BINDING_STATES = Object.freeze(['UNBOUND_SAMPLE', 'BOUND_VERIFIED', 'BOUND_STALE']);
export const PAGE_OPERATIONS = Object.freeze(['GENERATE', 'PATCH', 'SAVE', 'ROLLBACK']);
export const PREVIEW_STATUS = Object.freeze(['PENDING', 'APPLIED', 'CANCELLED']);
export const HANDSHAKE_FIELDS = Object.freeze(['protocol', 'instance_id', 'page_id', 'version', 'nonce']);
export const PAGE_TO_HOST_OPS = Object.freeze(['data.read', 'data.cancel']);
export const HOST_TO_PAGE_EVENTS = Object.freeze(['data.chunk', 'data.end', 'data.error', 'binding.state']);
export const FORBIDDEN_OPS = Object.freeze(['sql', 'save', 'http.fetch', 'credential.read']);

export const ERROR_HTTP = Object.freeze({
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

export function isIdentity(value) {
  return typeof value === 'string' && IDENTITY_PATTERN.test(value);
}

export function fail(code, message, extra) {
  const error = { code, message, http: ERROR_HTTP[code] };
  if (extra && typeof extra === 'object') Object.assign(error, extra);
  return { ok: false, error };
}

export function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function exactKeys(value, required, optional = []) {
  if (!record(value)) return false;
  const allowed = new Set([...required, ...optional]);
  return required.every((key) => Object.hasOwn(value, key))
    && Object.keys(value).every((key) => allowed.has(key));
}
