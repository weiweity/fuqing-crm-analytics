import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

test('native-query-assets is an explicit opt-in and does not replace native-query', async () => {
  const serve = await readFile(join(here, 'serve.mjs'), 'utf8');
  assert.match(serve, /native-query-assets/);
  assert.match(serve, /queryAssetsScenario/);
  assert.match(serve, /asset_capabilities/);
  assert.match(serve, /analysis_dir/);
  assert.match(serve, /cockpit_dir/);
  assert.match(serve, /queryFamily = queryScenario \|\| queryFaultScenario \|\| queryAssetsScenario/);
  assert.match(serve, /queryFaultScenario \? 'backend.tests.analytics_query_native_fault_probe' : stateScenario \? 'backend.tests.analytics_native_probe' : 'backend.analytics_runtime'/);
  assert.doesNotMatch(serve, /asset_capabilities.*run:create/);
});

test('query-only kernel config in serve does not grant asset capabilities by default', async () => {
  const serve = await readFile(join(here, 'serve.mjs'), 'utf8');
  const defaultBlock = serve.slice(serve.indexOf('const kernelConfig'), serve.indexOf('if (queryAssetsScenario)'));
  assert.doesNotMatch(defaultBlock, /asset_capabilities/);
  assert.match(serve, /if \(queryAssetsScenario\) \{/);
});

test('gateway asset map is not a generic /api proxy', async () => {
  const gateway = await readFile(join(here, 'gateway.mjs'), 'utf8');
  assert.match(gateway, /mapAssetRoute/);
  assert.match(gateway, /assetsEnabled/);
  assert.match(gateway, /browser-authorization|assetHeaderViolation/);
  assert.match(gateway, /kernel\('\/api\/v1\/analytics\/dashboards'\)/);
  assert.match(gateway, /http_api: 'UNAVAILABLE'/);
  assert.doesNotMatch(gateway, /fetch\(`http:\/\/127\.0\.0\.1:4315\$\{url\.pathname\}`/);
});

test('assets smoke drives real save/join controls and does not swallow failures', async () => {
  const smoke = await readFile(join(here, 'native-query-assets-smoke.mjs'), 'utf8');
  assert.match(smoke, /sendWhenReady/);
  assert.match(smoke, /QUESTIONS\[0\]/);
  assert.match(smoke, /analytics-query-save-button/);
  assert.match(smoke, /analytics-query-join-button/);
  assert.match(smoke, /analytics-cockpit-save/);
  assert.match(smoke, /missing visible control/);
  assert.doesNotMatch(smoke, /\.catch\(\(\) => \{\}\)/);
  assert.doesNotMatch(smoke, /includes\('合成查询'\)/);
});

test('HTTP overlay does not fetch the mock provider loopback', async () => {
  const overlay = await readFile(join(here, '../../dsh-plugins/analytics-workbench/src/client/asset-overlay.tsx'), 'utf8');
  assert.doesNotMatch(overlay, /127\.0\.0\.1:4319/);
  assert.doesNotMatch(overlay, /unavailable-probe/);
});
