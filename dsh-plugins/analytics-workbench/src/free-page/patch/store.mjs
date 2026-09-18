/** In-memory stand-in for Lane A page_documents. Tests only; not a second persistence contract. */
import { ERRORS, OPERATIONS, PREVIEW_STATUS, fail, isIdentity } from './codes.mjs';

function clone(value) {
  return structuredClone(value);
}

export function createMemoryPageStore({ now = () => Date.now() } = {}) {
  const pages = new Map();
  const previews = new Map();
  const receipts = new Map();

  return {
    now,
    seedPage(input) {
      if (!isIdentity(input.page_id) || !isIdentity(input.session_id)) {
        throw new Error('INVALID_PAGE');
      }
      const page = {
        page_id: input.page_id,
        session_id: input.session_id,
        version: Number.isInteger(input.version) ? input.version : 1,
        package: clone(input.package),
        binding_manifest: clone(input.binding_manifest ?? { bindings: [], result_refs: [] }),
      };
      pages.set(page.page_id, page);
      return clone(page);
    },
    getPage(page_id) {
      const page = pages.get(page_id);
      return page ? clone(page) : null;
    },
    putPreview(preview) {
      if (!isIdentity(preview.preview_id) || !PREVIEW_STATUS.includes(preview.status)) {
        return fail('INVALID_PAGE');
      }
      if (!OPERATIONS.includes(preview.operation)) return fail('INVALID_PAGE');
      previews.set(preview.preview_id, clone(preview));
      return { ok: true, preview: clone(preview) };
    },
    getPreview(preview_id) {
      const preview = previews.get(preview_id);
      return preview ? clone(preview) : null;
    },
    cancelPreview(preview_id) {
      const preview = previews.get(preview_id);
      if (!preview) return fail('NOT_FOUND');
      if (preview.status === 'APPLIED') return fail('VERSION_CONFLICT');
      preview.status = 'CANCELLED';
      return { ok: true, preview: clone(preview) };
    },
    confirmPatch({ preview_id, idempotency_key, now_ms }) {
      const existing = receipts.get(idempotency_key);
      if (existing) {
        if (existing.operation !== 'PATCH' || existing.preview_id !== preview_id) {
          return fail('IDEMPOTENCY_CONFLICT');
        }
        return { ok: true, page: clone(pages.get(existing.page_id)), operation: 'PATCH', idempotent: true };
      }
      const preview = previews.get(preview_id);
      if (!preview) return fail('NOT_FOUND');
      if (preview.status === 'CANCELLED') return fail('PREVIEW_CANCELLED');
      if (preview.status !== 'PENDING') return fail('VERSION_CONFLICT');
      if (now_ms >= preview.expires_at_ms) return fail('PREVIEW_EXPIRED');
      if (preview.idempotency_key !== idempotency_key) return fail('IDEMPOTENCY_CONFLICT');
      if (preview.operation !== 'PATCH') return fail('INVALID_PAGE');
      const page = pages.get(preview.page_id);
      if (!page) return fail('NOT_FOUND');
      if (page.version !== preview.base_version) return fail('VERSION_CONFLICT');
      page.version += 1;
      page.package = clone(preview.proposed_package);
      if (preview.binding_manifest) page.binding_manifest = clone(preview.binding_manifest);
      preview.status = 'APPLIED';
      receipts.set(idempotency_key, {
        operation: 'PATCH',
        page_id: page.page_id,
        version: page.version,
        preview_id,
      });
      return { ok: true, page: clone(page), operation: 'PATCH', idempotent: false };
    },
    saveDraft({ page_id, package: pagePackage, binding_manifest, idempotency_key, base_version }) {
      const existing = receipts.get(idempotency_key);
      if (existing) {
        if (existing.operation !== 'SAVE' || existing.page_id !== page_id) return fail('IDEMPOTENCY_CONFLICT');
        return { ok: true, page: clone(pages.get(page_id)), operation: 'SAVE', idempotent: true };
      }
      const page = pages.get(page_id);
      if (!page) return fail('NOT_FOUND');
      if (page.version !== base_version) return fail('VERSION_CONFLICT');
      page.version += 1;
      page.package = clone(pagePackage);
      if (binding_manifest) page.binding_manifest = clone(binding_manifest);
      receipts.set(idempotency_key, { operation: 'SAVE', page_id, version: page.version });
      return { ok: true, page: clone(page), operation: 'SAVE', idempotent: false };
    },
    errors: ERRORS,
  };
}
