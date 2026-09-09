import test from 'node:test';
import assert from 'node:assert/strict';
import { batchIntent, finishBatchIntent } from './batch-intent.mjs';
import { BOARD_SUCCESS, DEFAULT_PRINCIPAL } from './c0-fixtures.mjs';

test('remount retry retains intent; success and different actor start new intents', () => {
  const prior = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage');
  const values = new Map();
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: {
    getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key),
  } });
  try {
    const refs = BOARD_SUCCESS.batch.operations[0].endorsed_result_refs;
    const first = batchIntent(DEFAULT_PRINCIPAL, 'ONE_BOARD_MULTI_BLOCK', refs);
    const remount = batchIntent(DEFAULT_PRINCIPAL, 'ONE_BOARD_MULTI_BLOCK', refs);
    assert.deepEqual(first.payload, remount.payload);
    const other = batchIntent({ ...DEFAULT_PRINCIPAL, actor_id: 'other' }, 'ONE_BOARD_MULTI_BLOCK', refs);
    assert.notEqual(other.payload.batch_id, first.payload.batch_id);
    finishBatchIntent(DEFAULT_PRINCIPAL, remount);
    const next = batchIntent(DEFAULT_PRINCIPAL, 'ONE_BOARD_MULTI_BLOCK', refs);
    assert.notEqual(next.payload.batch_id, first.payload.batch_id);
  } finally {
    if (prior) Object.defineProperty(globalThis, 'sessionStorage', prior); else delete globalThis.sessionStorage;
  }
});
