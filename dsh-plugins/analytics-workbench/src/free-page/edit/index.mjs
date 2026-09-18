/**
 * Host-held free-page edit session.
 *
 * saved Vn -> local draft + undo -> patch preview -> explicit confirm -> CAS -> Vn+1
 *                       |                |                |
 *                  cancel/discard   invalid/expired   conflict/unknown reply
 *                       +----------------+----------------+
 *                                  retain Vn
 *
 * D6 = PATCH confirm of a valid preview (original idempotency_key).
 * D9 = explicit SAVE of the host draft. exit/close/cancel/clear-selection do not save.
 * hasActiveEditContext is not dirty by itself (D42).
 */
import { buildSourceIndex, locateSelection, pageIdentity } from '../source-index/index.mjs';
import { applyInnerText, applyRegionOuter, createPatchPreview, rebuildAfterApply } from '../patch/index.mjs';
import { ERRORS, fail, isIdentity } from '../patch/codes.mjs';

function clone(value) {
  return structuredClone(value);
}

function packagesEqual(a, b) {
  return a.html === b.html && a.css === b.css && a.js === b.js;
}

export function hasActiveEditContext(state) {
  return Boolean(state?.edit_context);
}

export function isDirty(state) {
  if (!state?.saved) return false;
  if (state.confirmation_uncertain) return true;
  if (state.preview?.status === 'PENDING') return true;
  return !packagesEqual(state.saved.package, state.draft);
}

