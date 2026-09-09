import test from 'node:test';
import assert from 'node:assert/strict';
import { apply } from './brand.mjs';
test('native dev brand extension serves only fixed verified assets and disposes routes', async () => {
  const routes = new Map(), disposers = [];
  await apply({
    effect(fn) { disposers.push(fn()); },
    on(event, fn) { assert.equal(event, 'webserver/index-inject'); const rows = []; fn(rows); assert.equal(rows[0].kind, 'style'); },
    webServer: { register(route) { routes.set(route.path, route); return () => routes.delete(route.path); } },
  });
  assert.deepEqual([...routes.keys()], ['/b0/brand/logo.png', '/b0/brand/mark.svg']);
  for (const route of routes.values()) {
    let status, body, headers;
    const res = { writeHead(code, value) { status = code; headers = value; return res; }, end(value) { body = value; } };
    route.handler({ method: 'GET' }, res);
    assert.equal(status, 200); assert.ok(body.length > 0); assert.equal(headers['content-length'], body.length);
    route.handler({ method: 'HEAD' }, res); assert.equal(status, 200); assert.equal(body, undefined);
    route.handler({ method: 'POST' }, res); assert.equal(status, 405);
  }
  for (const dispose of disposers) dispose();
  assert.equal(routes.size, 0);
});
