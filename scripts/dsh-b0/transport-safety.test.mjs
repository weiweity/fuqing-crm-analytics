import test from 'node:test';
import assert from 'node:assert/strict';
import { findReadyUrl, redactLaunchLog, pluginManifest, refreshedPluginManifest, safeRpcResult } from './transport-safety.mjs';
import { filterHttpResult } from './gateway-policy.mjs';

const origin = 'http://127.0.0.1:4317';
const token = 'SYNTHETIC_token-0123456789';
const launch = `${origin}/?token=${token}`;
const resource = '/plugins/??@fixture/alpha/client.js,@fixture/beta/client.js&rev=fixture-1';
const boot = (entries = [{ url: resource }], batches = [], extra = '') =>
  `<script>globalThis["__DSH_BOOT__"] = ${JSON.stringify({ entries, batches })};</script>${extra}`;
const rpcId = 'synthetic-rpc';
const scope = { sessionId: 'synthetic-session', workspaceId: 'synthetic-workspace', workspacePath: '/synthetic/workspace', inFlight: false };
const response = result => ({ type: 'server-response', rpcId, result });

test('ready URL is found only after the full newline, at every chunk split', () => {
  const line = `\u001b[32mB0 ready ${launch}\u001b[0m\n`;
  for (let split = 0; split < line.length; split++) {
    const first = line.slice(0, split);
    assert.equal(findReadyUrl(first, origin), null, `premature ready at split ${split}`);
    const accumulated = first + line.slice(split);
    assert.equal(findReadyUrl(accumulated, origin), launch);
    assert.ok(!redactLaunchLog(accumulated).includes(token));
  }
  assert.equal(findReadyUrl(`${launch}\r`, origin), null);
  assert.equal(findReadyUrl(`${launch}\r\nunfinished tail`, origin), launch);
});

test('launch lookup rejects foreign origins, duplicate/invalid token and fragments', () => {
  for (const value of [
    `https://example.invalid/?token=${token}`, `${origin}.example.invalid/?token=${token}`,
    `${origin}/?token=a&token=b`, `${origin}/?token=bad%21`, `${launch}#fragment`,
    `http://user:password@127.0.0.1:4317/?token=${token}`,
  ]) assert.equal(findReadyUrl(value + '\n', origin), null);
  assert.equal(findReadyUrl(null, origin), null);
});

test('complete log redacts both launch secrets and truncated token tails', () => {
  const log = `${launch}&mode=demo\n${origin}/?b0=synthetic-pass\n?token=partial-token`;
  const clean = redactLaunchLog(log);
  for (const secret of [token, 'synthetic-pass', 'partial-token']) assert.ok(!clean.includes(secret));
  assert.ok(clean.includes('&mode=demo'));
  assert.equal((clean.match(/\[REDACTED\]/g) ?? []).length, 3);
});

test('manifest preserves exact published query URLs and HTML ampersands', () => {
  const scriptResource = '/plugins/??@fixture/bootstrap/client.js&rev=fixture-2';
  const html = boot([{ url: resource }], [{ url: resource }],
    `<script src="${scriptResource.replaceAll('&', '&amp;')}"></script><script src="/assets/app.js"></script>`);
  const urls = pluginManifest(html, origin);
  assert.deepEqual([...urls], [origin + resource, origin + scriptResource]);
  for (const unknown of [resource.replace('fixture-1', 'fixture-9'), resource + '&extra=1',
    '/plugins/??@fixture/beta/client.js,@fixture/alpha/client.js&rev=fixture-1',
    '/plugins/events', '/api/session/page', '/plugins/']) assert.ok(!urls.has(origin + unknown));
});

test('manifest rejects external, credentials, fragments and non-published URL forms', () => {
  for (const value of ['https://example.invalid/plugins/??a&rev=x', '//example.invalid/plugins/??a&rev=x',
    'javascript:alert(1)', '/plugins/??a&rev=x#tail', '/plugins/../api/session/page',
    '/plugins/??a\\b&rev=x', '/plugins/??a\nb&rev=x', '/plugins/a.js', undefined]) {
    assert.throws(() => pluginManifest(boot([{ url: value }]), origin));
  }
  assert.throws(() => pluginManifest(boot([], []), origin));
  assert.throws(() => pluginManifest(boot(null, []), origin));
  assert.throws(() => pluginManifest(boot() + boot(), origin));
  assert.throws(() => pluginManifest(boot([], [], '<script src="https://example.invalid/app.js"></script>'), origin));
  assert.throws(() => pluginManifest(boot([], [], '<script src=/plugins/test.js></script>'), origin));
});

