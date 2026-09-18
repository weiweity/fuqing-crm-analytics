import test from 'node:test';
import assert from 'node:assert/strict';
import { DATA_SCOPE, PROTOCOL } from './contract.mjs';
import { createBridgeHost, createPageBridge } from './host.mjs';
import {
  BOUND_MANIFEST, UNBOUND_MANIFEST, createSyntheticAccess, defaultSyntheticSnapshot,
} from './synthetic.mjs';

const alice = {
  actor_id: 'alice',
  capabilities: new Set(['dashboard:read']),
  data_scopes: new Set([DATA_SCOPE]),
};

function handshake(overrides = {}) {
  return {
    protocol: PROTOCOL,
    instance_id: 'inst_1',
    page_id: 'page_fixture_unbound',
    version: 1,
    nonce: 'nonce_1',
    ...overrides,
  };
}

function hostWith(manifest = BOUND_MANIFEST, snapshot = defaultSyntheticSnapshot()) {
  const access = createSyntheticAccess({ actor: alice });
  access.putSnapshot(snapshot);
  const host = createBridgeHost({
    access, actor: alice, pageId: 'page_fixture_unbound', version: 1, manifest,
  });
  return { access, host };
}

test('unbound handshake still opens and emits sample binding state', async () => {
  const { host } = hostWith(UNBOUND_MANIFEST);
  const [state] = await host.dispatch(handshake());
  assert.equal(state.event, 'binding.state');
  assert.equal(state.binding_state, 'UNBOUND_SAMPLE');
  assert.equal(state.verified, false);
  const [denied] = await host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_1', result_ref: 'result_fixture_1', mode: 'summary',
  });
  assert.equal(denied.event, 'data.error');
  assert.equal(denied.code, 'FORBIDDEN');
});

test('bound handshake then summary chunk/end', async () => {
  const { host } = hostWith();
  const [state] = await host.dispatch(handshake());
  assert.equal(state.binding_state, 'BOUND_VERIFIED');
  const events = await host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_1', result_ref: 'result_fixture_1', mode: 'summary',
  });
  assert.equal(events[0].event, 'data.chunk');
  assert.equal(events[0].summary.unit, 'CNY 元');
  assert.equal(events[0].summary.row_count, 120);
  assert.equal(events[1].event, 'data.end');
  assert.equal(events[1].binding_state, 'BOUND_VERIFIED');
});

test('nonce replay, expired instance and unknown/forbidden ops', async () => {
  const { host } = hostWith();
  await host.dispatch(handshake());
  const [replay] = await host.dispatch(handshake());
  assert.equal(replay.code, 'BRIDGE_NONCE');
  host.expireInstance();
  const [expired] = await host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_old', result_ref: 'result_fixture_1',
  });
  assert.equal(expired.code, 'BRIDGE_EXPIRED_INSTANCE');
  const fresh = hostWith().host;
  for (const op of ['sql', 'save', 'http.fetch', 'credential.read']) {
    const [event] = await fresh.dispatch({ op, result_ref: 'result_fixture_1' });
    assert.equal(event.code, 'BRIDGE_UNKNOWN_OP');
  }
  await fresh.dispatch(handshake({ nonce: 'nonce_2', instance_id: 'inst_2' }));
  const [smuggled] = await fresh.dispatch({
    ...handshake({ nonce: 'nonce_2', instance_id: 'inst_2' }),
    op: 'data.read', request_id: 'req_sql', result_ref: 'result_fixture_1', sql: 'SELECT 1',
  });
  assert.equal(smuggled.code, 'BRIDGE_UNKNOWN_OP');
});

test('cancel aborts an in-flight read', async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const inner = createSyntheticAccess({ actor: alice });
  inner.putSnapshot(defaultSyntheticSnapshot());
  const access = {
    putSnapshot: inner.putSnapshot,
    bindingState: inner.bindingState,
    authorize: inner.authorize,
    cancel: inner.cancel,
    async read(request, options) {
      await gate;
      return inner.read(request, options);
    },
  };
  const host = createBridgeHost({
    access, actor: alice, pageId: 'page_fixture_unbound', version: 1, manifest: BOUND_MANIFEST,
  });
  await host.dispatch(handshake());
  const pending = host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_slow', result_ref: 'result_fixture_1', mode: 'summary',
  });
  const [cancelled] = await host.dispatch({
    ...handshake(), op: 'data.cancel', request_id: 'req_slow',
  });
  assert.equal(cancelled.status, 'CANCELLED');
  release();
  const [failed] = await pending;
  assert.equal(failed.event, 'data.error');
  assert.equal(failed.code, 'RESULT_UNAVAILABLE');
});

