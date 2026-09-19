/**
 * Shared cancel/receipt semantics (D45/T26).
 *
 * Three entry points used to maintain their own copy of the same branch:
 * editing cancel, preview cancel, and discard-then-navigate. They now share one
 * receipt check, one local cleanup and one failure rule: a receipt that is
 * missing, mismatched, conflicting or failed keeps the current content and the
 * recoverable message. Nothing here changes the server contract.
 */

const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/**
 * A cancel receipt is only accepted when it names the exact thing that was
 * asked to be cancelled. `expected` is the id field of the request; a receipt
 * that answers about something else proves nothing.
 */
export function verifyCancelReceipt(reply, idField, expectedId) {
  if (!record(reply) || reply.status !== 'CANCELLED') return { ok: false, reason: 'missing_receipt' };
  if (reply[idField] !== expectedId) return { ok: false, reason: 'mismatched_receipt' };
  return { ok: true, value: reply };
}

/** Local cleanup is expressed as a patch so the caller keeps a single state writer. */
export function cancelledPatch(kind) {
  if (kind === 'edit') return { editContext: null, preview: null, confirmationUncertain: false, incoming: null };
  if (kind === 'preview') return { preview: null, incoming: null, confirmationUncertain: false };
  if (kind === 'layout') return { layoutDraft: null, incoming: null };
  throw new Error(`未知的取消类型：${kind}`);
}

/** Messages the three entries share, so a user sees one story per outcome. */
export const CANCEL_MESSAGES = Object.freeze({
  edit: '已取消组件编辑及其待确认预览；已保存版本不变。',
  layout: '已取消布局调整；已保存版本不变。',
  preview: '已取消草稿；已保存看板不变。',
  retained: '未取得取消回执，保留当前草稿。',
});

/**
 * Run one cancellation: request, verify the receipt, then — and only then —
 * clear local state. Any failure leaves `preview`/`editContext`/
 * `confirmationUncertain` exactly as they were, so the user can retry or
 * inspect instead of losing the only evidence of what happened.
 *
 * A request that fails outright (network, server error) is normalised to the
 * shared retained message, so all three entries tell one story. An error that
 * already carries a specific, user-facing explanation — the "this draft was
 * saved, cancel cannot undo it" conflict — is passed through unchanged, because
 * collapsing it into the generic message would hide the recovery step.
 */
export async function cancelDraft({ kind, id, idField, request, emit, message = CANCEL_MESSAGES.retained }) {
  // A layout draft is local-only: there is no server object to cancel, so it is
  // cleared without a request. Handling it here keeps every caller from having
  // to special-case it (and from POSTing a cancel for a null preview id).
  if (kind === 'layout') {
    emit({ ...cancelledPatch('layout'), message: CANCEL_MESSAGES.layout });
    return null;
  }
  let reply;
  try {
    reply = await request(kind === 'edit' ? 'cancel_edit' : 'cancel', kind === 'edit' ? { edit_context_id: id } : { preview_id: id });
  } catch (error) {
    if (error?.cancelConflict) throw error;
    throw new Error(message);
  }
  const receipt = verifyCancelReceipt(reply, idField, id);
  if (!receipt.ok) throw new Error(message);
  emit({ ...cancelledPatch(kind), message: CANCEL_MESSAGES[kind] });
  return receipt.value;
}

/**
 * Which cancellation the current state calls for, in the same precedence the
 * workspace shows: an edit context owns its pending preview.
 *
 * `forLeave` changes one thing: a *clean* selection is not a leave obstacle
 * (D42), so leaving must not cancel it. The workspace's own Cancel button still
 * drops a bare selection, which is why the flag exists rather than the rule
 * being global.
 */
export function cancelTarget(state, { forLeave = false } = {}) {
  if (state?.preview?.source === 'fields') return { kind: 'preview', id: state.preview.preview_id, idField: 'preview_id' };
  const dirtyEdit = state?.editContext && (state.preview || state.confirmationUncertain);
  if (state?.editContext && (!forLeave || dirtyEdit)) {
    return { kind: 'edit', id: state.editContext.edit_context_id, idField: 'edit_context_id' };
  }
  if (state?.layoutDraft) return { kind: 'layout', id: null, idField: null };
  if (state?.preview) return { kind: 'preview', id: state.preview.preview_id, idField: 'preview_id' };
  return null;
}