test('boot graph is parsed as JSON, never executed as JavaScript', () => {
  assert.throws(() => pluginManifest('<script>globalThis["__DSH_BOOT__"] = {entries: [], batches: []};</script>', origin));
  assert.throws(() => pluginManifest('<script>globalThis["__DSH_BOOT__"] = (() => ({entries: [], batches: []}))();</script>', origin));
  assert.throws(() => pluginManifest('<script>globalThis["__DSH_BOOT__"] = {"entries":[],"batches":[]}; evil();</script>', origin));
});

const hostEntries = nonce => ['alpha', 'beta'].map((name, index) => ({
  url: `/plugins/??@fixture/${name}/client.js&rev=${nonce}-${index}`,
}));
const fixedBatches = [{ url: '/plugins/??@fixture/alpha/client.js,@fixture/beta/client.js&rev=abcdef012345' }];

test('owned Host restart refreshes exact per-boot URLs while preserving modules and content batches', () => {
  const original = boot(hostEntries('0123456789abcdef'), fixedBatches);
  const fresh = boot(hostEntries('fedcba9876543210'), fixedBatches);
  const allowed = refreshedPluginManifest(original, fresh, origin);
  assert.deepEqual(allowed, pluginManifest(fresh, origin));
  assert.ok(!allowed.has(origin + hostEntries('0123456789abcdef')[0].url));
  assert.ok(!allowed.has(origin + hostEntries('aaaaaaaaaaaaaaaa')[0].url));
});

for (const changed of ['new-module', 'missing-module', 'changed-batch', 'missing-batch', 'extra-query', 'mixed-nonce', 'wrong-index', 'extra-script']) {
  test(`Host restart cannot extend allowlist through ${changed}`, () => {
    const original = boot(hostEntries('0123456789abcdef'), fixedBatches);
    const entries = hostEntries('fedcba9876543210');
    const batches = structuredClone(fixedBatches);
    let script = '';
    if (changed === 'new-module') entries[0].url = entries[0].url.replace('alpha', 'unapproved');
    if (changed === 'missing-module') entries.pop();
    if (changed === 'changed-batch') batches[0].url = batches[0].url.replace('abcdef012345', 'ffffffffffff');
    if (changed === 'missing-batch') batches.pop();
    if (changed === 'extra-query') entries[0].url += '&permissions=all';
    if (changed === 'mixed-nonce') entries[0].url = entries[0].url.replace('fedcba9876543210', 'aaaaaaaaaaaaaaaa');
    if (changed === 'wrong-index') entries[0].url = entries[0].url.replace('-0', '-1');
    if (changed === 'extra-script') script = '<script src="/plugins/??@unapproved/other/client.js&rev=extra"></script>';
    assert.throws(() => refreshedPluginManifest(original, boot(entries, batches, script), origin));
  });
}

test('RPC errors never return upstream paths, credentials, headers or extra fields', () => {
  const sensitive = { path: '/synthetic-private/profile', cookie: 'synthetic-cookie', secret: 'synthetic-secret' };
  const envelope = { ...response({ ok: false, error: { code: 'upstream/private',
    message: JSON.stringify(sensitive), details: sensitive }, extra: sensitive }), extra: sensitive };
  const safe = safeRpcResult(envelope, rpcId, 'session/prompt', scope, () => { throw new Error('must not call'); });
  assert.deepEqual(safe, response({ ok: false, error: { code: 'gateway/internal', message: 'B0上游请求失败；内部诊断未公开', details: {} } }));
  for (const secret of Object.values(sensitive)) assert.ok(!JSON.stringify(safe).includes(secret));
});

test('RPC success is projected through policy, dropping envelope and value extras', () => {
  const upstream = { ...response({ ok: true, value: { accepted: true, cookie: 'synthetic-secret' } }), secret: 'synthetic-secret' };
  assert.deepEqual(safeRpcResult(upstream, rpcId, 'session/prompt', scope, filterHttpResult), response({ ok: true, value: { accepted: true } }));
  assert.deepEqual(safeRpcResult(response({ ok: true, value: true }), rpcId, 'session/canOpenWorkspacePath', scope, filterHttpResult), response({ ok: true, value: false }));
});

test('unknown/mismatched RPC envelopes and rejected outputs fail closed', () => {
  for (const envelope of [null, [], {}, { ...response({ ok: true, value: {} }), type: 'other' },
    { ...response({ ok: true, value: {} }), rpcId: 'other' }, response({ ok: 'true' }),
    response({ ok: false }), response({ ok: false, error: 'bad' })]) {
    assert.equal(safeRpcResult(envelope, rpcId, 'session/prompt', scope, filterHttpResult), null);
  }
  for (const filter of [undefined, () => null, () => undefined, () => { throw new Error('synthetic-secret'); }]) {
    assert.equal(safeRpcResult(response({ ok: true, value: {} }), rpcId, 'session/prompt', scope, filter), null);
  }
  assert.equal(safeRpcResult(response({ ok: true, value: {} }), rpcId, 'unknown/endpoint', scope, filterHttpResult), null);
});
