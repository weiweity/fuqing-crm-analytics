/** Isolated real HTTP + pinned Connection fixture. Credentials exist only in memory. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { callBoardConnection } from '../../src/board-spec/connection-call.mjs';

const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const pin = JSON.parse(await readFile(join(plugin, 'toolchain.json'), 'utf8'));
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: upstream, encoding: 'utf8' }).trim(), pin.upstream_sha);
const { Context } = createRequire(join(plugin, 'package.json'))('@deepseek-ai/cordis');
const connection = await import(pathToFileURL(join(upstream, 'packages/client/connection/lib/index.js')).href);

export async function mountNativeBoardBridge({ indexHtml = 'synthetic index', assets = {}, isolatedBrowserEntry = false } = {}) {
  const webRequire = createRequire(join(upstream, 'apps/web/package.json'));
  const esbuild = createRequire(webRequire.resolve('vite/package.json'))('esbuild');
  const outfile = join(plugin, 'lib/test-native-board-api.mjs');
  await esbuild.build({ absWorkingDir: plugin, entryPoints: ['src/board-browser-api.ts'], outfile,
    bundle: true, format: 'esm', platform: 'node', target: 'node24', external: ['@deepseek-ai/*'], logLevel: 'silent' });
  const business = await import(pathToFileURL(outfile).href);
  const routes = [], ctx = new Context();
  let credentialRecord;
  ctx.provide('credentials', {
    readRecord: async () => credentialRecord,
    modifyRecord: async (_key, mutate) => (credentialRecord = await mutate(credentialRecord)),
    deleteRecord: async () => { credentialRecord = undefined; },
  });
  const server = createServer((req, res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    // Test-only opt-in bootstrap for this disposable synthetic server. Never mounted in the product.
    if (isolatedBrowserEntry && pathname === '/__isolated_browser__' && req.method === 'GET'
      && req.headers.host === `127.0.0.1:${server.address().port}` && !req.headers.origin) {
      res.writeHead(302, { location: ctx.connection.authenticatedUrl(`http://127.0.0.1:${server.address().port}`), 'cache-control': 'no-store' });
      res.end(); return;
    }
    if (pathname === '/' || Object.hasOwn(assets, pathname)) {
      if (ctx.connection.authorizeIndex(req, res)) {
        const asset = assets[pathname];
        res.writeHead(200, { 'content-type': asset?.type ?? 'text/html; charset=utf-8', 'cache-control': 'no-store' });
        res.end(asset?.body ?? indexHtml);
      }
      return;
    }
    const route = routes.find(row => req.url.startsWith(`${row.path}/`));
    if (!route) { res.writeHead(404); res.end('not found'); return; }
    void route.handler(req, res).catch(() => { if (!res.writableEnded) { res.writeHead(500); res.end('isolated bridge failure'); } });
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const port = server.address().port;
  const webProvider = ctx.plugin({ name: 'isolated-web-provider', apply(provider) {
    provider.provide('webServer', { port, tapIndex: () => () => {}, register(route) {
    assert.equal(routes.some(row => row.path === route.path), false);
    routes.push(route); return () => { const index = routes.indexOf(route); if (index >= 0) routes.splice(index, 1); };
    } });
  } });
  await webProvider.await();
  let core, extension;
  try {
    core = ctx.plugin(connection); await core.await();
    extension = ctx.plugin(business); await extension.await();
    const origin = `http://127.0.0.1:${port}`;
    const exchanged = await fetch(ctx.connection.authenticatedUrl(origin), { redirect: 'manual' });
    const cookie = exchanged.headers.get('set-cookie')?.split(';', 1)[0];
    await exchanged.arrayBuffer(); assert.ok(cookie);
    let counter = 0;
    const rawCall = async (channel, operation, payload, signal) => {
      const rpcId = `isolated-${++counter}`;
      const response = await fetch(`${origin}${channel}/${operation}`, { method: 'POST', signal,
        headers: { cookie, origin, 'content-type': 'application/json' },
        body: JSON.stringify({ type: 'client-request', rpcId, method: operation, payload }) });
      assert.equal(response.status, 200);
      const body = await response.json();
      assert.equal(body.type, 'server-response'); assert.equal(body.rpcId, rpcId);
      return body.result;
    };
    const call = (channel, operation, payload, signal) => callBoardConnection({ call: rawCall }, channel, operation, payload, signal);
    return { origin, cookie, call, routes, removeBusiness: () => extension.dispose(),
      async close() { await extension.dispose(); await core.dispose(); await webProvider.dispose(); server.closeAllConnections();
        await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve())); } };
  } catch (error) {
    await extension?.dispose(); await core?.dispose(); await webProvider.dispose(); server.closeAllConnections();
    await new Promise(resolve => server.close(resolve)); throw error;
  }
}
