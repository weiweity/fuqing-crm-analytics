/**
 * Leave predicates (D42/T23).
 *
 * `hasUnsavedChanges` and `hasActiveEditContext` are separate questions:
 *
 *   hasUnsavedChanges     - is there work the user would lose by leaving?
 *   hasActiveEditContext  - is there a selection/focus context to resume?
 *
 * A just-selected element is a *clean* context: it must not raise the leave
 * prompt, and leaving must not call `cancel_edit` on it. Only a pending AI
 * patch, an *actually changed* local layout, or an uncertain save receipt count
 * as unsaved work.
 *
 * "Actually changed" matters: entering layout mode copies the saved snapshot
 * into `layoutDraft` before the user has moved anything, so the presence of a
 * draft is not by itself a modification.
 */
import { changedLayouts } from '../../board-spec/grid-layout.mjs';

/** True when the local layout draft really differs from the saved snapshot. */
export function layoutChanged(state) {
  const draft = state?.layoutDraft, saved = state?.saved;
  if (!draft) return false;
  // Without a saved head to compare against, a draft is the only copy of the
  // user's work: treat it as a change rather than silently dropping it.
  if (!saved?.spec || !draft.spec) return true;
  return changedLayouts(saved.spec, draft.spec).length > 0;
}

/** Why the current page is considered dirty. Empty array means clean. */
export function unsavedReasons(state) {
  const reasons = [];
  if (layoutChanged(state)) reasons.push('layout_changed');
  if (state?.preview) reasons.push('pending_patch_preview');
  if (state?.confirmationUncertain) reasons.push('confirmationUncertain');
  if (state?.fieldDraft) reasons.push('field_draft');
  if (state?.htmlUnsaved) reasons.push('html_unsaved');
  return reasons;
}

export function hasUnsavedChanges(state) {
  return unsavedReasons(state).length > 0;
}

/** A selection alone is not a reason to block leaving; it is a resume target. */
export function hasActiveEditContext(state) {
  return Boolean(state?.editContext);
}

/**
 * What a discard must clear, and what must survive it.
 *
 * `confirmationUncertain` is deliberately NOT part of the cleared set: it is
 * the only evidence that a write may have landed, and a discard must not turn
 * an unknown result into a clean page. It is cleared only where a *verified*
 * cancel receipt proves the draft did not land — a `CANCELLED` status, since an
 * already-applied draft is refused with `VERSION_CONFLICT` instead.
 */
export function discardableDraft(state) {
  return Boolean(state?.fieldDraft || state?.preview || layoutChanged(state) || state?.htmlUnsaved);
}

/** Local state a verified discard clears. `confirmationUncertain` is cleared separately, on proof. */
export const DISCARD_CLEARED_KEYS = Object.freeze(['preview', 'layoutDraft', 'incoming']);
