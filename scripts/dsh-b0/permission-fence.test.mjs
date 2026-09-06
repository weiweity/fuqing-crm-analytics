import test from 'node:test';
import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';
import { currentPermission, permissionFence } from './permission-fence.mjs';

test('each operation checks current authority, including after successful authentication', async () => {
  let allowed = true, checks = 0, closed = 0;
  const sent = [];
  const fence = permissionFence(async () => { checks++; return allowed; }, () => { closed++; });
  assert.equal(await fence.enqueue(() => { sent.push('before'); }), true);
  allowed = false;
  assert.equal(await fence.enqueue(() => { sent.push('forbidden'); }), false);
  allowed = true;
  assert.equal(await fence.enqueue(() => { sent.push('must-reconnect'); }), false);
  assert.deepEqual(sent, ['before']);
  assert.equal(checks, 2); assert.equal(closed, 1);
});
test('authority errors and malformed positive values fail closed', async () => {
  assert.equal(await currentPermission(async () => { throw new Error('unavailable'); }), false);
  assert.equal(await currentPermission(async () => ({ allowed: true })), false);
  assert.equal(await currentPermission(async () => true), true);
});
test('bounded queue cannot execute after overflow even if a prior grant later succeeds', async () => {
  const gate = Promise.withResolvers();
  let closed = 0, actions = 0;
  const fence = permissionFence(() => gate.promise, () => { closed++; }, { queueLimit: 2 });
  const a = fence.enqueue(() => { actions++; });
  const b = fence.enqueue(() => { actions++; });
  assert.equal(await fence.enqueue(() => { actions++; }), false);
  gate.resolve(true);
  assert.deepEqual(await Promise.all([a, b]), [false, false]);
  assert.equal(actions, 0); assert.equal(closed, 1);
});
test('stream operations retain order and recheck between queued messages', async () => {
  let allowed = true, closed = 0;
  const sent = [];
  const fence = permissionFence(async () => allowed, () => { closed++; });
  const a = fence.enqueue(async () => { await delay(5); sent.push('first'); allowed = false; });
  const b = fence.enqueue(() => { sent.push('late'); });
  assert.deepEqual(await Promise.all([a, b]), [true, false]);
  assert.deepEqual(sent, ['first']); assert.equal(closed, 1);
});
test('idle established streams are closed after revocation without a new message', async () => {
  let allowed = true;
  const revoked = Promise.withResolvers();
  const fence = permissionFence(async () => allowed, revoked.resolve, { pollMs: 5 });
  try {
    assert.equal(await fence.enqueue(() => {}), true);
    allowed = false;
    const result = await Promise.race([revoked.promise.then(() => true), delay(300).then(() => false)]);
    assert.equal(result, true);
    assert.equal(await fence.enqueue(() => assert.fail('revoked action')), false);
  } finally { fence.close(); }
});
test('explicit disposal prevents late checks from delivering content', async () => {
  const gate = Promise.withResolvers();
  const fence = permissionFence(() => gate.promise, () => {});
  const work = fence.enqueue(() => assert.fail('disposed action'));
  fence.close(); gate.resolve(true);
  assert.equal(await work, false);
});
