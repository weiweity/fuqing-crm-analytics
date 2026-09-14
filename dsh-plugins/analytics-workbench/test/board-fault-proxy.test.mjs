import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { test } from 'node:test';
import { mountBoardFaultProxy } from './helpers/board-fault-proxy.mjs';

test('owned HTTP fault proxy rejects before write, drops actual committed reply, and scopes one-shot reads', async t => {
  let writes = 0; const calls = [];
  const upstream = createServer((req, res) => {
    calls.push({ method: req.method, url: req.url, auth: req.headers.authorization });
    if (req.url.endsWith('/confirm')) writes++;
    req.resume(); res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ spec: { version: writes } }));
  });
  upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening');
  t.after(() => { upstream.closeAllConnections(); return new Promise(resolve => upstream.close(resolve)); });
  const proxy = await mountBoardFaultProxy(`http://127.0.0.1:${upstream.address().port}`);
  t.after(() => proxy.close());
  const send = (path, method = 'GET') => fetch(`${proxy.origin}/api/v1/analytics/board-spec${path}`, {
    method, headers: { authorization: 'synthetic-test-secret', 'idempotency-key': 'synthetic-key' },
  });
  proxy.arm('confirm-before');
  await (await send('/boards')).json();
  assert.equal(proxy.audit().armed, 'confirm-before');
  assert.equal((await send('/previews/p1/confirm', 'POST')).status, 503);
  assert.equal(writes, 0);
  proxy.arm('confirm-after');
  await assert.rejects(send('/previews/p1/confirm', 'POST'), /fetch failed/);
  assert.equal(writes, 1);
  assert.equal(proxy.audit().events.at(-1).committed_version, 1);
  assert.equal(proxy.audit().events.at(-1).same_key_as_first, true);
  assert.equal((await send('/previews/p1/confirm', 'POST')).status, 200);
  assert.equal(writes, 2); // Fixture intentionally not idempotent: this proxy must never implement storage semantics.
  for (const [mode, matched, other] of [['get', '/boards/b1', '/boards/b1/versions'], ['list', '/boards?limit=100', '/boards/b1']]) {
    proxy.arm(mode);
    assert.throws(() => proxy.arm(mode), /previous fault not consumed/);
    assert.equal((await send(other)).status, 200);
    assert.equal((await send(matched)).status, 503);
    assert.equal((await send(matched)).status, 200);
    assert.equal(proxy.audit().armed, null);
  }
  assert.ok(calls.every(row => row.auth === 'synthetic-test-secret'));
  assert.ok(!JSON.stringify(proxy.audit()).includes('synthetic-test-secret'));
  assert.ok(!JSON.stringify(proxy.audit()).includes('synthetic-key'));
  assert.equal((await fetch(`${proxy.origin}/other`)).status, 404);
  assert.throws(() => proxy.arm('arbitrary'));
});

test('fault proxy refuses non-isolated targets', async () => {
  for (const origin of ['http://127.0.0.1:6677', 'http://127.0.0.1:8000', 'https://127.0.0.1:8080', 'http://example.com:8080', 'http://127.0.0.1:8080/path']) {
    await assert.rejects(mountBoardFaultProxy(origin));
  }
});
