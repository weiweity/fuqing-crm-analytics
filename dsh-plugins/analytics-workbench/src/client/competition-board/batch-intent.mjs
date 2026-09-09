/** One durable browser intent per actor; retries retain the original payload. */
const PREFIX = 'competition-a6-batch-intent:';

function storage() {
  try { return globalThis.sessionStorage; } catch { return undefined; }
}

function key(principal) {
  return PREFIX + JSON.stringify([principal.actor_id, principal.permission_scope]);
}

export function batchIntent(principal, layoutMode, refs, prior = null) {
  const fingerprint = JSON.stringify([layoutMode, refs]);
  let saved = prior;
  if (!saved) {
    try { saved = JSON.parse(storage()?.getItem(key(principal)) || 'null'); } catch { /* optional storage */ }
  }
  if (saved?.fingerprint === fingerprint && saved.payload?.operations?.length) return saved;
  const id = globalThis.crypto.randomUUID().replaceAll('-', '');
  const groups = layoutMode === 'BATCH_MULTI_BOARD' ? refs.map(ref => [ref]) : [refs];
  const payload = {
    schema_version: 'competition-board-batch/v1', batch_id: `batch_${id}`, layout_mode: layoutMode,
    operations: groups.map((group, index) => ({
      board_id: null, endorsed_result_refs: group, layout_mode: layoutMode,
      idempotency_key: `create-${id}-${index}`, operation_id: `op_${id}_${index}`,
      request_fingerprint: group[0].evidence_digest,
      title: layoutMode === 'BATCH_MULTI_BOARD' ? `认可 ${group[0].result_id}` : '8月GSV诊断板',
    })),
  };
  const intent = { fingerprint, payload };
  try { storage()?.setItem(key(principal), JSON.stringify(intent)); } catch { /* in-memory retry remains */ }
  return intent;
}

export function finishBatchIntent(principal, intent) {
  try {
    const saved = JSON.parse(storage()?.getItem(key(principal)) || 'null');
    if (saved?.payload?.batch_id === intent?.payload?.batch_id) storage()?.removeItem(key(principal));
  } catch { /* optional storage */ }
}
