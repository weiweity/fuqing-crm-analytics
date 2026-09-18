import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import {
  B0_DEMO_DISABLE_IDS, COMPETITION_VITE_PORT, COMPETITION_WEB_PORT, DEV_WEB_PORT, FOREIGN_PORTS,
  PINNED_SHA, PLUGIN_UI_ID, PORT_RANGE, PORTS, SHINE_BRAND_UI_ID, SHINE_WATERFALL_UI_ID, SHINE_CROWD_ACTION_UI_ID, SHINE_QUERY_UI_ID, SHINE_BOARD_UI_ID, SHINE_FUNNEL_UI_ID,
} from './constants.mjs';
import { findReadyUrl, redactLaunchLog } from './launch-url.mjs';
import { assertNoB0Disables, buildPluginDisable, buildPluginOverlay, buildShineBrandDisable, buildShineWaterfallDisable, buildShineCrowdActionDisable, buildShineQueryDisable, buildShineBoardDisable, buildShineFunnelDisable, pluginEnabled, pluginRowState } from './overlay.mjs';
import { defaultShineBrandPath, defaultShineWaterfallPath, defaultShineCrowdActionPath, defaultShineQueryPath, defaultShineBoardPath, defaultShineFunnelPath } from './paths.mjs';
import { assertOwnedHost, assertOwnedPort } from './ports.mjs';
import { isolatedEnv, parseServeArgs, profileInstallPaths, profilePluginAddArgs, resolveShineBrandPath, resolveShineWaterfallPath, resolveShineCrowdActionPath, resolveShineQueryPath, resolveShineBoardPath, resolveShineFunnelPath } from './serve.mjs';

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
    delete process.env.NODE_EXTRA_CA_CERTS;
    const fallback = isolatedEnv('/tmp/runtime', '/tmp/runtime/harness');
    if (existsSync('/etc/ssl/cert.pem')) assert.equal(fallback.NODE_EXTRA_CA_CERTS, '/etc/ssl/cert.pem');
    assert.equal(fallback.DEEPSEEK_API_KEY, undefined);
    process.env.NODE_EXTRA_CA_CERTS = 'relative.pem';
    assert.throws(() => isolatedEnv('/tmp/runtime', '/tmp/runtime/harness'), /absolute public CA/);
  } finally {
    for (const [key, value] of Object.entries(prior)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});

test('plugin overlay carries only the brand-assets and page-globals rows and never copies B0 demo disables', () => {
  const patch = buildPluginOverlay('/tmp/analytics-workbench');
  assert.equal(patch.length, 1);
  assert.deepEqual(patch[0].insert.map(row => row.id),
    ['analytics-dev-brand-assets', 'analytics-dev-page-globals']);
  assert.equal(patch[0].insert[0].name.endsWith('/brand.mjs'), true);
  assert.equal(patch[0].insert[1].name.endsWith('/page-globals.mjs'), true);
  // The business plugin installs as a profile bundle; a second
  // analytics-workbench-ui row here would shadow it with a stale copy.
  assert.equal(JSON.stringify(patch).includes(PLUGIN_UI_ID), false);
  assertNoB0Disables(patch);
  for (const id of B0_DEMO_DISABLE_IDS) {
    assert.equal(JSON.stringify(patch).includes(`"${id}"`), false);
  }
});

test('plugin-on install is dsh plugin add of the absolute workbench path', () => {
  const cli = '/abs/upstream/apps/cli/lib/bin.js';
  const plugin = '/abs/dsh-plugins/analytics-workbench';
  assert.deepEqual(profilePluginAddArgs(cli, plugin), [cli, 'plugin', '--profile', 'web', 'add', plugin]);
  assert.throws(() => profilePluginAddArgs(cli, 'dsh-plugin'), /absolute/);
});

test('shine-brand path is the repo package, not a sibling of --plugin-path', () => {
  const isolatedWorkbench = '/tmp/clean-build-workbench';
  assert.equal(
    resolveShineBrandPath({ plugin: 'on', shineBrand: 'on', pluginPath: isolatedWorkbench }),
    defaultShineBrandPath(),
  );
  assert.equal(resolveShineBrandPath({ plugin: 'on', shineBrand: 'off', pluginPath: isolatedWorkbench }), null);
  assert.equal(resolveShineBrandPath({ plugin: 'off', shineBrand: 'on' }), null);
  const explicit = '/abs/dsh-plugins/shine-brand';
  assert.equal(
    resolveShineBrandPath({ plugin: 'on', shineBrand: 'on', shineBrandPath: explicit }),
    explicit,
  );
});

