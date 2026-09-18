/**
 * Save receipt checking (D43/T24).
 *
 * A save is not a read. Its receipt is matched on the asset identity, the
 * idempotency key that was actually sent, and the CAS version the write was
 * based on — never discarded as if a newer navigation had made it irrelevant.
 * A receipt that does not match proves nothing, so the draft is kept.
 */

/** The key the board client sends for a confirm; retrying must reuse it verbatim. */
export function confirmIdempotencyKey(previewId) {
  return `board-confirm:${previewId}`;
}

/**
 * @returns {{ok: true}} only when the receipt names the same asset, the same
 * version the confirmed draft promised, and the idempotency key that was
 * actually sent. Anything else is `ok: false` with a reason the caller can show
 * without claiming the write failed.
 *
 * The key check is what makes the receipt *this* save rather than merely a
 * snapshot that happens to share board/session/version.
 */
export function verifySaveReceipt({ draft, saved, key, confirmationUncertain = false }) {
  if (confirmationUncertain) return { ok: false, reason: 'uncertain' };
  if (!draft || !saved) return { ok: false, reason: 'missing_receipt' };
  const expected = draft.snapshot?.spec;
  const actual = saved.spec;
  if (!expected || !actual) return { ok: false, reason: 'malformed_receipt' };
  if (key !== confirmIdempotencyKey(draft.preview_id)) return { ok: false, reason: 'idempotency_mismatch' };
  if (actual.board_id !== expected.board_id) return { ok: false, reason: 'page_mismatch' };
  if (actual.session_id !== expected.session_id) return { ok: false, reason: 'session_mismatch' };
  if (actual.version !== draft.base_version + 1) return { ok: false, reason: 'cas_mismatch' };
  if (actual.version !== expected.version) return { ok: false, reason: 'version_mismatch' };
  return { ok: true };
}

/** User-facing reasons; none of them asserts the write did or did not land. */
export const SAVE_FAILURE_MESSAGES = Object.freeze({
  uncertain: '保存结果待核对，不能确认已保存；已留在当前页并保留草稿。',
  missing_receipt: '未取得保存回执；已留在当前页并保留草稿，可核对或重试。',
  malformed_receipt: '保存回执不符合合同；已留在当前页并保留草稿。',
  page_mismatch: '保存回执指向另一份资产；已留在当前页并保留草稿。',
  session_mismatch: '保存回执与原会话不一致；已留在当前页并保留草稿。',
  cas_mismatch: '保存回执的版本与本次提交不一致；已留在当前页并保留草稿。',
  version_mismatch: '保存回执与预览版本不一致；已留在当前页并保留草稿。',
  idempotency_mismatch: '保存回执不是本次提交的幂等键；已留在当前页并保留草稿。',
  conflict: '保存冲突：已有更新的版本，未覆盖；已留在当前页并保留草稿。',
  forbidden: '当前权限不允许保存；已留在当前页并保留草稿。',
  failed: '保存未成功；已留在当前页并保留草稿。',
  // A local layout draft has no server-side object yet, so there is nothing a
  // "save and leave" could persist. The user must confirm the layout first.
  layout_unsaved: '布局调整尚未提交保存，不能直接保存并离开。请先检查布局并确认，或放弃修改。',
});

export function saveFailureMessage(reason) {
  return SAVE_FAILURE_MESSAGES[reason] ?? SAVE_FAILURE_MESSAGES.failed;
}
