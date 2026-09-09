import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { brandAssets } from '../dsh-b0/brand-assets.mjs';
import { join } from 'node:path';
import { apply } from './brand.mjs';


test('native dev brand extension serves verified local assets', async () => {
  const routes = new Map(), disposers = [];
  await apply({
    effect(fn) { const dispose = fn(); if (typeof dispose === 'function') disposers.push(dispose); },
    on(event, fn) {
      assert.equal(event, 'webserver/index-inject');
      const rows = []; fn(rows);
      assert.equal(rows[0].kind, 'style');
      assert.match(rows[0].text, /\/b0\/brand\/logo\.png/);
      assert.match(rows[0].text, /Outfit/);
    },
    webServer: { register(route) { routes.set(route.path, route); return () => routes.delete(route.path); } },
  });
  assert.ok(routes.has('/b0/brand/mark.svg'));
  assert.ok(routes.has('/b0/brand/outfit.ttf'));
  assert.ok(routes.has('/b0/brand/outfit-ofl.txt'));
  assert.ok(routes.has('/favicon.svg'));
  assert.ok(routes.has('/b0/brand/logo.png'), 'logo must be restored from verified non-LFS bytes');
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

test('missing or unresolved local logo fails without consulting another checkout', async () => {
  const root = await mkdtemp(join(tmpdir(), 'brand-assets-'));
  try {
    await assert.rejects(brandAssets(root), { code: 'ENOENT' });
    const dir = join(root, 'frontend-vue3/src/assets/brand');
    await mkdir(dir, { recursive: true });
    await writeFile(join(dir, 'shine-mage.png'), 'version https://git-lfs.github.com/spec/v1\n');
    await assert.rejects(brandAssets(root), /Original brand bytes changed/);
    await writeFile(join(dir, 'shine-mage.png'), 'invalid PNG bytes');
    await assert.rejects(brandAssets(root), /Original brand bytes changed/);
  } finally { await rm(root, { recursive: true, force: true }); }
});