test('plugin-on install order is brand, waterfall, crowd-action, query, board, then workbench', () => {
  const workbench = '/abs/dsh-plugins/analytics-workbench';
  const brand = defaultShineBrandPath();
  const waterfall = defaultShineWaterfallPath();
  const crowd = defaultShineCrowdActionPath();
  const query = defaultShineQueryPath();
  const board = defaultShineBoardPath();
  const funnel = defaultShineFunnelPath();
  assert.deepEqual(profileInstallPaths({
    pluginPath: workbench, shineBrandPath: brand, shineWaterfallPath: waterfall,
    shineCrowdActionPath: crowd, shineQueryPath: query, shineBoardPath: board, shineFunnelPath: funnel,
  }), [brand, waterfall, crowd, query, board, funnel, workbench]);
  assert.deepEqual(profileInstallPaths({
    pluginPath: workbench, shineBrandPath: null, shineWaterfallPath: null, shineCrowdActionPath: null,
    shineQueryPath: null, shineBoardPath: null, shineFunnelPath: null,
  }), [workbench]);
});

test('waterfall path is the repo package, not a sibling of --plugin-path', () => {
  const isolatedWorkbench = '/tmp/clean-build-workbench';
  assert.equal(
    resolveShineWaterfallPath({ plugin: 'on', shineWaterfall: 'on', pluginPath: isolatedWorkbench }),
    defaultShineWaterfallPath(),
  );
  assert.equal(resolveShineWaterfallPath({ plugin: 'on', shineWaterfall: 'off', pluginPath: isolatedWorkbench }), null);
  assert.equal(resolveShineWaterfallPath({ plugin: 'off', shineWaterfall: 'on' }), null);
});

test('crowd-action path is the repo package, not a sibling of --plugin-path', () => {
  const isolatedWorkbench = '/tmp/clean-build-workbench';
  assert.equal(
    resolveShineCrowdActionPath({ plugin: 'on', shineCrowdAction: 'on', pluginPath: isolatedWorkbench }),
    defaultShineCrowdActionPath(),
  );
  assert.equal(resolveShineCrowdActionPath({ plugin: 'on', shineCrowdAction: 'off', pluginPath: isolatedWorkbench }), null);
  assert.equal(resolveShineCrowdActionPath({ plugin: 'off', shineCrowdAction: 'on' }), null);
});

test('plugin-off layer disables the installed bundle and never touches native rows', () => {
  const patch = buildPluginDisable();
  assert.deepEqual(patch, [
    { id: PLUGIN_UI_ID, disabled: true },
    { id: SHINE_BRAND_UI_ID, disabled: true },
    { id: SHINE_WATERFALL_UI_ID, disabled: true },
    { id: SHINE_CROWD_ACTION_UI_ID, disabled: true },
    { id: SHINE_QUERY_UI_ID, disabled: true },
    { id: SHINE_BOARD_UI_ID, disabled: true },
    { id: SHINE_FUNNEL_UI_ID, disabled: true },
  ]);
  assertNoB0Disables(patch);
});

test('shine-brand-off overlay disables leftover brand without touching workbench', () => {
  const patch = buildShineBrandDisable();
  assert.deepEqual(patch, [{ id: SHINE_BRAND_UI_ID, disabled: true }]);
  assert.equal(JSON.stringify(patch).includes(PLUGIN_UI_ID), false);
  assertNoB0Disables(patch);
});

test('waterfall-off overlay disables leftover waterfall without touching workbench', () => {
  const patch = buildShineWaterfallDisable();
  assert.deepEqual(patch, [{ id: SHINE_WATERFALL_UI_ID, disabled: true }]);
  assert.equal(JSON.stringify(patch).includes(PLUGIN_UI_ID), false);
  assertNoB0Disables(patch);
});

test('crowd-action-off overlay disables leftover crowd-action without touching workbench', () => {
  const patch = buildShineCrowdActionDisable();
  assert.deepEqual(patch, [{ id: SHINE_CROWD_ACTION_UI_ID, disabled: true }]);
  assert.equal(JSON.stringify(patch).includes(PLUGIN_UI_ID), false);
  assertNoB0Disables(patch);
});

test('query and board paths are repo packages; off omits them', () => {
  assert.equal(resolveShineQueryPath({ plugin: 'on', shineQuery: 'on' }), defaultShineQueryPath());
  assert.equal(resolveShineQueryPath({ plugin: 'on', shineQuery: 'off' }), null);
  assert.equal(resolveShineBoardPath({ plugin: 'on', shineBoard: 'on' }), defaultShineBoardPath());
  assert.equal(resolveShineBoardPath({ plugin: 'on', shineBoard: 'off' }), null);
  assert.deepEqual(buildShineQueryDisable(), [{ id: SHINE_QUERY_UI_ID, disabled: true }]);
  assert.deepEqual(buildShineBoardDisable(), [{ id: SHINE_BOARD_UI_ID, disabled: true }]);
  assert.equal(resolveShineFunnelPath({ plugin: 'on', shineFunnel: 'on' }), defaultShineFunnelPath());
  assert.equal(resolveShineFunnelPath({ plugin: 'on', shineFunnel: 'off' }), null);
  assert.deepEqual(buildShineFunnelDisable(), [{ id: SHINE_FUNNEL_UI_ID, disabled: true }]);
});

