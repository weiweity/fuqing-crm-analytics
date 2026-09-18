import test from 'node:test';
import assert from 'node:assert/strict';
import { createPageSession } from './session.mjs';
import { BRIDGE_PROTOCOL } from '../resource/frozen-contract.mjs';

test('session attach posts handshake to iframe and dispose expires the port', async () => {
  const posted = [];
  const iframe = {
    contentWindow: {
      postMessage(data, origin, ports) {
        posted.push({ data, origin, ports });
      },
    },
  };
  const session = createPageSession({ pageId: 'page_fixture_unbound', version: 1 });
  assert.equal(session.attach(iframe).ok, true);
  assert.equal(posted.length, 1);
  assert.equal(posted[0].data.protocol, BRIDGE_PROTOCOL);
  assert.equal(posted[0].data.type, 'handshake');
  assert.equal(posted[0].origin, '*');
  assert.equal(posted[0].ports.length, 1);
  assert.equal(session.attach(iframe).ok, true);
  assert.equal(posted.length, 2);
  session.dispose();
  assert.equal(session.alive, false);
  assert.equal(session.postToPage({ type: 'ping' }).ok, false);
  session.dispose();
});