test('in-flight dedup still re-authorizes the second waiter', async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const inner = createSyntheticAccess({ actor: alice });
  inner.putSnapshot(defaultSyntheticSnapshot());
  let authorizes = 0;
  const access = {
    putSnapshot: inner.putSnapshot,
    bindingState: inner.bindingState,
    cancel: inner.cancel,
    authorize(...args) {
      authorizes += 1;
      return inner.authorize(...args);
    },
    async read(request, options) {
      await gate;
      return inner.read(request, options);
    },
  };
  const host = createBridgeHost({
    access, actor: alice, pageId: 'page_fixture_unbound', version: 1, manifest: BOUND_MANIFEST,
  });
  await host.dispatch(handshake());
  const first = host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_a', result_ref: 'result_fixture_1', mode: 'summary',
  });
  await Promise.resolve();
  inner.revoke('result_fixture_1', alice);
  const second = await host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_b', result_ref: 'result_fixture_1', mode: 'summary',
  });
  assert.equal(second[0].code, 'RESULT_REVOKED');
  release();
  await first;
  assert.ok(authorizes >= 2);
});

test('re-handshake drops in-flight read from the old instance', async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const inner = createSyntheticAccess({ actor: alice });
  inner.putSnapshot(defaultSyntheticSnapshot());
  const access = {
    putSnapshot: inner.putSnapshot,
    bindingState: inner.bindingState,
    authorize: inner.authorize,
    cancel: inner.cancel,
    async read(request, options) {
      await gate;
      return inner.read(request, options);
    },
  };
  const host = createBridgeHost({
    access, actor: alice, pageId: 'page_fixture_unbound', version: 1, manifest: BOUND_MANIFEST,
  });
  await host.dispatch(handshake());
  const pending = host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_old', result_ref: 'result_fixture_1', mode: 'summary',
  });
  const [state] = await host.dispatch(handshake({ instance_id: 'inst_2', nonce: 'nonce_2' }));
  assert.equal(state.event, 'binding.state');
  assert.equal(state.instance_id, 'inst_2');
  release();
  const [failed] = await pending;
  assert.equal(failed.event, 'data.error');
  assert.equal(failed.code, 'RESULT_UNAVAILABLE');
  assert.equal(failed.instance_id, 'inst_1');
});

test('new instance can reuse an aborted request_id', async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  let hold = true;
  const inner = createSyntheticAccess({ actor: alice });
  inner.putSnapshot(defaultSyntheticSnapshot());
  const access = {
    putSnapshot: inner.putSnapshot,
    bindingState: inner.bindingState,
    authorize: inner.authorize,
    cancel: inner.cancel,
    async read(request, options) {
      if (hold) await gate;
      return inner.read(request, options);
    },
  };
  const host = createBridgeHost({
    access, actor: alice, pageId: 'page_fixture_unbound', version: 1, manifest: BOUND_MANIFEST,
  });
  await host.dispatch(handshake());
  const pending = host.dispatch({
    ...handshake(), op: 'data.read', request_id: 'req_1', result_ref: 'result_fixture_1', mode: 'summary',
  });
  await host.dispatch(handshake({ instance_id: 'inst_2', nonce: 'nonce_2' }));
  hold = false;
  release();
  const [failed] = await pending;
  assert.equal(failed.code, 'RESULT_UNAVAILABLE');
  const events = await host.dispatch({
    ...handshake({ instance_id: 'inst_2', nonce: 'nonce_2' }),
    op: 'data.read', request_id: 'req_1', result_ref: 'result_fixture_1', mode: 'summary',
  });
  assert.equal(events[0].event, 'data.chunk');
  assert.equal(events[0].instance_id, 'inst_2');
});

test('failed handshake rejects the page handshake promise', async () => {
  const { host } = hostWith();
  const channel = new MessageChannel();
  host.attach(channel.port1);
  const page = createPageBridge(channel.port2, handshake({ page_id: 'page_other' }));
  await assert.rejects(page.handshake, error => error.code === 'INVALID_PAGE');
  channel.port1.close();
  channel.port2.close();
});

test('MessageChannel roundtrip reads authorized summary', async () => {
  const { host } = hostWith();
  const channel = new MessageChannel();
  host.attach(channel.port1);
  const page = createPageBridge(channel.port2, handshake({ nonce: 'nonce_ch', instance_id: 'inst_ch' }));
  const state = await page.handshake;
  assert.equal(state.binding_state, 'BOUND_VERIFIED');
  const result = await page.read({
    request_id: 'req_ch', result_ref: 'result_fixture_1', mode: 'summary',
  });
  assert.equal(result.chunks[0].event, 'data.chunk');
  assert.equal(result.chunks[0].summary.source.startsWith('合成结果夹具'), true);
  assert.equal(result.end.event, 'data.end');
  channel.port1.close();
  channel.port2.close();
});
