/**
 * Save-receipt checking (T24/T25, D43).
 *
 * The frozen contract names the check as
 * `[idempotency_key, CAS, page_id, base_version]`. The key matters most: a
 * snapshot that merely shares board/session/version with the draft is not proof
 * that *this* save landed, and treating it as one would let the coordinator
 * navigate away on someone else's write.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { verifySaveReceipt, confirmIdempotencyKey, saveFailureMessage, SAVE_FAILURE_MESSAGES } from './save-receipt.mjs';
import { librarySnapshot as snap, libraryPreview as draft } from '../../../test/helpers/library-board-fixtures.mjs';

const frozen = JSON.parse(await readFile(new URL('../../../../../docs/hackathon/free-html-cockpit/fixtures/leave-epoch.fixture.json', import.meta.url), 'utf8'));

const applied = () => snap({ version: 2, content: '已保存' });

test('the frozen fixture names the fields the check actually uses', () => {
  assert.deepEqual([...frozen.epoch.save_receipt_check], ['idempotency_key', 'CAS', 'page_id', 'base_version']);
  // idempotency_key -> the key argument; CAS + base_version -> cas_mismatch;
  // page_id -> page_mismatch.
  const pending = draft(applied());
  const key = confirmIdempotencyKey(pending.preview_id);
  assert.equal(key, `board-confirm:${pending.preview_id}`, 'the key is derived from the preview it confirms');
  assert.deepEqual(verifySaveReceipt({ draft: pending, saved: applied(), key }), { ok: true });
});

test('a matching board/session/version is not enough: the key must be this save', () => {
  const pending = draft(applied());
  const saved = applied();
  const mine = confirmIdempotencyKey(pending.preview_id);
  assert.deepEqual(verifySaveReceipt({ draft: pending, saved, key: mine }), { ok: true });
  // A receipt from a different confirm must not pass, however plausible it looks.
  assert.deepEqual(verifySaveReceipt({ draft: pending, saved, key: confirmIdempotencyKey('another_preview') }),
    { ok: false, reason: 'idempotency_mismatch' });
  assert.deepEqual(verifySaveReceipt({ draft: pending, saved, key: undefined }), { ok: false, reason: 'idempotency_mismatch' });
  assert.deepEqual(verifySaveReceipt({ draft: pending, saved, key: 'board-confirm:' }), { ok: false, reason: 'idempotency_mismatch' });
});

test('each CAS / identity failure is named separately', () => {
  const pending = draft(applied());
  const key = confirmIdempotencyKey(pending.preview_id);
  const base = { draft: pending, key };
  assert.deepEqual(verifySaveReceipt({ ...base, saved: snap({ boardId: 'other', version: 2 }) }),
    { ok: false, reason: 'page_mismatch' });
  assert.deepEqual(verifySaveReceipt({ ...base, saved: snap({ version: 3 }) }), { ok: false, reason: 'cas_mismatch' });
  assert.deepEqual(verifySaveReceipt({ ...base, saved: null }), { ok: false, reason: 'missing_receipt' });
  assert.deepEqual(verifySaveReceipt({ ...base, draft: null, saved: applied() }), { ok: false, reason: 'missing_receipt' });
  assert.deepEqual(verifySaveReceipt({ draft: { preview_id: pending.preview_id, base_version: 1, snapshot: {} }, saved: applied(), key }),
    { ok: false, reason: 'malformed_receipt' });
  assert.deepEqual(verifySaveReceipt({ ...base, saved: applied(), confirmationUncertain: true }),
    { ok: false, reason: 'uncertain' }, 'an uncertain receipt can never be read as success');
});

test('every failure reason has a message that does not claim the write failed', () => {
  const reasons = [...Object.keys(SAVE_FAILURE_MESSAGES)];
  assert.ok(reasons.includes('idempotency_mismatch'), 'the new reason must be user-visible');
  for (const reason of reasons) {
    const message = saveFailureMessage(reason);
    assert.equal(typeof message, 'string');
    assert.ok(message.length > 0);
    // None of these may assert the write did not land — that is unknowable.
    assert.doesNotMatch(message, /没有保存|未保存成功|写入失败/);
  }
  assert.equal(saveFailureMessage('a_reason_that_does_not_exist'), SAVE_FAILURE_MESSAGES.failed,
    'an unknown reason falls back rather than rendering undefined');
});
