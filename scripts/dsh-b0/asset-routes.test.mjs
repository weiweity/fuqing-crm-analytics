import test from 'node:test';
import assert from 'node:assert/strict';
import { assetHeaderViolation, mapAssetRoute } from './asset-routes.mjs';

test('asset routes are an exact method/path whitelist', () => {
  const empty = new URLSearchParams();
  assert.equal(mapAssetRoute('GET', '/b0/assets', empty).kind, 'status');
  assert.equal(mapAssetRoute('POST', '/b0/assets', empty).kind, 'reject');
  assert.equal(mapAssetRoute('GET', '/b0/analyses', empty).kernel, '/api/v1/analytics/analyses');
  assert.equal(mapAssetRoute('POST', '/b0/analyses', empty).key, true);
  const id = 'analysis_' + 'a'.repeat(32);
  assert.equal(mapAssetRoute('GET', `/b0/analyses/${id}`, empty).kernel, `/api/v1/analytics/analyses/${id}`);
  assert.equal(mapAssetRoute('GET', `/b0/analyses/${id}`, new URLSearchParams('version=2')).kernel,
    `/api/v1/analytics/analyses/${id}?version=2`);
  assert.equal(mapAssetRoute('GET', `/b0/analyses/${id}`, new URLSearchParams('version=0')).kind, 'reject');
  assert.equal(mapAssetRoute('GET', '/b0/analyses/../secret', empty), null);
  assert.equal(mapAssetRoute('GET', '/api/v1/analytics/analyses', empty), null);
  const dash = 'dashboard_' + 'b'.repeat(32);
  assert.equal(mapAssetRoute('POST', `/b0/dashboards/${dash}/preview`, empty).match, true);
  assert.equal(mapAssetRoute('POST', `/b0/dashboards/${dash}/versions`, empty).key, true);
  assert.equal(mapAssetRoute('DELETE', `/b0/dashboards/${dash}`, empty).kind, 'reject');
  assert.equal(mapAssetRoute('GET', '/b0/other', empty), null);
  assert.equal(mapAssetRoute('GET', '/b0/dashboards', empty).kernel, '/api/v1/analytics/dashboards');
  assert.equal(mapAssetRoute('POST', '/b0/dashboards', empty).key, true);
  assert.equal(mapAssetRoute('GET', `/b0/dashboards/${dash}`, empty).kernel, `/api/v1/analytics/dashboards/${dash}`);
  assert.equal(mapAssetRoute('GET', '/b0/assets', new URLSearchParams('x=1')).kind, 'reject');
  assert.equal(mapAssetRoute('GET', '/b0/analyses', new URLSearchParams('q=1')).kind, 'reject');
  assert.equal(mapAssetRoute('GET', '/b0/dashboards', new URLSearchParams('q=1')).kind, 'reject');
  assert.equal(mapAssetRoute('POST', `/b0/analyses/${id}`, empty).kind, 'reject');
  assert.equal(mapAssetRoute('GET', `/b0/analyses/${id}`, new URLSearchParams('version=2&other=1')).kind, 'reject');
  assert.equal(mapAssetRoute('GET', `/b0/analyses/${id}`, new URLSearchParams('version=01')).kind, 'reject');
  assert.equal(mapAssetRoute('GET', `/b0/dashboards/${dash}/preview`, empty).kind, 'reject');
  assert.equal(mapAssetRoute('GET', `/b0/dashboards/${dash}/versions`, empty).kind, 'reject');
  assert.equal(mapAssetRoute('POST', `/b0/dashboards/${dash}/preview`, new URLSearchParams('x=1')).kind, 'reject');
  assert.equal(mapAssetRoute('GET', `/b0/dashboards/${dash}`, new URLSearchParams('x=1')).kind, 'reject');
});

test('browser must not send backend bearer, session fence, or duplicate version headers', () => {
  assert.equal(assetHeaderViolation(['Host', '127.0.0.1:4318']), null);
  assert.equal(assetHeaderViolation(['Authorization', 'Bearer secret']), 'browser-authorization');
  assert.equal(assetHeaderViolation(['X-Runtime-Session-Id', 'session-x']), 'session-fence');
  assert.equal(assetHeaderViolation(['If-Match', '1', 'If-Match', '2']), 'duplicate-if-match');
  assert.equal(assetHeaderViolation(['Idempotency-Key', 'a', 'Idempotency-Key', 'b']), 'duplicate-idempotency-key');
});
