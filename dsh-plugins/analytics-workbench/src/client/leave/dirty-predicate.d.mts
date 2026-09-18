export type LeavePredicateState = {
  layoutDraft?: unknown; saved?: unknown; preview?: unknown; confirmationUncertain?: boolean; editContext?: unknown;
  /** Free-HTML dirty flag folded in by the host (index.tsx); read by unsavedReasons. */
  htmlUnsaved?: boolean;
};
export type UnsavedReason = 'layout_changed' | 'pending_patch_preview' | 'confirmationUncertain';
export function layoutChanged(state: LeavePredicateState | null | undefined): boolean;
export function unsavedReasons(state: LeavePredicateState | null | undefined): UnsavedReason[];
export function hasUnsavedChanges(state: LeavePredicateState | null | undefined): boolean;
export function hasActiveEditContext(state: LeavePredicateState | null | undefined): boolean;
export function discardableDraft(state: LeavePredicateState | null | undefined): boolean;
export const DISCARD_CLEARED_KEYS: readonly ['preview', 'layoutDraft', 'incoming'];
