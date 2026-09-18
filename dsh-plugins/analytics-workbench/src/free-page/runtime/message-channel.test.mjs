import test from 'node:test';
import assert from 'node:assert/strict';
import { BRIDGE_PROTOCOL } from '../resource/frozen-contract.mjs';
import { createHostChannel } from './message-channel.mjs';

function waitFor(fn, timeout = 1000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      try {
        const value = fn();
        if (value) return resolve(value);
      } catch (error) {
        return reject(error);
      }
      if (Date.now() - start > timeout) return reject(new Error('wait timeout'));
      setTimeout(tick, 10);
    };
    tick();
  });
}

test('handshake, unknown op, forbidden op, bad nonce, and expired instance', async () => {
  const events = [];
  const errors = [];
  const host = createHostChannel({
    instanceId: 'inst_1',
    pageId: 'page_fixture_unbound',
    version: 1,
    nonce: 'nonce_1',
    onEvent: (event) => events.push(event),
    onError: (error) => errors.push(error),
  });
  const { port1, port2 } = new MessageChannel();
  const incoming = [];
  port2.addEventListener('message', (event) => incoming.push(event.data));
  port2.start();
  host.bindPort(port1);
  await waitFor(() => incoming.some((row) => row.type === 'handshake'));

  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'hello', instance_id: 'inst_1', page_id: 'page_fixture_unbound',
    version: 1, nonce: 'nonce_1',
  });
  await waitFor(() => events.some((row) => row.type === 'hello'));

  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'request', op: 'sql', request_id: 'r1',
    instance_id: 'inst_1', page_id: 'page_fixture_unbound', version: 1, nonce: 'nonce_1', payload: { q: 'select 1' },
  });
  await waitFor(() => incoming.some((row) => row.type === 'error' && row.error?.code === 'FORBIDDEN'));

  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'request', op: 'http.fetch', request_id: 'r2',
    instance_id: 'inst_1', page_id: 'page_fixture_unbound', version: 1, nonce: 'nonce_1',
  });
  await waitFor(() => incoming.filter((row) => row.error?.code === 'FORBIDDEN').length >= 2);

  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'request', op: 'data.hack', request_id: 'r3',
    instance_id: 'inst_1', page_id: 'page_fixture_unbound', version: 1, nonce: 'nonce_1',
  });
  await waitFor(() => incoming.some((row) => row.error?.code === 'BRIDGE_UNKNOWN_OP'));

  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'request', op: 'data.read',
    instance_id: 'inst_1', page_id: 'page_fixture_unbound', version: 1, nonce: 'nonce_1',
    payload: { result_ref: 'result_fixture_1', mode: 'summary', cursor: null, limit: 50 },
  });
  await waitFor(() => incoming.some((row) => row.error?.code === 'INVALID_PAGE'));

  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'request', op: 'data.read', request_id: 'r4',
    instance_id: 'inst_1', page_id: 'page_fixture_unbound', version: 1, nonce: 'nonce_1',
    payload: { result_ref: 'result_fixture_1', mode: 'summary', cursor: null, limit: 50 },
  });
  await waitFor(() => incoming.some((row) => row.error?.code === 'RESULT_UNAVAILABLE'));

  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'hello', instance_id: 'inst_1', page_id: 'page_fixture_unbound',
    version: 1, nonce: 'nonce_other',
  });
  await waitFor(() => errors.some((row) => row.code === 'BRIDGE_NONCE'));

  host.dispose();
  port2.postMessage({
    protocol: BRIDGE_PROTOCOL, type: 'hello', instance_id: 'inst_1', page_id: 'page_fixture_unbound',
    version: 1, nonce: 'nonce_1',
  });
  await waitFor(() => errors.some((row) => row.code === 'BRIDGE_EXPIRED_INSTANCE'));
});
