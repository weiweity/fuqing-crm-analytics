#!/usr/bin/env node
/** Local DSH-base entry. Does not manage 8000/5173/15173/4315-4319. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { writeFile, mkdir, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { ALLOWED_WEB_PORTS, COMPETITION_VITE_PORT, COMPETITION_WEB_PORT, DEV_WEB_PORT, NATIVE_WEB_IDS, NODE_MAJOR, PLUGIN_UI_ID, SHINE_BRAND_UI_ID, SHINE_WATERFALL_UI_ID, SHINE_CROWD_ACTION_UI_ID, SHINE_QUERY_UI_ID, SHINE_BOARD_UI_ID, SHINE_FUNNEL_UI_ID } from './constants.mjs';
import { pluginEnabled, pluginRowState } from './overlay.mjs';
import { repoRoot, contextRoot, currentPath, defaultPluginPath, defaultShineBrandPath, defaultShineWaterfallPath, defaultShineCrowdActionPath, defaultShineQueryPath, defaultShineBoardPath, defaultShineFunnelPath, defaultRuntimeRoot } from './paths.mjs';
import { PAGE_HTTP_DEFAULT_PORT, startPageHttp, writePageHttpState } from './page-http.mjs';
import { ensurePersistentRuntime } from './persist-runtime.mjs';
import { randomBytes } from 'node:crypto';
import { bootHost, dumpConfig, installProfilePlugin, isolatedEnv, parseServeArgs, prepareRuntime, readCurrent, runOwnedSupervisor, stopOwned, watchOwnedStart } from './serve.mjs';
import { diagnose, printDiagnose } from './diagnose.mjs';

const USAGE = `Usage: node scripts/dsh-dev/cli.mjs <check|dump-config|start|stop|status|diagnose|reload>
  --upstream /absolute/pinned/dsh
  --plugin on|off
  --plugin-path /absolute/workbench
  --shine-brand on|off
  --shine-brand-path /absolute/shine-brand
  --waterfall on|off
  --waterfall-path /absolute/shine-waterfall
  --crowd-action on|off
  --crowd-action-path /absolute/shine-crowd-action
  --query on|off
  --query-path /absolute/shine-query
  --board on|off
  --board-path /absolute/shine-board
  --funnel on|off
  --funnel-path /absolute/shine-funnel
  --extra-patch /absolute/overlay.yml
  --runtime /absolute/runtime
  --web-port ${ALLOWED_WEB_PORTS.join('|')}
  --host 127.0.0.1
  --page-http on|off   start the isolated page-documents/result-access HTTP (default ${PAGE_HTTP_DEFAULT_PORT}, never 6677) and inject PAGE_* into the web host
  --page-http-port N   custom loopback port for that listener
  --detach          start only
  --fresh           NEW empty runtime (wipes API keys and extra plugins). Daily plugin rebuilds must use reload, not --fresh.

--plugin on installs workbench and the feature packs from repo paths (not siblings of --plugin-path). --query off / --board off drop session query tools or cockpit generate independently. --plugin off disables every shine UI id.
reload  builds workbench and the enabled feature packs, restarts 6677 on the durable runtime, and opens the launch URL without printing the token.
--page-http on boots an isolated page-documents/result-access HTTP on 127.0.0.1:${PAGE_HTTP_DEFAULT_PORT} (small SQLite, explicit page_state_dir, never 6677) and forwards PAGE_* env so the browser bundle configures its page store; without it generation/saves stay http_not_configured instead of silently targeting 6677.

Node 24 required for check/start/reload. diagnose is read-only: it never binds ports or signals PIDs.
User demo 127.0.0.1:4327 / 8000 / 5173 must not be stopped or reused.
Independent DSH: --web-port ${COMPETITION_WEB_PORT}. Vite ${COMPETITION_VITE_PORT} is reserved and not bound here.
Launch tokens are never printed. Unauthenticated GET / must stay 401.`;

function parseArgv(argv) {
  const [command, ...rest] = argv;
  assert.ok(['check', 'dump-config', 'start', 'stop', 'status', 'diagnose', 'reload'].includes(command), USAGE);
  if (command === 'reload') {
    const flags = rest.filter(flag => flag !== '--fresh' && flag !== '--detach');
    const options = parseServeArgs(flags.includes('--plugin') ? flags : ['--plugin', 'on', '--web-port', String(DEV_WEB_PORT), ...flags]);
    options.fresh = false;
    options.detach = true;
    options.runtime = options.runtime ?? defaultRuntimeRoot();
    return { command, options };
  }
  if (command === 'stop' || command === 'status' || command === 'diagnose') {
    if (command === 'diagnose') {
      const upstreamFlag = rest.indexOf('--upstream');
      const options = {};
      if (upstreamFlag >= 0) {
        assert.ok(rest[upstreamFlag + 1] && !rest[upstreamFlag + 1].startsWith('--'), 'missing value for --upstream');
        options.upstream = rest[upstreamFlag + 1];
      }
      return { command, options };
    }
    assert.equal(rest.length, 0, `${command} takes no flags`);
    return { command };
  }
  return { command, options: parseServeArgs(rest) };
}

function assertDumpContainsNative(text) {
  for (const id of NATIVE_WEB_IDS) {
    assert.ok(text.includes(`id: ${id}`) || text.includes(`- id: ${id}`), `dump missing native id ${id}`);
  }
  assert.ok(!text.includes('analytics-b0'), 'dump must not pin the B0 analytics-b0 preset as the product default');
}

async function runCheck(options) {
  const prepared = await prepareRuntime({ ...options, fresh: options.runtime ? options.fresh : true });
  if (prepared.enabled) installProfilePlugin(prepared);
  const dump = await dumpConfig(prepared);
  await writeFile(join(prepared.runtime, 'dump-config.txt'), dump, { mode: 0o600 });
  assertDumpContainsNative(dump);
  const workbench = pluginRowState(dump, PLUGIN_UI_ID);
  const brand = pluginRowState(dump, SHINE_BRAND_UI_ID);
  const waterfall = pluginRowState(dump, SHINE_WATERFALL_UI_ID);
  const crowd = pluginRowState(dump, SHINE_CROWD_ACTION_UI_ID);
  const query = pluginRowState(dump, SHINE_QUERY_UI_ID);
  const board = pluginRowState(dump, SHINE_BOARD_UI_ID);
  const funnel = pluginRowState(dump, SHINE_FUNNEL_UI_ID);
  if (prepared.enabled) {
    assert.equal(workbench.present, true, 'plugin overlay was not composed into dump-config');
    assert.equal(workbench.disabled, false, 'plugin row is disabled while --plugin on');
    if (prepared.shineBrandPath) {
      assert.equal(brand.present, true, 'shine-brand overlay was not composed into dump-config');
      assert.equal(brand.disabled, false, 'shine-brand row is disabled while --shine-brand on');
    } else if (brand.present) {
      assert.equal(brand.disabled, true, 'shine-brand row is still active while --shine-brand off');
    }
    if (prepared.shineWaterfallPath) {
      assert.equal(waterfall.present, true, 'shine-waterfall overlay was not composed into dump-config');
      assert.equal(waterfall.disabled, false, 'shine-waterfall row is disabled while --waterfall on');
    } else if (waterfall.present) {
      assert.equal(waterfall.disabled, true, 'shine-waterfall row is still active while --waterfall off');
    }
    if (prepared.shineCrowdActionPath) {
      assert.equal(crowd.present, true, 'shine-crowd-action overlay was not composed into dump-config');
      assert.equal(crowd.disabled, false, 'shine-crowd-action row is disabled while --crowd-action on');
    } else if (crowd.present) {
      assert.equal(crowd.disabled, true, 'shine-crowd-action row is still active while --crowd-action off');
    }
    if (prepared.shineQueryPath) {
      assert.equal(query.present, true, 'shine-query overlay was not composed into dump-config');
      assert.equal(query.disabled, false, 'shine-query row is disabled while --query on');
    } else if (query.present) {
      assert.equal(query.disabled, true, 'shine-query row is still active while --query off');
    }
    if (prepared.shineBoardPath) {
      assert.equal(board.present, true, 'shine-board overlay was not composed into dump-config');
      assert.equal(board.disabled, false, 'shine-board row is disabled while --board on');
    } else if (board.present) {
      assert.equal(board.disabled, true, 'shine-board row is still active while --board off');
    }
    if (prepared.shineFunnelPath) {
      assert.equal(funnel.present, true, 'shine-funnel overlay was not composed into dump-config');
      assert.equal(funnel.disabled, false, 'shine-funnel row is disabled while --funnel on');
    } else if (funnel.present) {
      assert.equal(funnel.disabled, true, 'shine-funnel row is still active while --funnel off');
    }
  } else {
    assert.equal(workbench.disabled, true, 'plugin row is still active in a plugin-off dump');
    if (brand.present) {
      assert.equal(brand.disabled, true, 'shine-brand row is still active in a plugin-off dump');
    }
    if (waterfall.present) {
      assert.equal(waterfall.disabled, true, 'shine-waterfall row is still active in a plugin-off dump');
    }
    if (crowd.present) {
      assert.equal(crowd.disabled, true, 'shine-crowd-action row is still active in a plugin-off dump');
    }
    if (query.present) {
      assert.equal(query.disabled, true, 'shine-query row is still active in a plugin-off dump');
    }
    if (board.present) {
      assert.equal(board.disabled, true, 'shine-board row is still active in a plugin-off dump');
    }
    if (funnel.present) {
      assert.equal(funnel.disabled, true, 'shine-funnel row is still active in a plugin-off dump');
    }
  }
  console.log(`DSH_DEV_CHECK pinned=${prepared.verified.upstream_sha} plugin=${prepared.enabled ? 'on' : 'off'}`);
  console.log(`DSH_DEV_DUMP ${join(prepared.runtime, 'dump-config.txt')}`);
  return prepared;
}

async function runStart(options) {
  await mkdir(contextRoot(), { recursive: true, mode: 0o700 });
  const abort = new AbortController();
  const onSignal = () => abort.abort();
  process.once('SIGTERM', onSignal);
  process.once('SIGINT', onSignal);
  let pageHttp = null;
  try {
    await runOwnedSupervisor({
      contextDir: contextRoot(),
      startId: process.env.DSH_DEV_START_ID,
      signal: abort.signal,
      boot: async ({ signal }) => {
        const prepared = await prepareRuntime(options);
        const tls = isolatedEnv(prepared.runtime, prepared.home).NODE_EXTRA_CA_CERTS;
        console.log(tls ? `DSH_DEV_TLS ${tls}` : 'DSH_DEV_TLS missing; Node 24 cannot verify api.deepseek.com without a CA bundle');
        if (prepared.enabled) installProfilePlugin(prepared);
        // The isolated page HTTP is supervisor-owned: it starts before the
        // web host (so PAGE_* reach the host env through isolatedEnv) and
        // stops with the supervisor. Default off; explicit --page-http on.
        // A caller-configured PAGE_DOCUMENTS_HTTP_BASE is forwarded as-is.
        if (options.pageHttp === 'on') {
          assert.equal(process.env.PAGE_DOCUMENTS_HTTP_BASE, undefined,
            'PAGE_DOCUMENTS_HTTP_BASE is already set in the caller env; dsh-dev forwards it as-is instead of spawning its own listener');
          pageHttp = await startPageHttp({
            port: options.pageHttpPort ?? PAGE_HTTP_DEFAULT_PORT,
            stateDir: join(prepared.runtime, 'page-documents'),
            signal,
          });
          await writePageHttpState(prepared.runtime, pageHttp);
          process.env.PAGE_DOCUMENTS_HTTP_BASE = pageHttp.base;
          process.env.PAGE_DOCUMENTS_HTTP_TOKEN = pageHttp.token;
          delete process.env.PAGE_RESULT_HTTP_BASE;
          delete process.env.PAGE_RESULT_HTTP_TOKEN;
          console.log(`DSH_DEV_PAGE_HTTP ${pageHttp.base} (documents+result on one listener; token not printed)`);
        }
        const booted = await bootHost(prepared, { signal });
        return { ...prepared, ...booted, pageHttpBase: pageHttp?.base ?? null,
          cleanup: async () => { await pageHttp?.stop(); } };
      },
    });
  } finally {
    process.removeListener('SIGTERM', onSignal);
    process.removeListener('SIGINT', onSignal);
  }
}

async function openLaunchUrl(runtime) {
  const priv = JSON.parse(await readFile(join(runtime, 'browser-private.json'), 'utf8'));
  assert.equal(typeof priv.launchUrl, 'string');
  assert.equal(typeof priv.launchOrigin, 'string');
  const opener = process.platform === 'darwin' ? 'open' : 'xdg-open';
  spawn(opener, [priv.launchUrl], { stdio: 'ignore', detached: true }).unref();
  console.log(`DSH_DEV_OPEN ${priv.launchOrigin}/ (launch token not printed)`);
}

function buildLocalPlugin(dir) {
  const built = spawnSync(process.execPath, [join(dir, 'build.mjs')], {
    cwd: dir, stdio: 'inherit', env: process.env, timeout: 180000,
  });
  assert.equal(built.status, 0, `plugin build.mjs failed (${dir})`);
}

function reloadStartArgs(options, runtime) {
  const args = [
    join(repoRoot, 'scripts/dsh-dev/cli.mjs'), 'start',
    '--plugin', options.plugin || 'on',
    '--web-port', String(options.webPort || DEV_WEB_PORT),
    '--runtime', runtime,
  ];
  if (options.pluginPath) args.push('--plugin-path', options.pluginPath);
  if (options.shineBrand) args.push('--shine-brand', options.shineBrand);
  if (options.shineBrandPath) args.push('--shine-brand-path', options.shineBrandPath);
  if (options.shineWaterfall) args.push('--waterfall', options.shineWaterfall);
  if (options.shineWaterfallPath) args.push('--waterfall-path', options.shineWaterfallPath);
  if (options.shineCrowdAction) args.push('--crowd-action', options.shineCrowdAction);
  if (options.shineCrowdActionPath) args.push('--crowd-action-path', options.shineCrowdActionPath);
  if (options.shineQuery) args.push('--query', options.shineQuery);
  if (options.shineQueryPath) args.push('--query-path', options.shineQueryPath);
  if (options.shineBoard) args.push('--board', options.shineBoard);
  if (options.shineBoardPath) args.push('--board-path', options.shineBoardPath);
  if (options.shineFunnel) args.push('--funnel', options.shineFunnel);
  if (options.shineFunnelPath) args.push('--funnel-path', options.shineFunnelPath);
  if (options.pageHttp) args.push('--page-http', options.pageHttp);
  if (options.pageHttpPort !== undefined) args.push('--page-http-port', String(options.pageHttpPort));
  return args;
}

async function runReload(options) {
  assert.equal(Number(process.versions.node.split('.')[0]), NODE_MAJOR, `Use Node ${NODE_MAJOR}`);
  const runtime = await ensurePersistentRuntime({ dest: options.runtime ?? defaultRuntimeRoot() });
  buildLocalPlugin(options.pluginPath ?? defaultPluginPath());
  if (pluginEnabled(options.plugin || 'on') && pluginEnabled(options.shineBrand ?? 'on')) {
    buildLocalPlugin(options.shineBrandPath ?? defaultShineBrandPath());
  }
  if (pluginEnabled(options.plugin || 'on') && pluginEnabled(options.shineWaterfall ?? 'on')) {
    buildLocalPlugin(options.shineWaterfallPath ?? defaultShineWaterfallPath());
  }
  if (pluginEnabled(options.plugin || 'on') && pluginEnabled(options.shineCrowdAction ?? 'on')) {
    buildLocalPlugin(options.shineCrowdActionPath ?? defaultShineCrowdActionPath());
  }
  if (pluginEnabled(options.plugin || 'on') && pluginEnabled(options.shineQuery ?? 'on')) {
    buildLocalPlugin(options.shineQueryPath ?? defaultShineQueryPath());
  }
  if (pluginEnabled(options.plugin || 'on') && pluginEnabled(options.shineBoard ?? 'on')) {
    buildLocalPlugin(options.shineBoardPath ?? defaultShineBoardPath());
  }
  if (pluginEnabled(options.plugin || 'on') && pluginEnabled(options.shineFunnel ?? 'on')) {
    buildLocalPlugin(options.shineFunnelPath ?? defaultShineFunnelPath());
  }
  await stopOwned();
  const startId = randomBytes(16).toString('hex');
  const child = spawn(process.execPath, reloadStartArgs(options, runtime), {
    cwd: repoRoot,
    env: { ...process.env, DSH_DEV_START_ID: startId },
    detached: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout?.unref();
  child.stderr?.unref();
  child.unref();
  console.log(`DSH_DEV_DETACHED pid=${child.pid}`);
  const origin = `http://127.0.0.1:${options.webPort || DEV_WEB_PORT}`;
  await watchOwnedStart(child, { origin, runtime, currentPath: currentPath(), startId });
  await openLaunchUrl(runtime);
  console.log(`DSH_DEV_RELOADED runtime=${runtime}`);
}

async function runStatus() {
  const current = await readCurrent();
  if (!current) {
    console.log('DSH_DEV_STATUS stopped');
    return;
  }
  let alive = false;
  const control = current.control;
  if (Number.isInteger(control?.port) && control.port > 0 && control.port <= 65535
    && typeof control.token === 'string' && control.token.length >= 32) {
    try {
      const response = await fetch(`http://127.0.0.1:${control.port}/status`, {
        headers: { authorization: `Bearer ${control.token}` }, redirect: 'error', signal: AbortSignal.timeout(1500),
      });
      alive = response.status === 200;
    } catch { /* stale supervisor: no signal is sent */ }
  }
  console.log(`DSH_DEV_STATUS ${alive ? 'running' : 'stale'} pid=${current.childPid ?? 'none'} web=${current.host}:${current.webPort}`);
  console.log(`DSH_DEV_RUNTIME ${current.runtime}`);
  console.log(`DSH_DEV_PLUGIN ${current.pluginEnabled ? current.plugin : 'off'}`);
  console.log(`DSH_DEV_SHINE_BRAND ${current.shineBrand ?? 'off'}`);
  console.log(`DSH_DEV_WATERFALL ${current.shineWaterfall ?? 'off'}`);
  console.log(`DSH_DEV_CROWD_ACTION ${current.shineCrowdAction ?? 'off'}`);
  console.log(`DSH_DEV_QUERY ${current.shineQuery ?? 'off'}`);
  console.log(`DSH_DEV_BOARD ${current.shineBoard ?? 'off'}`);
  console.log(`DSH_DEV_FUNNEL ${current.shineFunnel ?? 'off'}`);
  console.log(`DSH_DEV_PAGE_HTTP ${current.pageHttpBase ?? 'off'}`);
}

function isCliEntry() {
  const entry = process.argv[1];
  if (!entry) return false;
  const self = fileURLToPath(import.meta.url);
  return self === entry || self === resolve(entry);
}

if (isCliEntry()) {
  const { command, options } = parseArgv(process.argv.slice(2));
  if (command === 'diagnose') printDiagnose(await diagnose(options ?? {}));
  else if (command === 'check' || command === 'dump-config') await runCheck(options);
  else if (command === 'start') {
    if (options.detach) {
      const child = spawn(process.execPath, [join(repoRoot, 'scripts/dsh-dev/cli.mjs'), 'start',
        ...process.argv.slice(3).filter(flag => flag !== '--detach')], {
        cwd: repoRoot, detached: true, stdio: 'ignore', env: process.env,
      });
      child.unref();
      console.log(`DSH_DEV_DETACHED pid=${child.pid}`);
    } else {
      await runStart(options);
    }
  } else if (command === 'reload') {
    await runReload(options);
  } else if (command === 'stop') {
    const result = await stopOwned();
    console.log(result.stopped ? 'DSH_DEV_STOPPED acknowledged by owned supervisor' : 'DSH_DEV_STATUS stopped');
  } else if (command === 'status') await runStatus();
}
