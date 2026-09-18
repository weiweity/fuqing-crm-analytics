import test from 'node:test';
import assert from 'node:assert/strict';
import { DATA_SCOPE } from './contract.mjs';
import {
  BOUND_MANIFEST, UNBOUND_MANIFEST, createSyntheticAccess, defaultSyntheticSnapshot,
} from './synthetic.mjs';

const alice = {
  actor_id: 'alice',
  capabilities: new Set(['dashboard:read']),
  data_scopes: new Set([DATA_SCOPE]),
};
const bob = {
  actor_id: 'bob',
  capabilities: new Set(['dashboard:read']),
  data_scopes: new Set([DATA_SCOPE]),
};

function access(overrides = {}) {
  const created = createSyntheticAccess({ actor: alice, clock: () => 1000 });
  created.putSnapshot(defaultSyntheticSnapshot(overrides));
  return created;
}

test('unbound pages open as sample and cannot read live results', async () => {
  const store = access();
  const state = store.bindingState(alice, UNBOUND_MANIFEST);
  assert.equal(state.binding_state, 'UNBOUND_SAMPLE');
  assert.equal(state.verified, false);
  await assert.rejects(
    () => store.read({ op: 'data.read', result_ref: 'result_fixture_1', mode: 'summary' }, {
      actor: alice, manifest: UNBOUND_MANIFEST,
    }),
    error => error.code === 'FORBIDDEN',
  );
});

test('summary, paging and data_ref stay on one result version', async () => {
  const store = access();
  const summary = await store.read({
    op: 'data.read', request_id: 'req_1', result_ref: 'result_fixture_1', mode: 'summary',
  }, { actor: alice, manifest: BOUND_MANIFEST });
  assert.equal(summary.summary.row_count, 120);
  assert.equal(summary.rows.length, 5);
  assert.equal(summary.binding_state, 'BOUND_VERIFIED');
  const page = await store.read({
    op: 'data.read', request_id: 'req_2', result_ref: 'result_fixture_1', mode: 'page', limit: 50,
  }, { actor: alice, manifest: BOUND_MANIFEST });
  const next = await store.read({
    op: 'data.read', request_id: 'req_3', result_ref: 'result_fixture_1', mode: 'page',
    limit: 50, cursor: page.cursor,
  }, { actor: alice, manifest: BOUND_MANIFEST });
  assert.deepEqual(page.rows.map(row => row.i), [...Array(50).keys()]);
  assert.deepEqual(next.rows.map(row => row.i), [...Array(50).keys()].map(i => i + 50));
  const viaRef = await store.read({
    op: 'data.read', request_id: 'req_4', data_ref: summary.data_ref, mode: 'range', start: 0, end: 3,
  }, { actor: alice, manifest: BOUND_MANIFEST });
  assert.equal(viaRef.rows.length, 3);
  store.putSnapshot(defaultSyntheticSnapshot({ result_version: 2 }));
  await assert.rejects(
    () => store.read({
      op: 'data.read', request_id: 'req_5', result_ref: 'result_fixture_1', mode: 'page', cursor: page.cursor,
    }, { actor: alice, manifest: BOUND_MANIFEST }),
    error => error.code === 'RESULT_STALE',
  );
});

test('cross-actor, revoke-on-cache, expiry and unit mismatch', async () => {
  const store = access();
  assert.equal((await store.read({
    op: 'data.read', request_id: 'req_1', result_ref: 'result_fixture_1', mode: 'summary',
  }, { actor: alice, manifest: BOUND_MANIFEST })).ok, true);
  await assert.rejects(
    () => store.read({
      op: 'data.read', request_id: 'req_bob', result_ref: 'result_fixture_1', mode: 'summary',
    }, { actor: bob, manifest: BOUND_MANIFEST }),
    error => error.code === 'NOT_FOUND',
  );
  store.revoke('result_fixture_1', alice);
  await assert.rejects(
    () => store.read({
      op: 'data.read', request_id: 'req_revoked', result_ref: 'result_fixture_1', mode: 'summary',
    }, { actor: alice, manifest: BOUND_MANIFEST }),
    error => error.code === 'RESULT_REVOKED',
  );
  assert.equal(store.bindingState(alice, BOUND_MANIFEST).binding_state, 'BOUND_STALE');
  await assert.rejects(
    () => store.read({
      op: 'data.read', request_id: 'req_bob_revoked', result_ref: 'result_fixture_1', mode: 'summary',
    }, { actor: bob, manifest: BOUND_MANIFEST }),
    error => error.code === 'NOT_FOUND',
  );
  assert.equal(store.bindingState(bob, BOUND_MANIFEST).reasons.includes('RESULT_REVOKED'), false);
  const clock = { now: 10 };
  const expiring = createSyntheticAccess({ actor: alice, clock: () => clock.now });
  expiring.putSnapshot(defaultSyntheticSnapshot({ expires_at_ms: 20 }));
  clock.now = 20;
  await assert.rejects(
    () => expiring.read({
      op: 'data.read', request_id: 'req_exp', result_ref: 'result_fixture_1', mode: 'summary',
    }, { actor: alice, manifest: BOUND_MANIFEST }),
    error => error.code === 'RESULT_STALE',
  );
});

test('sql token save and unknown ops never become a query entry', async () => {
  const store = access();
  for (const request of [
    { op: 'sql', result_ref: 'result_fixture_1' },
    { op: 'save' },
    { op: 'http.fetch' },
    { op: 'credential.read' },
    { op: 'data.read', result_ref: 'result_fixture_1', sql: 'SELECT 1' },
    { op: 'data.read', result_ref: 'result_fixture_1', token: 'x' },
  ]) {
    await assert.rejects(
      () => store.read(request, { actor: alice, manifest: BOUND_MANIFEST }),
      error => error.code === 'BRIDGE_UNKNOWN_OP',
    );
  }
});

test('cancel and cumulative budget', async () => {
  const store = access({ rowCount: 2000 });
  store.cancel({ op: 'data.cancel', request_id: 'req_stop' }, alice);
  await assert.rejects(
    () => store.read({
      op: 'data.read', request_id: 'req_stop', result_ref: 'result_fixture_1', mode: 'summary',
    }, { actor: alice, manifest: BOUND_MANIFEST }),
    error => error.code === 'RESULT_UNAVAILABLE',
  );
  let cursor;
  for (let page = 0; page < 40; page += 1) {
    const body = await store.read({
      op: 'data.read', request_id: `req_p_${page}`, result_ref: 'result_fixture_1',
      mode: 'page', limit: 50, cursor, instance_id: 'inst_1',
    }, { actor: alice, manifest: BOUND_MANIFEST });
    cursor = body.cursor;
  }
  await assert.rejects(
    () => store.read({
      op: 'data.read', request_id: 'req_over', result_ref: 'result_fixture_1',
      mode: 'page', limit: 1, instance_id: 'inst_1',
    }, { actor: alice, manifest: BOUND_MANIFEST }),
    error => error.code === 'PACKAGE_TOO_LARGE',
  );
});
