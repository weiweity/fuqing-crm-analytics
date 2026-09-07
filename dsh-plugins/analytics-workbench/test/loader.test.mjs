/** Real pinned Cordis Loader, synthetic service facades. Not a native-run test. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdtemp } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { randomBytes } from 'node:crypto';
import { createServer } from 'node:net';

const plugin = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const load = path => import(pathToFileURL(join(upstream, path)).href);
const { Context } = await load('vendor/cordis/lib/index.js');
const { default: Loader } = await load('vendor/loader/lib/index.js');
const { default: Include } = await load('vendor/include/lib/index.js');

test('built package root and per-agent tool load through real Cordis include and dispose', async () => {
  // The fixed B0 private bridge port is part of the runtime contract. Never
  // probe somebody else's server with this test's ephemeral capability.
  const portProbe = createServer();
  await new Promise((ready, reject) => {
    portProbe.once('error', () => reject(new Error('Loader test requires port 4316 free; stop only your own B0 runtime first.')));
    portProbe.listen(4316, '127.0.0.1', ready);
  });
  await new Promise((ready, reject) => portProbe.close(error => error ? reject(error) : ready()));
  const fixture = await mkdtemp(join(plugin, 'lib/loader-fixture-'));
  const token = randomBytes(32).toString('base64url');
  process.env.B0_RUNTIME_TOKEN = token;
  process.env.B0_SESSION_ID = 'session-b0-synthetic-primary';
  try {
    for (const face of ['index', 'tool']) {
      const config = join(fixture, `${face}.yml`);
      await writeFile(config, JSON.stringify([{ id: `b0-${face}`, name: pathToFileURL(join(plugin, `lib/${face}.js`)).href }]), { mode: 0o600 });
      const ctx = new Context();
      const registered = [];
      ctx.provide('agents', { get: () => undefined });
      ctx.provide('sessions', { flush: async () => { assert.fail('loader-only test executed a session'); } });
      ctx.provide('sessionController', { prompt: async () => { assert.fail('loader-only test sent a prompt'); } });
      ctx.provide('tools', { register: tool => { registered.push(tool); } });
      try {
        ctx.baseUrl = pathToFileURL(fixture).href + '/';
        await ctx.plugin(Loader);
        ctx.loader.builtins.include = Include;
        // Import actual built modules, without Node source hooks or aliasing
        // their exports. Cordis owns include, injection, entry start and stop.
        ctx.loader.internal = { version: 'v2', import: specifier => import(specifier) };
        await ctx.loader.create({ name: 'cordis:include', config: { path: pathToFileURL(config).href } });
        await ctx.loader.await();
        if (face === 'tool') assert.deepEqual(registered.map(tool => tool.name), ['analytics_b0_query']);
        else {
          const response = await fetch('http://127.0.0.1:4316/health', {
            method: 'POST', headers: { authorization: `Bearer ${token}` }, body: '{}',
            signal: AbortSignal.timeout(3000), redirect: 'error',
          });
          assert.equal(response.status, 200);
          assert.deepEqual(await response.json(), { ready: false });
        }
      } finally { await ctx.fiber.dispose(); }
    }
    const manifest = JSON.parse(await readFile(join(plugin, 'package.json'), 'utf8'));
    assert.equal(manifest.dsh.client.platform, 'web');
  } finally { delete process.env.B0_RUNTIME_TOKEN; delete process.env.B0_SESSION_ID; }
});

test('query-family Cordis loader registers query tool and two-session health', async () => {
  const portProbe = createServer();
  await new Promise((ready, reject) => {
    portProbe.once('error', () => reject(new Error('Loader test requires port 4316 free; stop only your own B0 runtime first.')));
    portProbe.listen(4316, '127.0.0.1', ready);
  });
  await new Promise((ready, reject) => portProbe.close(error => error ? reject(error) : ready()));
  const fixture = await mkdtemp(join(plugin, 'lib/loader-fixture-'));
  const token = randomBytes(32).toString('base64url');
  const previous = {
    token: process.env.B0_RUNTIME_TOKEN,
    session: process.env.B0_SESSION_ID,
    sessions: process.env.B0_SESSION_IDS,
    family: process.env.B0_RUNTIME_FAMILY,
  };
  process.env.B0_RUNTIME_TOKEN = token;
  process.env.B0_RUNTIME_FAMILY = 'channel_followup';
  process.env.B0_SESSION_IDS = 'session-query-a,session-query-b';
  delete process.env.B0_SESSION_ID;
  try {
    for (const face of ['index', 'tool']) {
      const config = join(fixture, `query-${face}.yml`);
      await writeFile(config, JSON.stringify([{ id: `query-${face}`, name: pathToFileURL(join(plugin, `lib/${face}.js`)).href }]), { mode: 0o600 });
      const ctx = new Context();
      const registered = [];
      ctx.provide('agents', { get: () => undefined });
      ctx.provide('sessions', { flush: async () => { assert.fail('loader-only test executed a session'); } });
      ctx.provide('sessionController', { prompt: async () => { assert.fail('loader-only test sent a prompt'); } });
      ctx.provide('tools', { register: tool => { registered.push(tool); } });
      try {
        ctx.baseUrl = pathToFileURL(fixture).href + '/';
        await ctx.plugin(Loader);
        ctx.loader.builtins.include = Include;
        ctx.loader.internal = { version: 'v2', import: specifier => import(specifier) };
        await ctx.loader.create({ name: 'cordis:include', config: { path: pathToFileURL(config).href } });
        await ctx.loader.await();
        if (face === 'tool') assert.deepEqual(registered.map(tool => tool.name), ['analytics_channel_followup_query']);
        else {
          const response = await fetch('http://127.0.0.1:4316/health', {
            method: 'POST', headers: { authorization: `Bearer ${token}` }, body: '{}',
            signal: AbortSignal.timeout(3000), redirect: 'error',
          });
          assert.equal(response.status, 200);
          assert.deepEqual(await response.json(), { ready: false });
        }
      } finally { await ctx.fiber.dispose(); }
    }
  } finally {
    if (previous.token === undefined) delete process.env.B0_RUNTIME_TOKEN; else process.env.B0_RUNTIME_TOKEN = previous.token;
    if (previous.session === undefined) delete process.env.B0_SESSION_ID; else process.env.B0_SESSION_ID = previous.session;
    if (previous.sessions === undefined) delete process.env.B0_SESSION_IDS; else process.env.B0_SESSION_IDS = previous.sessions;
    if (previous.family === undefined) delete process.env.B0_RUNTIME_FAMILY; else process.env.B0_RUNTIME_FAMILY = previous.family;
  }
});
