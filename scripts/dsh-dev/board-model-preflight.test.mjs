import test from 'node:test';
import assert from 'node:assert/strict';
import { boardModelPreflight, localLaunch } from './board-model-preflight.mjs';

const launch = 'http://127.0.0.1:6677/?token=DO_NOT_PRINT';
const model = { default: { provider: 'deepseek-official', model: 'configured-model' }, routableProviders: ['deepseek-official'] };
const envelope = value => Response.json({ result: { ok: true, value } });
function fixture({ boardStatus = 200, configured = true, providers, unauth = 401, fail = false, modelStatus = 200 } = {}) {
  const calls = [];
  return { calls, fetcher: async (input, options) => {
    const url = new URL(input); calls.push({ path: url.pathname, method: options.method ?? 'GET' });
    assert.equal(options.redirect, 'manual', 'credential-bearing redirects must never be followed');
    if (fail) throw new Error(`fetch failed ${launch}`);
    if (url.search) return new Response(null, { status: 303, headers: { 'set-cookie': 'fixture=DO_NOT_PRINT; HttpOnly', location: '/' } });
    if (url.pathname === '/') return new Response(null, { status: unauth });
    assert.equal(options.headers.cookie, 'fixture=DO_NOT_PRINT');
    const body = JSON.parse(options.body);
    if (url.pathname === '/api/session/modelCatalog') {
      assert.deepEqual(body.payload, { args: {} });
      return new Response(JSON.stringify({ result: { ok: true, value: { ...model,
        ...providers ? { routableProviders: providers } : {} } } }), { status: modelStatus });
    }
    assert.equal(url.pathname, '/api/shine-mage-board');
    assert.deepEqual(body.payload, { operation: 'status', payload: {} });
    return boardStatus === 200 ? envelope({ protocol: 'board-browser/v1', configured })
      : new Response('unexpected response with DO_NOT_PRINT', { status: boardStatus });
  } };
}
for (const [name, options, reason, ready] of [
  ['ready is only admission, not model execution', {}, 'PREFLIGHT_ONLY', true],
  ['old host returns 404', { boardStatus: 404 }, 'BOARD_PROTOCOL_UNAVAILABLE', false],
  ['business service not configured', { configured: false }, 'BOARD_SERVICE_NOT_CONFIGURED', false],
  ['model route absent', { providers: [] }, 'MODEL_ROUTE_UNAVAILABLE', false],
  ['non-200 catalogue is not ready even with an ok-shaped body', { modelStatus: 403 }, 'MODEL_ROUTE_UNAVAILABLE', false],
  ['unauthenticated host fails closed', { unauth: 200 }, 'AUTH_FENCE_NOT_VERIFIED', false],
  ['transport failure never leaks exception URL', { fail: true }, 'TRANSPORT_FAILED', false],
]) test(name, async () => {
  const f = fixture(options); const report = await boardModelPreflight(launch, f.fetcher);
  assert.equal(report.transport_ready, ready); assert.equal(report.reason, reason);
  assert.equal(report.model_execution, 'NOT_RUN'); assert.equal(report.credentials_verified, false);
  assert.equal(report.model_calls, 0); assert.equal(report.sessions_created, 0);
  assert.equal(report.settings_changed, false); assert.equal(report.host_restarted, false);
  assert.doesNotMatch(JSON.stringify(report), /DO_NOT_PRINT|token=/);
  assert.ok(f.calls.every(call => ['/', '/api/session/modelCatalog', '/api/shine-mage-board'].includes(call.path)));
});
test('rejects remote, credentialed, path-injected and non-HTTP launch URLs before I/O', () => {
  for (const url of ['https://example.com/?token=x', 'http://localhost:6677/', 'http://user@127.0.0.1:6677/',
    'http://127.0.0.1:6677/api/', 'file:///tmp/private', 'http://127.0.0.1/']) assert.throws(() => localLaunch(url));
  assert.equal(localLaunch(launch).origin, 'http://127.0.0.1:6677');
});
