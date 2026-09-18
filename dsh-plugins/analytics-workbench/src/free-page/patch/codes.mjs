/** Submit/locate error codes. HTTP semantics reuse board_documents; INVALID_PAGE not INVALID_BOARD. */

export const ERRORS = Object.freeze({
  VERSION_CONFLICT: Object.freeze({ code: 'VERSION_CONFLICT', http: 409 }),
  NOT_FOUND: Object.freeze({ code: 'NOT_FOUND', http: 404 }),
  FORBIDDEN: Object.freeze({ code: 'FORBIDDEN', http: 403 }),
  PREVIEW_EXPIRED: Object.freeze({ code: 'PREVIEW_EXPIRED', http: 409 }),
  PREVIEW_CANCELLED: Object.freeze({ code: 'PREVIEW_CANCELLED', http: 409 }),
  IDEMPOTENCY_CONFLICT: Object.freeze({ code: 'IDEMPOTENCY_CONFLICT', http: 409 }),
  RECEIPT_UNCERTAIN: Object.freeze({ code: 'RECEIPT_UNCERTAIN', http: 0 }),
  INVALID_PAGE: Object.freeze({ code: 'INVALID_PAGE', http: 422 }),
  MAPPING_STALE: Object.freeze({ code: 'MAPPING_STALE', http: 409 }),
  SCOPE_REQUIRES_CONFIRMATION: Object.freeze({ code: 'SCOPE_REQUIRES_CONFIRMATION', http: 409 }),
});

export const PREVIEW_STATUS = Object.freeze(['PENDING', 'APPLIED', 'CANCELLED']);
export const OPERATIONS = Object.freeze(['GENERATE', 'PATCH', 'SAVE', 'ROLLBACK']);
export const IDENTITY_PATTERN = /^[A-Za-z0-9_.:-]{1,128}$/;

export function isIdentity(value) {
  return typeof value === 'string' && IDENTITY_PATTERN.test(value);
}

export function fail(code, extra = {}) {
  const error = ERRORS[code] ?? ERRORS.INVALID_PAGE;
  return Object.freeze({ ok: false, error, widen_to_whole_page: false, keep_draft: true, ...extra });
}
