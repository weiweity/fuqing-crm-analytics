#!/usr/bin/env node
/** Local DSH-base entry. Does not manage 8000/5173/15173/4315-4319. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { writeFile, mkdir, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { ALLOWED_WEB_PORTS, COMPETITION_VITE_PORT, COMPETITION_WEB_PORT, DEV_WEB_PORT, NATIVE_WEB_IDS, NODE_MAJOR } from './constants.mjs';
import { pluginRowState } from './overlay.mjs';
import { repoRoot, contextRoot, currentPath, defaultPluginPath, defaultRuntimeRoot } from './paths.mjs';
import { ensurePersistentRuntime } from './persist-runtime.mjs';
import { randomBytes } from 'node:crypto';
import { bootHost, dumpConfig, installProfilePlugin, isolatedEnv, parseServeArgs, prepareRuntime, readCurrent, runOwnedSupervisor, stopOwned, watchOwnedStart } from './serve.mjs';
import { diagnose, printDiagnose } from './diagnose.mjs';

const USAGE = `Usage: node scripts/dsh-dev/cli.mjs <check|dump-config|start|stop|status|diagnose|reload>
  --upstream /absolute/pinned/dsh
  --plugin on|off
  --plugin-path /absolute/plugin
  --extra-patch /absolute/overlay.yml
  --runtime /absolute/runtime
  --web-port ${ALLOWED_WEB_PORTS.join('|')}
  --host 127.0.0.1
  --detach          start only
  --fresh           NEW empty runtime (wipes API keys and extra plugins). Daily plugin rebuilds must use reload, not --fresh.

reload  builds the workbench, restarts 6677 on the durable runtime, and opens the launch URL without printing the token.

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
  const row = pluginRowState(dump);
  if (prepared.enabled) {
    assert.equal(row.present, true, 'plugin overlay was not composed into dump-config');
    assert.equal(row.disabled, false, 'plugin row is disabled while --plugin on');
  } else {
    assert.equal(row.disabled, true, 'plugin row is still active in a plugin-off dump');
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
        const booted = await bootHost(prepared, { signal });
        return { ...prepared, ...booted };
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

async function runReload(options) {
  assert.equal(Number(process.versions.node.split('.')[0]), NODE_MAJOR, `Use Node ${NODE_MAJOR}`);
  const runtime = await ensurePersistentRuntime({ dest: options.runtime ?? defaultRuntimeRoot() });
  const plugin = defaultPluginPath();
  const built = spawnSync(process.execPath, [join(plugin, 'build.mjs')], {
    cwd: plugin, stdio: 'inherit', env: process.env, timeout: 180000,
  });
  assert.equal(built.status, 0, 'plugin build.mjs failed');
  await stopOwned();
  const startId = randomBytes(16).toString('hex');
  const child = spawn(process.execPath, [
    join(repoRoot, 'scripts/dsh-dev/cli.mjs'), 'start',
    '--plugin', options.plugin || 'on',
    '--web-port', String(options.webPort || DEV_WEB_PORT),
    '--runtime', runtime,
  ], {
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
