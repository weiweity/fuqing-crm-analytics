import test from 'node:test';
import assert from 'node:assert/strict';
import { request as httpRequest } from 'node:http';
import { mountNativeBoardBridge } from './helpers/native-board-bridge.mjs';

test('actual business channel requires native cookie and same origin; unloading removes only business route', async t => {
  const bridge = await mountNativeBoardBridge(); t.after(() => bridge.close());
  assert.equal(bridge.routes.some(route => route.path === '/api'), true);
  assert.equal((await bridge.call('/shine-mage-board', 'status', {})).ok, true);
  for (const operation of ['list', 'confirm']) {
    const response = await fetch(`${bridge.origin}/api/shine-mage-board`, { method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ type: 'client-request', rpcId: 'deny', method: 'shine-mage-board',
        payload: { operation, payload: { preview_id: 'preview_test', key: 'unauthorized' } } }) });
    assert.equal(response.status, 401); await response.arrayBuffer();
  }
  for (const headers of [{ host: 'attacker.example' }, { origin: 'https://attacker.example', cookie: bridge.cookie }]) {
    // Node fetch normalizes Host. A raw IncomingMessage must exercise the forged authority.
    const status = await new Promise((resolve, reject) => {
      const request = httpRequest(`${bridge.origin}/api/shine-mage-board`, { method: 'POST',
        headers: { ...headers, 'content-type': 'application/json' } }, response => {
        response.resume(); response.on('end', () => resolve(response.statusCode));
      });
      request.on('error', reject); request.end('{}');
    });
    assert.equal(status, 403);
  }
  const mismatch = await fetch(`${bridge.origin}/api/shine-mage-board`, { method: 'POST',
    headers: { cookie: bridge.cookie, 'content-type': 'application/json' },
    body: JSON.stringify({ type: 'client-request', rpcId: 'mismatch', method: 'confirm', payload: {} }) });
  assert.equal((await mismatch.json()).result.error.code, 'gateway/bad-request');
  assert.equal((await bridge.call('/shine-mage-board', 'http', { path: '/settings' })).error.code, 'INVALID_REQUEST');
  await bridge.removeBusiness();
  assert.equal(bridge.routes.some(route => route.path === '/shine-mage-board'), false);
  assert.equal(bridge.routes.some(route => route.path === '/api'), true);
  const removed = await fetch(`${bridge.origin}/api/shine-mage-board`, { method: 'POST', headers: { cookie: bridge.cookie } });
  assert.equal(removed.status, 404); await removed.arrayBuffer();
});
