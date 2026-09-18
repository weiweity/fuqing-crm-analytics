/** Public adapter for Lane E. Host UI owns rendering; this module owns locate/patch/save semantics. */
import { createEditController, hasActiveEditContext, isDirty } from './index.mjs';

export function createFreePageEditAdapter(options) {
  const controller = createEditController(options);
  return Object.freeze({
    open: controller.open,
    enterEdit: controller.enterEdit,
    exitEdit: controller.exitEdit,
    select: controller.select,
    switchWholePage: controller.switchWholePage,
    agentContext: controller.agentContext,
    previewPatch: controller.previewPatch,
    confirmPatch: controller.confirmPatch,
    saveDraft: controller.saveDraft,
    cancelPreview: controller.cancelPreview,
    closePanel: controller.closePanel,
    clearSelection: controller.clearSelection,
    applyLocalDraft: controller.applyLocalDraft,
    undo: controller.undo,
    mutateSelectedText: controller.mutateSelectedText,
    mutateSelectedRegion: controller.mutateSelectedRegion,
    snapshot: controller.snapshot,
    hasActiveEditContext: () => hasActiveEditContext(controller.snapshot()),
    isDirty: () => isDirty(controller.snapshot()),
  });
}
