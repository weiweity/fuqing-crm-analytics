import test from 'node:test';
import assert from 'node:assert/strict';
import {
  B0_DEMO_DISABLE_IDS, COMPETITION_VITE_PORT, COMPETITION_WEB_PORT, FOREIGN_PORTS,
  PINNED_SHA, PLUGIN_UI_ID, PORT_RANGE, PORTS,
} from './constants.mjs';
import { findReadyUrl, redactLaunchLog } from './launch-url.mjs';
import { assertNoB0Disables, buildPluginOverlay, pluginEnabled } from './overlay.mjs';
import { assertOwnedHost, assertOwnedPort } from './ports.mjs';
import { isolatedEnv, parseServeArgs } from './serve.mjs';

test('isolated launch accepts an explicit public CA bundle without forwarding keys or TLS bypass', () => {
  const additions = {
    NODE_EXTRA_CA_CERTS: '/tmp/public-ca.pem',
    NODE_TLS_REJECT_UNAUTHORIZED: '0',
    DEEPSEEK_API_KEY: 'synthetic-key-not-real',
    COMPETITION_HTTP_BASE: 'http://127.0.0.1:18083',
    COMPETITION_HTTP_TOKEN: 'synthetic-competition-token',
  };
  const prior = Object.fromEntries(Object.keys(additions).map(key => [key, process.env[key]]));
  try {
    Object.assign(process.env, additions);
    const env = isolatedEnv('/tmp/runtime', '/tmp/runtime/harness');
    assert.equal(env.NODE_EXTRA_CA_CERTS, '/tmp/public-ca.pem');
    assert.equal(env.NODE_TLS_REJECT_UNAUTHORIZED, undefined);
    assert.equal(env.DEEPSEEK_API_KEY, undefined);
    assert.equal(env.COMPETITION_HTTP_BASE, 'http://127.0.0.1:18083');
    process.env.NODE_EXTRA_CA_CERTS = 'relative.pem';
    assert.throws(() => isolatedEnv('/tmp/runtime', '/tmp/runtime/harness'), /absolute public CA/);
  } finally {
    for (const [key, value] of Object.entries(prior)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});

test('plugin overlay carries only the brand-assets row and never copies B0 demo disables', () => {
  const patch = buildPluginOverlay('/tmp/analytics-workbench');
  assert.equal(patch.length, 1);
  assert.equal(patch[0].insert.length, 1);
  assert.equal(patch[0].insert[0].id, 'analytics-dev-brand-assets');
  // The business plugin installs as a profile bundle; a second
  // analytics-workbench-ui row here would shadow it with a stale copy.
  assert.equal(JSON.stringify(patch).includes(PLUGIN_UI_ID), false);
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
  assert.equal(assertOwnedPort(COMPETITION_WEB_PORT), COMPETITION_WEB_PORT);
  assert.deepEqual([...PORT_RANGE], [4325, 4326, 4327, 4328, 4329]);
  for (const port of FOREIGN_PORTS) {
    assert.throws(() => assertOwnedPort(port));
  }
  assert.throws(() => assertOwnedPort(80));
  assert.throws(() => assertOwnedPort(COMPETITION_VITE_PORT));
  assert.equal(assertOwnedHost('127.0.0.1'), '127.0.0.1');
  assert.throws(() => assertOwnedHost('0.0.0.0'));
});

test('serve args pin loopback and refuse foreign ports', () => {
  const options = parseServeArgs(['--plugin', 'off', '--web-port', '4327']);
  assert.equal(options.plugin, 'off');
  assert.equal(options.webPort, 4327);
  assert.equal(options.host, '127.0.0.1');
  assert.equal(parseServeArgs(['--plugin', 'off', '--web-port', '14327']).webPort, COMPETITION_WEB_PORT);
  assert.throws(() => parseServeArgs(['--web-port', '4317']));
  assert.throws(() => parseServeArgs(['--web-port', '15173']));
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