test('plugin row state tells a disabled plugin-off row from an active plugin-on row', () => {
  const header = `# == @shine-mage/dsh-analytics-workbench-b0\n- id: ${PLUGIN_UI_ID}\n  name: '@shine-mage/dsh-analytics-workbench-b0'\n`;
  assert.deepEqual(pluginRowState(`${header}  disabled: true\n`), { present: true, disabled: true });
  assert.deepEqual(pluginRowState(`${header}- id: next-row\n`), { present: true, disabled: false });
  assert.deepEqual(pluginRowState('- id: other-row\n  disabled: true\n'), { present: false, disabled: false });
  const brand = `# == @shine-mage/dsh-shine-brand\n- id: ${SHINE_BRAND_UI_ID}\n  name: '@shine-mage/dsh-shine-brand'\n`;
  assert.deepEqual(pluginRowState(`${brand}  disabled: true\n`, SHINE_BRAND_UI_ID), { present: true, disabled: true });
  assert.deepEqual(pluginRowState(header, SHINE_BRAND_UI_ID), { present: false, disabled: false });
});

test('plugin flag only accepts on or off', () => {
  assert.equal(pluginEnabled('off'), false);
  assert.equal(pluginEnabled('on'), true);
  assert.throws(() => pluginEnabled('yes'));
});

test('owned ports reject B0 and Mission listeners', () => {
  assert.equal(assertOwnedPort(4327), PORTS.web);
  assert.equal(assertOwnedPort(COMPETITION_WEB_PORT), COMPETITION_WEB_PORT);
  assert.equal(assertOwnedPort(DEV_WEB_PORT), DEV_WEB_PORT);
  for (const port of [6666, 6665, 6000, 10080]) {
    assert.throws(() => assertOwnedPort(port), /ERR_UNSAFE_PORT/);
  }
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
  assert.equal(parseServeArgs(['--plugin', 'on', '--web-port', '6677']).webPort, DEV_WEB_PORT);
  assert.equal(parseServeArgs(['--plugin', 'on', '--web-port', '6677']).shineBrand, 'on');
  assert.equal(parseServeArgs(['--plugin', 'on', '--shine-brand', 'off', '--web-port', '6677']).shineBrand, 'off');
  assert.equal(
    parseServeArgs(['--plugin', 'on', '--shine-brand-path', '/abs/shine-brand', '--web-port', '6677']).shineBrandPath,
    '/abs/shine-brand',
  );
  assert.throws(() => parseServeArgs(['--plugin', 'on', '--shine-brand', 'off', '--shine-brand-path', '/abs/shine-brand']));
  assert.equal(parseServeArgs(['--plugin', 'on', '--web-port', '6677']).shineWaterfall, 'on');
  assert.equal(parseServeArgs(['--plugin', 'on', '--waterfall', 'off', '--web-port', '6677']).shineWaterfall, 'off');
  assert.throws(() => parseServeArgs(['--plugin', 'on', '--waterfall', 'off', '--waterfall-path', '/abs/shine-waterfall']));
  assert.equal(parseServeArgs(['--plugin', 'on', '--web-port', '6677']).shineCrowdAction, 'on');
  assert.equal(parseServeArgs(['--plugin', 'on', '--crowd-action', 'off', '--web-port', '6677']).shineCrowdAction, 'off');
  assert.throws(() => parseServeArgs(['--plugin', 'on', '--crowd-action', 'off', '--crowd-action-path', '/abs/shine-crowd-action']));
  assert.equal(parseServeArgs(['--plugin', 'on', '--web-port', '6677']).shineQuery, 'on');
  assert.equal(parseServeArgs(['--plugin', 'on', '--query', 'off', '--web-port', '6677']).shineQuery, 'off');
  assert.equal(parseServeArgs(['--plugin', 'on', '--web-port', '6677']).shineBoard, 'on');
  assert.equal(parseServeArgs(['--plugin', 'on', '--board', 'off', '--web-port', '6677']).shineBoard, 'off');
  assert.throws(() => parseServeArgs(['--plugin', 'on', '--query', 'off', '--query-path', '/abs/shine-query']));
  assert.throws(() => parseServeArgs(['--plugin', 'on', '--board', 'off', '--board-path', '/abs/shine-board']));
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
  assert.equal(PINNED_SHA, 'ddefc45fbc7f8e46dd73185e68295696d1297887');
});


test('value-taking flags cannot silently fall back after a missing argument', () => {
  for (const flag of ['--upstream', '--plugin-path', '--shine-brand', '--shine-brand-path', '--waterfall', '--waterfall-path', '--crowd-action', '--crowd-action-path', '--query', '--query-path', '--board', '--board-path', '--funnel', '--funnel-path', '--runtime', '--extra-patch', '--web-port']) {
    assert.throws(() => parseServeArgs([flag]), /missing value/);
    assert.throws(() => parseServeArgs([flag, '--fresh']), /missing value/);
  }
});