export function createEditController({
  store,
  now = () => Date.now(),
  ttl_ms = 15 * 60 * 1000,
  ids = makeIds(),
} = {}) {
  if (!store) throw new Error('store required');
  let state = emptyState();

  function snapshot() {
    return clone(state);
  }

  function set(patch) {
    state = { ...state, ...patch };
    return snapshot();
  }

  function open(page) {
    if (!pageIdentity(page.page_id) || !pageIdentity(page.session_id)) return fail('INVALID_PAGE');
    const pagePackage = clone(page.package);
    let index;
    try {
      index = buildSourceIndex(pagePackage);
    } catch {
      return fail('INVALID_PAGE', { reason: 'index' });
    }
    state = {
      page_id: page.page_id,
      session_id: page.session_id,
      saved: clone(page),
      draft: pagePackage,
      undo_stack: [],
      index,
      mode: 'browse',
      panel: null,
      edit_context: null,
      preview: null,
      confirmation_uncertain: false,
      last_error: null,
      last_idempotency_key: null,
    };
    return { ok: true, state: snapshot() };
  }

  function enterEdit() {
    if (!state.saved) return fail('INVALID_PAGE');
    return { ok: true, state: set({ mode: 'edit', last_error: null }) };
  }

  function exitEdit() {
    return { ok: true, saved: false, state: set({ mode: 'browse', edit_context: null, panel: null }) };
  }

  function closePanel() {
    return { ok: true, saved: false, state: set({ panel: null }) };
  }

  function clearSelection() {
    return { ok: true, saved: false, state: set({ edit_context: null }) };
  }

  function select(selection) {
    if (state.mode !== 'edit') return fail('INVALID_PAGE', { reason: 'not_in_edit_mode' });
    const located = locateSelection(state.index, selection);
    if (!located.ok) {
      set({ last_error: located.error, edit_context: state.edit_context });
      return { ...located, state: snapshot(), submitted: false };
    }
    return {
      ok: true,
      located,
      state: set({
        edit_context: { selection: located.selection, located },
        last_error: null,
      }),
    };
  }

  function switchWholePage() {
    if (state.mode !== 'edit') return fail('INVALID_PAGE', { reason: 'not_in_edit_mode' });
    return select({ kind: 'whole_page', user_switched: true });
  }

  function agentContext() {
    const located = state.edit_context?.located;
    if (!located?.ok) return fail('MAPPING_STALE', { require: 'reselect' });
    const node = located.node;
    const excerpt = node
      ? state.draft.html.slice(node.html_range.start, node.html_range.end)
      : state.draft.html;
    return Object.freeze({
      ok: true,
      context: Object.freeze({
        schema_version: 'free-page-edit-context/v1',
        runtime: 'native-dsh',
        page_id: state.page_id,
        session_id: state.session_id,
        base_version: state.saved.version,
        selection: located.selection,
        scope: located.scope,
        source_excerpt: excerpt,
        related_css: node
          ? node.css_rules.map(rule => rule.text)
          : [state.draft.css],
        related_js: node
          ? node.js_ranges.map(range => state.draft.js.slice(range.start, range.end))
          : [state.draft.js],
        constraint: 'Modify only the selected scope. Do not rewrite the whole page unless scope is whole_package.',
      }),
    });
  }

  function rebindContext(index) {
    const prev = state.edit_context;
    if (!prev?.located?.ok) return { edit_context: prev ?? null };
    if (prev.located.scope === 'whole_package') {
      const located = locateSelection(index, { kind: 'whole_page', user_switched: true });
      if (!located.ok) return { edit_context: null, last_error: located.error };
      return { edit_context: { selection: located.selection, located } };
    }
    const node = prev.located.node;
    const located = locateSelection(index, { kind: node.kind, node_id: node.node_id });
    if (!located.ok) return { edit_context: null, last_error: located.error };
    return { edit_context: { selection: located.selection, located }, last_error: null };
  }

  function applyLocalDraft(nextPackage) {
    if (!state.saved) return fail('INVALID_PAGE');
    let index;
    try {
      index = buildSourceIndex(nextPackage);
    } catch {
      return fail('INVALID_PAGE', { reason: 'index' });
    }
    const bound = rebindContext(index);
    state.undo_stack = [...state.undo_stack, clone(state.draft)];
    const draft = clone(nextPackage);
    return { ok: true, state: set({ draft, index, ...bound }) };
  }

  function undo() {
    if (!state.undo_stack.length) return { ok: true, state: snapshot() };
    const undo_stack = state.undo_stack.slice();
    const draft = undo_stack.pop();
    let index;
    try {
      index = buildSourceIndex(draft);
    } catch {
      return fail('INVALID_PAGE', { reason: 'index' });
    }
    const bound = rebindContext(index);
    return { ok: true, state: set({ draft, undo_stack, index, ...bound }) };
  }

  function previewPatch(proposed, { scope_confirmed = false, impact_hash = null } = {}) {
    if (!state.saved) return fail('INVALID_PAGE');
    if (!state.edit_context?.located?.ok) {
      return fail('MAPPING_STALE', { require: 'reselect', submitted: false });
    }
    const preview_id = ids.preview();
    const idempotency_key = ids.key('patch');
    const created = createPatchPreview({
      index: state.index,
      pagePackage: state.draft,
      selection: state.edit_context.selection,
      proposed,
      page_id: state.page_id,
      session_id: state.session_id,
      base_version: state.saved.version,
      idempotency_key,
      preview_id,
      now_ms: now(),
      ttl_ms,
      scope_confirmed,
      impact_hash,
    });
    if (!created.ok) {
      set({ last_error: created.error });
      return { ...created, state: snapshot(), submitted: false };
    }
    store.putPreview(created.preview);
    set({
      preview: created.preview,
      last_idempotency_key: idempotency_key,
      last_error: null,
      panel: 'patch',
    });
    return { ok: true, preview: created.preview, impact: created.impact, state: snapshot(), submitted: false };
  }

  async function confirmPatch() {
    const preview = state.preview;
    if (!preview || preview.status !== 'PENDING') return fail('NOT_FOUND', { submitted: false });
    const key = preview.idempotency_key;
    set({ confirmation_uncertain: true });
    let result;
    try {
      result = await store.confirmPatch({
        preview_id: preview.preview_id,
        idempotency_key: key,
        now_ms: now(),
      });
    } catch {
      return { ...fail('RECEIPT_UNCERTAIN'), state: snapshot(), submitted: false };
    }
    if (!result.ok) {
      set({ last_error: result.error, confirmation_uncertain: result.error.code === 'RECEIPT_UNCERTAIN' });
      return { ...result, state: snapshot(), submitted: false };
    }
    const page = result.page;
    const index = rebuildAfterApply(page.package);
    set({
      saved: page,
      draft: clone(page.package),
      index,
      preview: null,
      confirmation_uncertain: false,
      last_error: null,
      undo_stack: [],
      edit_context: null,
    });
    return { ok: true, page, operation: 'PATCH', idempotent: result.idempotent === true, state: snapshot() };
  }

  async function saveDraft() {
    if (!state.saved) return fail('INVALID_PAGE');
    if (state.preview?.status === 'PENDING') {
      return fail('INVALID_PAGE', { reason: 'pending_patch_preview', submitted: false });
    }
    if (!isDirty(state) && !state.confirmation_uncertain) {
      return { ok: true, page: clone(state.saved), operation: 'SAVE', noop: true, state: snapshot() };
    }
    const reuse = state.confirmation_uncertain
      && typeof state.last_idempotency_key === 'string'
      && state.last_idempotency_key.startsWith('save_');
    const key = reuse ? state.last_idempotency_key : ids.key('save');
    set({ confirmation_uncertain: true, last_idempotency_key: key });
    let result;
    try {
      result = await store.saveDraft({
        page_id: state.page_id,
        package: state.draft,
        binding_manifest: state.saved.binding_manifest,
        idempotency_key: key,
        base_version: state.saved.version,
      });
    } catch {
      return { ...fail('RECEIPT_UNCERTAIN'), state: snapshot(), submitted: false };
    }
    if (!result.ok) {
      set({ last_error: result.error, confirmation_uncertain: result.error.code === 'RECEIPT_UNCERTAIN' });
      return { ...result, state: snapshot(), submitted: false };
    }
    const page = result.page;
    set({
      saved: page,
      draft: clone(page.package),
      index: rebuildAfterApply(page.package),
      confirmation_uncertain: false,
      last_error: null,
      undo_stack: [],
    });
    return { ok: true, page, operation: 'SAVE', idempotent: result.idempotent === true, state: snapshot() };
  }

  function cancelPreview() {
    if (!state.preview) return { ok: true, saved: false, state: snapshot() };
    const cancelled = store.cancelPreview(state.preview.preview_id);
    if (!cancelled.ok) {
      set({ last_error: cancelled.error });
      return { ...cancelled, saved: false, state: snapshot() };
    }
    return {
      ok: true,
      saved: false,
      preview: cancelled.preview,
      state: set({ preview: null, last_error: null, panel: null }),
    };
  }

  function mutateSelectedText(text) {
    const located = state.edit_context?.located;
    const result = applyInnerText(state.draft, located, text);
    if (!result.ok) return { ...result, state: snapshot() };
    return applyLocalDraft(result.package);
  }

  function mutateSelectedRegion(outerHtml) {
    const located = state.edit_context?.located;
    const result = applyRegionOuter(state.draft, located, outerHtml);
    if (!result.ok) return { ...result, state: snapshot() };
    return applyLocalDraft(result.package);
  }

  return {
    open,
    enterEdit,
    exitEdit,
    closePanel,
    clearSelection,
    select,
    switchWholePage,
    agentContext,
    applyLocalDraft,
    undo,
    previewPatch,
    confirmPatch,
    saveDraft,
    cancelPreview,
    mutateSelectedText,
    mutateSelectedRegion,
    snapshot,
    isDirty: () => isDirty(state),
    hasActiveEditContext: () => hasActiveEditContext(state),
  };
}

function emptyState() {
  return {
    page_id: null,
    session_id: null,
    saved: null,
    draft: null,
    undo_stack: [],
    index: null,
    mode: 'browse',
    panel: null,
    edit_context: null,
    preview: null,
    confirmation_uncertain: false,
    last_error: null,
    last_idempotency_key: null,
  };
}

export function makeIds() {
  let n = 0;
  return {
    preview: () => `preview_${++n}`,
    key: kind => `${kind}_key_${++n}`,
  };
}

export { ERRORS, fail, isIdentity };
