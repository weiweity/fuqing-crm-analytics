import test from 'node:test';
import assert from 'node:assert/strict';
import { B0_DEMO_DISABLE_IDS, FOREIGN_PORTS, PINNED_SHA, PLUGIN_UI_ID, PORT_RANGE, PORTS } from './constants.mjs';
import { findReadyUrl, redactLaunchLog } from './launch-url.mjs';
import { assertNoB0Disables, buildPluginOverlay, pluginEnabled } from './overlay.mjs';
import { assertOwnedHost, assertOwnedPort } from './ports.mjs';
import { parseServeArgs } from './serve.mjs';

test('plugin overlay inserts file URL and never copies B0 demo disables', () => {
  const patch = buildPluginOverlay('/tmp/analytics-workbench');
  assert.equal(patch.length, 1);
  assert.equal(patch[0].insert[0].id, PLUGIN_UI_ID);
  assert.ok(patch[0].insert[0].name.startsWith('file:///tmp/analytics-workbench/lib/index.js'));
  assertNoB0Disables(patch);
  for (const id of B0_DEMO_DISABLE_IDS) {
    assert.equal(JSON.stringify(patch).includes(`"${id}"`), false);
  }
});

test('plugin flag only accepts on or off', () => {
  assert.equal(pluginEnabled('off'), false);
  assert.equal(pluginEnabled('on'), true);
  assert.throws(() => pluginEnabled('yes'));
});

test('owned ports reject B0 and Mission listeners', () => {
  assert.equal(assertOwnedPort(4327), PORTS.web);
  assert.deepEqual([...PORT_RANGE], [4325, 4326, 4327, 4328, 4329]);
  for (const port of FOREIGN_PORTS) {
    assert.throws(() => assertOwnedPort(port));
  }
  assert.throws(() => assertOwnedPort(80));
  assert.equal(assertOwnedHost('127.0.0.1'), '127.0.0.1');
  assert.throws(() => assertOwnedHost('0.0.0.0'));
});

test('serve args pin loopback and refuse foreign ports', () => {
  const options = parseServeArgs(['--plugin', 'off', '--web-port', '4327']);
  assert.equal(options.plugin, 'off');
  assert.equal(options.webPort, 4327);
  assert.equal(options.host, '127.0.0.1');
  assert.throws(() => parseServeArgs(['--web-port', '4317']));
  assert.throws(() => parseServeArgs(['--host', '0.0.0.0']));
  assert.throws(() => parseServeArgs(['--plugin', 'maybe']));
});

test('launch URL helper requires a tokenized loopback URL and redacts it', () => {
  const origin = 'http://127.0.0.1:4327';
  const log = 'dsh web: listening\nopen http://127.0.0.1:4327/?token=abc_DEF-123\n';
  assert.equal(findReadyUrl(log, origin), 'http://127.0.0.1:4327/?token=abc_DEF-123');
  assert.equal(findReadyUrl('http://127.0.0.1:4317/?token=abc\n', origin), null);
  assert.equal(findReadyUrl('http://127.0.0.1:4327/\n', origin), null);
  assert.ok(redactLaunchLog(log).includes('token=[REDACTED]'));
  assert.equal(redactLaunchLog(log).includes('abc_DEF-123'), false);
});

test('pinned SHA matches toolchain contract constant', () => {
  assert.equal(PINNED_SHA, 'd347e703908d0406b7a7ef80e3a0e594d86b2215');
});


test('value-taking flags cannot silently fall back after a missing argument', () => {
  for (const flag of ['--upstream', '--plugin-path', '--runtime', '--extra-patch', '--web-port']) {
    assert.throws(() => parseServeArgs([flag]), /missing value/);
    assert.throws(() => parseServeArgs([flag, '--fresh']), /missing value/);
  }
});
