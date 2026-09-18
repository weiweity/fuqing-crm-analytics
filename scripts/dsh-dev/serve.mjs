/** Full DSH web supervisor. Owns only this runtime and 4325-4329. */
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, writeFile, readFile, access, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { dirname, isAbsolute, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { API_KEY_ENV, COMPETITION_WEB_PORT, FOREIGN_PORTS, HOST, NODE_MAJOR, PINNED_SHA, PORTS, PORT_RANGE } from './constants.mjs';
import { findReadyUrl, originOf, redactLaunchLog } from './launch-url.mjs';
import { assertNoB0Disables, assertPluginRoot, buildPluginDisable, buildPluginOverlay, buildShineBrandDisable, buildShineWaterfallDisable, buildShineCrowdActionDisable, buildShineQueryDisable, buildShineBoardDisable, buildShineFunnelDisable, pluginEnabled } from './overlay.mjs';
import { readToolchain, verifyUpstream } from './pin.mjs';
import { assertOwnedHost, assertOwnedPort, assertFree } from './ports.mjs';
import { assertCli, contextRoot, currentPath, defaultPluginPath, defaultShineBrandPath, defaultShineWaterfallPath, defaultShineCrowdActionPath, defaultShineQueryPath, defaultShineBoardPath, defaultShineFunnelPath, defaultRuntimeRoot, ensureDir, repoRoot, resolveUpstream } from './paths.mjs';

function writeJson(path, value) {
  return writeFile(path, JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
}

export function parseServeArgs(argv) {
  const options = {
    plugin: 'off',
    shineBrand: 'on',
    shineWaterfall: 'on',
    shineCrowdAction: 'on',
    shineQuery: 'on',
    shineBoard: 'on',
    shineFunnel: 'on',
    host: HOST,
    webPort: PORTS.web,
    detach: false,
    fresh: false,
    extraPatch: [],
  };
  const args = [...argv];
  while (args.length) {
    const flag = args.shift();
    const valueFlags = [
      '--upstream', '--plugin', '--plugin-path', '--shine-brand', '--shine-brand-path',
      '--waterfall', '--waterfall-path', '--crowd-action', '--crowd-action-path',
      '--query', '--query-path', '--board', '--board-path', '--funnel', '--funnel-path',
      '--extra-patch', '--runtime', '--web-port', '--host', '--page-http', '--page-http-port',
    ];
    if (valueFlags.includes(flag)) assert.ok(args[0] && !args[0].startsWith('--'), `missing value for ${flag}`);
    if (flag === '--upstream') options.upstream = args.shift();
    else if (flag === '--plugin') options.plugin = args.shift();
    else if (flag === '--plugin-path') options.pluginPath = args.shift();
    else if (flag === '--shine-brand') options.shineBrand = args.shift();
    else if (flag === '--shine-brand-path') options.shineBrandPath = args.shift();
    else if (flag === '--waterfall') options.shineWaterfall = args.shift();
    else if (flag === '--waterfall-path') options.shineWaterfallPath = args.shift();
    else if (flag === '--crowd-action') options.shineCrowdAction = args.shift();
    else if (flag === '--crowd-action-path') options.shineCrowdActionPath = args.shift();
    else if (flag === '--query') options.shineQuery = args.shift();
    else if (flag === '--query-path') options.shineQueryPath = args.shift();
    else if (flag === '--board') options.shineBoard = args.shift();
    else if (flag === '--board-path') options.shineBoardPath = args.shift();
    else if (flag === '--funnel') options.shineFunnel = args.shift();
    else if (flag === '--funnel-path') options.shineFunnelPath = args.shift();
    else if (flag === '--extra-patch') options.extraPatch.push(args.shift());
    else if (flag === '--runtime') options.runtime = args.shift();
    else if (flag === '--web-port') options.webPort = Number(args.shift());
    else if (flag === '--host') options.host = args.shift();
    else if (flag === '--page-http') options.pageHttp = args.shift();
    else if (flag === '--page-http-port') options.pageHttpPort = Number(args.shift());
    else if (flag === '--detach') options.detach = true;
    else if (flag === '--fresh') options.fresh = true;
    else throw new Error(`unknown flag ${flag}`);
  }
  assert.ok(options.plugin === 'on' || options.plugin === 'off', 'Usage: --plugin on|off');
  pluginEnabled(options.shineBrand);
  pluginEnabled(options.shineWaterfall);
  pluginEnabled(options.shineCrowdAction);
  pluginEnabled(options.shineQuery);
  pluginEnabled(options.shineBoard);
  pluginEnabled(options.shineFunnel);
  if (options.pluginPath) assert.ok(options.pluginPath.startsWith('/'), '--plugin-path must be an absolute path');
  if (options.shineBrandPath) {
    assert.ok(options.shineBrandPath.startsWith('/'), '--shine-brand-path must be an absolute path');
    assert.equal(pluginEnabled(options.shineBrand), true, '--shine-brand-path requires --shine-brand on');
  }
  if (options.shineWaterfallPath) {
    assert.ok(options.shineWaterfallPath.startsWith('/'), '--waterfall-path must be an absolute path');
    assert.equal(pluginEnabled(options.shineWaterfall), true, '--waterfall-path requires --waterfall on');
  }
  if (options.shineCrowdActionPath) {
    assert.ok(options.shineCrowdActionPath.startsWith('/'), '--crowd-action-path must be an absolute path');
    assert.equal(pluginEnabled(options.shineCrowdAction), true, '--crowd-action-path requires --crowd-action on');
  }
  if (options.shineQueryPath) {
    assert.ok(options.shineQueryPath.startsWith('/'), '--query-path must be an absolute path');
    assert.equal(pluginEnabled(options.shineQuery), true, '--query-path requires --query on');
  }
  if (options.shineBoardPath) {
    assert.ok(options.shineBoardPath.startsWith('/'), '--board-path must be an absolute path');
    assert.equal(pluginEnabled(options.shineBoard), true, '--board-path requires --board on');
  }
  if (options.shineFunnelPath) {
    assert.ok(options.shineFunnelPath.startsWith('/'), '--funnel-path must be an absolute path');
    assert.equal(pluginEnabled(options.shineFunnel), true, '--funnel-path requires --funnel on');
  }
  assertOwnedHost(options.host);
  assertOwnedPort(options.webPort);
  if (options.pageHttp !== undefined) {
    assert.ok(options.pageHttp === 'on' || options.pageHttp === 'off', 'Usage: --page-http on|off');
  }
  if (options.pageHttpPort !== undefined) {
    assert.ok(Number.isInteger(options.pageHttpPort) && options.pageHttpPort > 0
      && options.pageHttpPort <= 65535 && options.pageHttpPort !== 6677
      && !PORT_RANGE.includes(options.pageHttpPort) && options.pageHttpPort !== COMPETITION_WEB_PORT,
      '--page-http-port must be 1-65535 and never 6677 or an owned web port');
  }
  for (const patch of options.extraPatch) {
    assert.ok(patch && patch.startsWith('/'), '--extra-patch must be an absolute path');
  }
  return options;
}

/** Repo shine-brand path, or null when `--shine-brand off`. Never dirname(--plugin-path). */
export function resolveShineBrandPath(options) {
  if (!pluginEnabled(options.plugin)) return null;
  if (!pluginEnabled(options.shineBrand ?? 'on')) return null;
  return options.shineBrandPath ?? defaultShineBrandPath();
}

export function resolveShineWaterfallPath(options) {
  if (!pluginEnabled(options.plugin)) return null;
  if (!pluginEnabled(options.shineWaterfall ?? 'on')) return null;
  return options.shineWaterfallPath ?? defaultShineWaterfallPath();
}

export function resolveShineCrowdActionPath(options) {
  if (!pluginEnabled(options.plugin)) return null;
  if (!pluginEnabled(options.shineCrowdAction ?? 'on')) return null;
  return options.shineCrowdActionPath ?? defaultShineCrowdActionPath();
}

export function resolveShineQueryPath(options) {
  if (!pluginEnabled(options.plugin)) return null;
  if (!pluginEnabled(options.shineQuery ?? 'on')) return null;
  return options.shineQueryPath ?? defaultShineQueryPath();
}

export function resolveShineBoardPath(options) {
  if (!pluginEnabled(options.plugin)) return null;
  if (!pluginEnabled(options.shineBoard ?? 'on')) return null;
  return options.shineBoardPath ?? defaultShineBoardPath();
}

export function resolveShineFunnelPath(options) {
  if (!pluginEnabled(options.plugin)) return null;
  if (!pluginEnabled(options.shineFunnel ?? 'on')) return null;
  return options.shineFunnelPath ?? defaultShineFunnelPath();
}

export function profileInstallPaths(prepared) {
  const paths = [];
  if (prepared.shineBrandPath) paths.push(prepared.shineBrandPath);
  if (prepared.shineWaterfallPath) paths.push(prepared.shineWaterfallPath);
  if (prepared.shineCrowdActionPath) paths.push(prepared.shineCrowdActionPath);
  if (prepared.shineQueryPath) paths.push(prepared.shineQueryPath);
  if (prepared.shineBoardPath) paths.push(prepared.shineBoardPath);
  if (prepared.shineFunnelPath) paths.push(prepared.shineFunnelPath);
  if (prepared.pluginPath) paths.push(prepared.pluginPath);
  return paths;
}

export function isolatedEnv(runtime, home, extra = {}) {
  const kept = Object.fromEntries(Object.entries(process.env).filter(([key]) => (
    key === 'HOME' || key === 'LANG' || key === 'TZ'
  ) && !API_KEY_ENV.includes(key)));
  const competition = {};
  const caFile = process.env.NODE_EXTRA_CA_CERTS
    ?? (existsSync('/etc/ssl/cert.pem') ? '/etc/ssl/cert.pem' : undefined);
  if (caFile) {
    assert.ok(isAbsolute(caFile), 'NODE_EXTRA_CA_CERTS must be an absolute public CA bundle path');
    competition.NODE_EXTRA_CA_CERTS = caFile;
  }
  const httpBase = process.env.COMPETITION_HTTP_BASE;
  const httpToken = process.env.COMPETITION_HTTP_TOKEN;
  if (httpBase && httpToken) {
    if (/:(4327|8000|5173)(\/|$)/.test(httpBase)) {
      throw new Error('COMPETITION_HTTP_BASE must not target 4327/8000/5173');
    }
    competition.COMPETITION_HTTP_BASE = httpBase;
    competition.COMPETITION_HTTP_TOKEN = httpToken;
  }
  // Isolated page documents/result HTTP: forwarded only when explicitly
  // configured; a base containing the live web port refuses to boot.
  const pageBase = process.env.PAGE_DOCUMENTS_HTTP_BASE;
  if (pageBase) {
    if (pageBase.includes(':6677')) {
      throw new Error('PAGE_DOCUMENTS_HTTP_BASE must not target the live web port 6677');
    }
    const pageToken = process.env.PAGE_DOCUMENTS_HTTP_TOKEN;
    assert.ok(pageToken && pageToken.length >= 32,
      'PAGE_DOCUMENTS_HTTP_TOKEN must be at least 32 chars when PAGE_DOCUMENTS_HTTP_BASE is set');
    competition.PAGE_DOCUMENTS_HTTP_BASE = pageBase;
    competition.PAGE_DOCUMENTS_HTTP_TOKEN = pageToken;
    const resultBase = process.env.PAGE_RESULT_HTTP_BASE;
    if (resultBase) {
      if (resultBase.includes(':6677')) {
        throw new Error('PAGE_RESULT_HTTP_BASE must not target the live web port 6677');
      }
      competition.PAGE_RESULT_HTTP_BASE = resultBase;
      competition.PAGE_RESULT_HTTP_TOKEN = process.env.PAGE_RESULT_HTTP_TOKEN ?? pageToken;
    }
  }
  return {
    ...kept,
    ...competition,
    ...(extra.SHINE_WATERFALL ? { SHINE_WATERFALL: extra.SHINE_WATERFALL } : {}),
    ...(extra.SHINE_CROWD_ACTION ? { SHINE_CROWD_ACTION: extra.SHINE_CROWD_ACTION } : {}),
    ...(extra.SHINE_QUERY ? { SHINE_QUERY: extra.SHINE_QUERY } : {}),
    ...(extra.SHINE_BOARD ? { SHINE_BOARD: extra.SHINE_BOARD } : {}),
    ...(extra.SHINE_FUNNEL ? { SHINE_FUNNEL: extra.SHINE_FUNNEL } : {}),
    PATH: `${dirname(process.execPath)}:/usr/bin:/bin`,
    LANG: kept.LANG ?? 'en_US.UTF-8',
    TZ: kept.TZ ?? 'Asia/Shanghai',
    DSH_HOME: home,
    DSH_AGENTS_HOME: join(home, 'agents'),
    DSH_TELEMETRY_DISABLED: '1',
    DSH_ANALYTICS_UI_ONLY: '1',
    TMPDIR: join(runtime, 'tmp'),
  };
}

export async function prepareRuntime(options) {
  assert.equal(Number(process.versions.node.split('.')[0]), NODE_MAJOR, `Use Node ${NODE_MAJOR}`);
  const pin = await readToolchain(repoRoot);
  const upstream = resolveUpstream(options.upstream);
  const verified = await verifyUpstream(upstream, pin);
  const cli = await assertCli(upstream);
  const enabled = pluginEnabled(options.plugin);
  let pluginPath = null;
  let overlayPath = null;
  await ensureDir(contextRoot());
  const runtime = options.runtime
    ?? (options.fresh ? await mkdtemp(join(contextRoot(), 'runtime-')) : defaultRuntimeRoot());
  assert.ok(runtime.startsWith('/'), 'runtime must be absolute');
  await ensureDir(runtime);
  const home = join(runtime, 'harness');
  const workspace = join(runtime, 'workspace');
  for (const path of [home, workspace, join(runtime, 'tmp'), join(home, 'agents')]) {
    await mkdir(path, { recursive: true, mode: 0o700 });
  }
  const patches = [];
  let shineBrandPath = null;
  let shineWaterfallPath = null;
  let shineCrowdActionPath = null;
  let shineQueryPath = null;
  let shineBoardPath = null;
  let shineFunnelPath = null;
  if (enabled) {
    pluginPath = await assertPluginRoot(options.pluginPath ?? defaultPluginPath());
    const brandCandidate = resolveShineBrandPath({ ...options, plugin: 'on' });
    if (brandCandidate) shineBrandPath = await assertPluginRoot(brandCandidate);
    const waterfallCandidate = resolveShineWaterfallPath({ ...options, plugin: 'on' });
    if (waterfallCandidate) shineWaterfallPath = await assertPluginRoot(waterfallCandidate);
    const crowdCandidate = resolveShineCrowdActionPath({ ...options, plugin: 'on' });
    if (crowdCandidate) shineCrowdActionPath = await assertPluginRoot(crowdCandidate);
    const queryCandidate = resolveShineQueryPath({ ...options, plugin: 'on' });
    if (queryCandidate) shineQueryPath = await assertPluginRoot(queryCandidate);
    const boardCandidate = resolveShineBoardPath({ ...options, plugin: 'on' });
    if (boardCandidate) shineBoardPath = await assertPluginRoot(boardCandidate);
    const funnelCandidate = resolveShineFunnelPath({ ...options, plugin: 'on' });
    if (funnelCandidate) shineFunnelPath = await assertPluginRoot(funnelCandidate);
    let overlay = buildPluginOverlay(pluginPath);
    if (!shineBrandPath) overlay = [...overlay, ...buildShineBrandDisable()];
    if (!shineWaterfallPath) overlay = [...overlay, ...buildShineWaterfallDisable()];
    if (!shineCrowdActionPath) overlay = [...overlay, ...buildShineCrowdActionDisable()];
    if (!shineQueryPath) overlay = [...overlay, ...buildShineQueryDisable()];
    if (!shineBoardPath) overlay = [...overlay, ...buildShineBoardDisable()];
    if (!shineFunnelPath) overlay = [...overlay, ...buildShineFunnelDisable()];
    overlayPath = join(runtime, 'plugin.patch.yml');
    await writeJson(overlayPath, overlay);
    patches.push(overlayPath);
  } else {
    overlayPath = join(runtime, 'plugin-off.patch.yml');
    await writeJson(overlayPath, buildPluginDisable());
    patches.push(overlayPath);
  }
  for (const extra of options.extraPatch) {
    await access(extra);
    patches.push(extra);
  }
  if (patches.length) {
    const composed = [];
    for (const path of patches) {
      composed.push(JSON.parse(await readFile(path, 'utf8')));
    }
    assertNoB0Disables(composed);
  }
  return {
    pin, upstream, verified, cli, enabled, pluginPath, shineBrandPath, shineWaterfallPath, shineCrowdActionPath, shineQueryPath, shineBoardPath, shineFunnelPath, overlayPath, patches,
    runtime, home, workspace, host: options.host, webPort: options.webPort,
  };
}

/** `dsh plugin --profile web add <absolute plugin path>`. */
export function profilePluginAddArgs(cli, pluginPath) {
  assert.ok(cli && cli.startsWith('/'), 'cli path must be absolute');
  assert.ok(pluginPath && pluginPath.startsWith('/'), 'plugin path must be absolute');
  return [cli, 'plugin', '--profile', 'web', 'add', pluginPath];
}

function pluginInstallEnv(runtime, home) {
  const env = isolatedEnv(runtime, home);
  const parts = [dirname(process.execPath), process.env.PATH, env.PATH].filter(Boolean);
  return { ...env, PATH: parts.join(':') };
}

function runtimeEnv(prepared) {
  return isolatedEnv(prepared.runtime, prepared.home, {
    SHINE_WATERFALL: prepared.shineWaterfallPath ? 'on' : 'off',
    SHINE_CROWD_ACTION: prepared.shineCrowdActionPath ? 'on' : 'off',
    SHINE_QUERY: prepared.shineQueryPath ? 'on' : 'off',
    SHINE_BOARD: prepared.shineBoardPath ? 'on' : 'off',
    SHINE_FUNNEL: prepared.shineFunnelPath ? 'on' : 'off',
  });
}

/**
 * Install local packages into this runtime's web profile.
 * `--plugin off` must not call this; off only disables already-installed rows.
 * shine-brand is omitted when `--shine-brand off`.
 */
export function installProfilePlugin(prepared) {
  assert.equal(prepared.enabled, true, 'installProfilePlugin is plugin-on only');
  for (const pluginPath of profileInstallPaths(prepared)) {
    const args = profilePluginAddArgs(prepared.cli, pluginPath).slice(1);
    const result = spawnSync(process.execPath, [prepared.cli, ...args], {
      cwd: prepared.workspace,
      env: pluginInstallEnv(prepared.runtime, prepared.home),
      encoding: 'utf8',
      timeout: 180000,
      maxBuffer: 8 * 1024 * 1024,
    });
    const detail = (result.stderr || result.stdout || result.error?.message || '').slice(-2000);
    assert.ok(!result.error && result.status === 0, `dsh plugin add failed (${pluginPath}): ${detail}`);
  }
}

export function dumpConfigArgs(prepared) {
  const args = [prepared.cli, '--profile', 'web'];
  for (const patch of prepared.patches) args.push('--patch', patch);
  args.push(prepared.patches.length ? '--dump-config' : '--dump-default-config');
  return args;
}

export async function dumpConfig(prepared) {
  const { spawnSync } = await import('node:child_process');
  const args = dumpConfigArgs(prepared).slice(1);
  const result = spawnSync(process.execPath, [prepared.cli, ...args], {
    cwd: prepared.workspace,
    env: runtimeEnv(prepared),
    encoding: 'utf8',
    timeout: 60000,
    maxBuffer: 8 * 1024 * 1024,
  });
  assert.ok(!result.error && result.status === 0, `dump-config failed: ${result.error?.message ?? result.stderr ?? result.stdout}`);
  return result.stdout;
}

export async function bootHost(prepared, { signal, timeoutMs = 45000 } = {}) {
  signal?.throwIfAborted();
  await assertFree(prepared.webPort, prepared.host);
  const origin = originOf(prepared.host, prepared.webPort);
  const args = [prepared.cli, '--profile', 'web'];
  for (const patch of prepared.patches) args.push('--patch', patch);
  args.push('--host', prepared.host, '--port', String(prepared.webPort), '--no-open');
  const child = spawn(process.execPath, args, {
    cwd: prepared.workspace,
    env: runtimeEnv(prepared),
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const abort = () => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM'); };
  signal?.addEventListener('abort', abort, { once: true });
  let completeLog = '';
  let launchUrl;
  let capturing = true;
  let overflow = false;
  const ingest = chunk => {
    if (!capturing || overflow) return;
    const incoming = String(chunk);
    const limit = 2 * 1024 * 1024;
    overflow = completeLog.length + incoming.length > limit;
    completeLog = (completeLog + incoming).slice(0, limit);
    if (overflow) { child.kill('SIGTERM'); return; }
    launchUrl = findReadyUrl(completeLog, origin);
  };
  child.stdout.on('data', ingest);
  child.stderr.on('data', ingest);
  const childExit = new Promise(ok => {
    child.once('close', (code, signal) => ok({ code, signal }));
    child.once('error', ok);
  });
  const deadline = Date.now() + timeoutMs;
  try {
    while (!launchUrl && child.exitCode === null && child.signalCode === null && Date.now() < deadline && !signal?.aborted && !overflow) {
      await delay(100);
    }
    await writeFile(join(prepared.runtime, 'boot.log'), redactLaunchLog(completeLog), { mode: 0o600 });
    assert.ok(!overflow, 'DSH startup log exceeds bound');
    assert.ok(launchUrl, `DSH startup did not produce a ready URL within ${timeoutMs}ms`);
    await writeJson(join(prepared.runtime, 'browser-private.json'), { launchOrigin: origin, launchUrl });
    signal?.throwIfAborted();
    capturing = false; // Continue draining pipes without retaining unbounded runtime logs.
    completeLog = '';
    return { child, childExit, launchUrl, origin };
  } catch (error) {
    await terminateChild(child, childExit);
    throw error;
  } finally {
    signal?.removeEventListener('abort', abort);
  }
}

export async function writeCurrent(state, path = currentPath()) {
  await writeJson(path, {
    runtime: state.runtime,
    control: state.control,
    supervisorPid: process.pid,
    childPid: state.child?.pid ?? null,
    webPort: state.webPort,
    host: state.host,
    pinned: PINNED_SHA,
    pluginEnabled: state.enabled,
    plugin: state.pluginPath,
    shineBrand: state.shineBrandPath ?? null,
    shineWaterfall: state.shineWaterfallPath ?? null,
    shineCrowdAction: state.shineCrowdActionPath ?? null,
    shineQuery: state.shineQueryPath ?? null,
    shineBoard: state.shineBoardPath ?? null,
    shineFunnel: state.shineFunnelPath ?? null,
    pageHttpBase: state.pageHttpBase ?? null,
    upstream: state.upstream,
    startId: state.startId ?? null,
    ownedPorts: [PORTS.kernel, PORTS.bridge, PORTS.web, PORTS.gateway, PORTS.mock],
    boundPorts: [state.webPort],
    foreignPortsUntouched: [...FOREIGN_PORTS], // 15173 is COMPETITION_VITE_PORT: not bound, classified separately
  });
}

export async function readCurrent(path = currentPath()) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function onceExit(child) {
  if (!child) return Promise.resolve({ code: null, signal: null });
  if (child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve({ code: child.exitCode, signal: child.signalCode });
  }
  return new Promise(resolve => child.once('exit', (code, signal) => resolve({ code, signal })));
}

const CHILD_TERM_MS = 3000;
const CHILD_KILL_WAIT_MS = 1000;
const SUPERVISOR_CLEANUP_MS = 2000;
export const CANCEL_BUDGET_MS = CHILD_TERM_MS + CHILD_KILL_WAIT_MS + SUPERVISOR_CLEANUP_MS + 9000;

export async function terminateChild(child, exited, { termMs = CHILD_TERM_MS, killWaitMs = CHILD_KILL_WAIT_MS } = {}) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  const exitDone = onceExit(child);
  const provided = exited ? Promise.resolve(exited).then(() => true) : null;
  child.kill('SIGTERM');
  let timer;
  const drained = await Promise.race([
    exitDone.then(() => true),
    ...(provided ? [provided] : []),
    new Promise(resolve => { timer = setTimeout(() => resolve(false), termMs); }),
  ]);
  clearTimeout(timer);
  if (!drained && child.exitCode === null && child.signalCode === null) {
    child.kill('SIGKILL');
    await Promise.race([exitDone, delay(killWaitMs)]);
  }
}

export function supervisorLockPath(root = contextRoot()) {
  return join(root, 'supervisor.lock');
}

export async function acquireSupervisorLock(lockPath) {
  try {
    await mkdir(lockPath, { mode: 0o700 });
  } catch (error) {
    if (error.code === 'EEXIST') {
      throw new Error('DSH_DEV_LOCK supervisor.lock exists; refusing to delete or signal unknown owners');
    }
    throw error;
  }
  return lockPath;
}

export async function waitForOwnedCleanup({ currentPath: statePath, lockPath } = {}, { timeoutMs = 15000 } = {}) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const currentGone = !statePath || !existsSync(statePath);
    const lockGone = !lockPath || !existsSync(lockPath);
    if (currentGone && lockGone) return;
    await delay(50);
  }
  throw new Error('DSH_DEV_STOP owned supervisor did not finish cleanup');
}

export async function runOwnedSupervisor({
  contextDir = contextRoot(),
  startId = process.env.DSH_DEV_START_ID,
  signal,
  boot,
} = {}) {
  assert.equal(typeof boot, 'function', 'runOwnedSupervisor requires a boot function');
  const lock = supervisorLockPath(contextDir);
  const statePath = join(contextDir, 'current.json');
  const generation = startId || null;
  await mkdir(contextDir, { recursive: true, mode: 0o700 });
  await acquireSupervisorLock(lock);
  let session, server, askedToStop = false;
  try {
    session = await boot({ signal });
    assert.ok(session?.child, 'boot must return a child process');
    session.childExit ??= onceExit(session.child);
    const token = randomBytes(32).toString('hex');
    let finish;
    const requested = new Promise(resolve => { finish = resolve; });
    server = createServer((req, res) => {
      const actual = Buffer.from(req.headers.authorization ?? '');
      const expected = Buffer.from(`Bearer ${token}`);
      if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) {
        res.writeHead(401).end();
        return;
      }
      if (req.method === 'GET' && req.url === '/status') { res.writeHead(200).end(); return; }
      if (req.method !== 'POST' || req.url !== '/stop') { res.writeHead(404).end(); return; }
      askedToStop = true;
      void terminateChild(session.child, session.childExit).then(() => {
        res.writeHead(200).end(); finish();
      }).catch(() => { res.writeHead(500).end(); finish(); });
    });
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', resolve);
    });
    await writeCurrent({
      ...session,
      child: session.child,
      control: { port: server.address().port, token },
      startId: generation,
    }, statePath);
    console.log(`DSH_DEV_READY ${session.origin}/ (launch token not printed)`);
    if (session.runtime) console.log(`DSH_DEV_RUNTIME ${session.runtime}`);
    const aborted = new Promise(resolve => {
      if (signal?.aborted) resolve();
      else signal?.addEventListener('abort', resolve, { once: true });
    });
    const outcome = await Promise.race([
      requested,
      Promise.resolve(session.childExit).then(exit => ({ exit })),
      aborted.then(() => ({ aborted: true })),
    ]);
    if (outcome?.exit && !askedToStop && !signal?.aborted) process.exitCode = outcome.exit.code ?? 1;
  } finally {
    if (session?.child) await terminateChild(session.child, session.childExit);
    if (typeof session?.cleanup === 'function') await session.cleanup();
    if (server) await new Promise(resolve => server.close(resolve));
    const current = await readCurrent(statePath);
    if (!current || !generation || current.startId === generation) {
      await rm(statePath, { force: true });
    }
    await rm(lock, { recursive: true, force: true });
  }
}

function fetchSignal(timeoutMs, signal) {
  const timeout = AbortSignal.timeout(timeoutMs);
  return signal ? AbortSignal.any([timeout, signal]) : timeout;
}

function childGone(child) {
  return !child || child.exitCode !== null || child.signalCode !== null;
}

async function originResponding(origin, signal) {
  if (!origin) return false;
  try {
    await fetch(`${new URL(origin).origin}/`, {
      redirect: 'manual',
      signal: fetchSignal(500, signal),
    });
    return true;
  } catch {
    return false;
  }
}

export async function isOwnedReady({
  origin, runtime, currentPath: statePath, startId, supervisorPid, signal, stillLive,
} = {}) {
  const live = () => {
    if (signal?.aborted) return false;
    if (typeof stillLive === 'function' && !stillLive()) return false;
    return true;
  };
  if (!live()) return false;
  const current = await readCurrent(statePath);
  if (!live() || !current) return false;
  if (startId && current.startId !== startId) return false;
  if (Number.isInteger(supervisorPid) && current.supervisorPid !== supervisorPid) return false;
  if (runtime && current.runtime && current.runtime !== runtime) return false;
  const originUrl = new URL(origin);
  if (Number(current.webPort) !== Number(originUrl.port)) return false;
  const control = current.control;
  if (!control || !Number.isInteger(control.port) || typeof control.token !== 'string' || control.token.length < 32) {
    return false;
  }
  try {
    const status = await fetch(`http://127.0.0.1:${control.port}/status`, {
      headers: { authorization: `Bearer ${control.token}` },
      redirect: 'error',
      signal: fetchSignal(1500, signal),
    });
    if (!live() || status.status !== 200) return false;
    const unauth = await fetch(`${originUrl.origin}/`, {
      redirect: 'manual',
      signal: fetchSignal(2000, signal),
    });
    if (!live() || unauth.status !== 401) return false;
  } catch {
    return false;
  }
  if (!runtime || !live()) return false;
  try {
    const priv = JSON.parse(await readFile(join(runtime, 'browser-private.json'), 'utf8'));
    if (!live()) return false;
    if (typeof priv.launchUrl !== 'string' || typeof priv.launchOrigin !== 'string') return false;
    if (priv.launchOrigin !== originUrl.origin) return false;
    const launch = new URL(priv.launchUrl);
    if (launch.origin !== originUrl.origin || !launch.searchParams.get('token')) return false;
  } catch {
    return false;
  }
  return live();
}

export async function cancelOwnedStart(child, {
  currentPath: statePath,
  lockPath,
  origin,
  startId,
  timeoutMs = CANCEL_BUDGET_MS,
} = {}) {
  const started = Date.now();
  const remaining = () => Math.max(50, timeoutMs - (Date.now() - started));
  const inferredLock = lockPath ?? (statePath ? join(dirname(statePath), 'supervisor.lock') : undefined);
  const current = statePath ? await readCurrent(statePath) : null;
  const ours = Boolean(current
    && (!startId || current.startId === startId)
    && (!child?.pid || current.supervisorPid === child.pid));
  const ownedOrigin = ours && origin && Number(current.webPort) === Number(new URL(origin).port);

  let stoppedViaControl = false;
  if (ours) {
    try {
      await stopOwned(current, {
        currentPath: statePath,
        lockPath: inferredLock,
        timeoutMs: remaining(),
      });
      stoppedViaControl = true;
    } catch { /* supervisor-owned stop failed; signal and verify below */ }
  }

  if (!childGone(child)) {
    child.kill('SIGTERM');
    await Promise.race([
      onceExit(child),
      delay(stoppedViaControl ? SUPERVISOR_CLEANUP_MS : remaining()),
    ]);
    if (!childGone(child) && !stoppedViaControl) {
      child.kill('SIGKILL');
      await Promise.race([onceExit(child), delay(CHILD_KILL_WAIT_MS)]);
    } else if (!childGone(child)) {
      await Promise.race([onceExit(child), delay(SUPERVISOR_CLEANUP_MS)]);
    }
  }

  const webGone = !ownedOrigin || !await originResponding(origin);
  const currentGone = !statePath || !existsSync(statePath);
  const lockGone = !inferredLock || !existsSync(inferredLock);
  const supervisorGone = childGone(child);
  if (supervisorGone && webGone && currentGone && lockGone) {
    return { cancelled: true, cleaned: true, stoppedViaControl };
  }
  const error = new Error(
    `DSH_DEV_CANCEL cleanup incomplete supervisorGone=${supervisorGone} webGone=${webGone} currentGone=${currentGone} lockGone=${lockGone}`,
  );
  error.incomplete = { supervisorGone, webGone, currentGone, lockGone };
  error.cleaned = false;
  throw error;
}

function collectSpawnLog(child) {
  const logs = [];
  const ingest = chunk => {
    logs.push(String(chunk));
    const joined = logs.join('');
    if (joined.length > 65536) {
      logs.length = 0;
      logs.push(joined.slice(-65536));
    }
  };
  child.stdout?.on('data', ingest);
  child.stderr?.on('data', ingest);
  const stdioDone = Promise.all(['stdout', 'stderr'].map(name => {
    const stream = child[name];
    if (!stream || stream.readableEnded) return Promise.resolve();
    return new Promise(resolve => stream.once('end', resolve));
  }));
  return {
    detail() { return redactLaunchLog(logs.join('')).slice(-2000); },
    async flush() { await Promise.race([stdioDone, delay(200)]); },
  };
}

export async function watchOwnedStart(child, {
  origin,
  runtime,
  currentPath: statePath = currentPath(),
  lockPath,
  startId,
  timeoutMs = 90000,
} = {}) {
  assert.ok(child && Number.isInteger(child.pid) && child.pid > 0, 'DSH_DEV_START missing pid');
  assert.ok(typeof origin === 'string' && origin.startsWith('http://127.0.0.1'), 'origin must be loopback');
  const log = collectSpawnLog(child);
  const abort = new AbortController();
  const deadline = Date.now() + timeoutMs;
  let settled = false;
  let terminal = null;
  let finish;
  const finished = new Promise((resolve, reject) => {
    finish = (error, value) => {
      if (settled) return;
      settled = true;
      abort.abort();
      if (error) reject(error);
      else resolve(value);
    };
  });
  const markTerminal = (kind, payload = {}) => {
    if (settled || terminal) return false;
    terminal = { kind, ...payload };
    abort.abort();
    return true;
  };
  const canSucceed = () => !settled && !terminal && !childGone(child) && Date.now() < deadline;
  const failExited = async (code, signal) => {
    await log.flush();
    const error = new Error(
      `DSH_DEV_START pid=${child.pid} exited before ready code=${code ?? 'unknown'} ${log.detail()}`.trim(),
    );
    error.exitCode = Number.isInteger(code) ? code : 1;
    if (signal) error.signal = signal;
    finish(error);
  };
  if (childGone(child)) {
    markTerminal('exit', { code: child.exitCode, signal: child.signalCode });
    await failExited(child.exitCode, child.signalCode);
    return finished;
  }
  const onExit = (code, signal) => {
    if (!markTerminal('exit', { code, signal })) return;
    void failExited(code, signal);
  };
  const onError = error => {
    if (!markTerminal('error', { code: 1, signal: error })) return;
    void failExited(1, error);
  };
  child.once('exit', onExit);
  child.once('error', onError);
  void (async () => {
    while (canSucceed()) {
      try {
        const ready = await isOwnedReady({
          origin, runtime, currentPath: statePath, startId, supervisorPid: child.pid,
          signal: abort.signal, stillLive: canSucceed,
        });
        if (ready && canSucceed()) {
          finish(null, { ready: true, pid: child.pid });
          return;
        }
      } catch { /* current/control not owned yet */ }
      if (!canSucceed()) break;
      try { await delay(50, null, { signal: abort.signal }); }
      catch { break; }
    }
    if (settled) return;
    markTerminal('timeout');
    await log.flush();
    const error = new Error(`DSH_DEV_RELOAD ${origin}/ did not become ready: ${log.detail()}`.trim());
    try {
      await cancelOwnedStart(child, {
        currentPath: statePath, lockPath, origin, startId, timeoutMs: CANCEL_BUDGET_MS,
      });
    } catch (cancelError) {
      finish(cancelError);
      return;
    }
    finish(error);
  })();
  try {
    return await finished;
  } finally {
    child.removeListener('exit', onExit);
    child.removeListener('error', onError);
    abort.abort();
  }
}

export async function watchDetachedStart(child, options) {
  return watchOwnedStart(child, options);
}

export async function stopOwned(current = undefined, options = {}) {
  const fromDisk = current === undefined;
  const statePath = options.currentPath ?? currentPath();
  current ??= await readCurrent(statePath);
  if (!current) return { stopped: false };
  const control = current.control;
  assert.ok(control && Number.isInteger(control.port) && control.port > 0 && control.port <= 65535
    && typeof control.token === 'string' && control.token.length >= 32,
    'No verified supervisor control endpoint; refusing to signal stored PIDs');
  const response = await fetch(`http://127.0.0.1:${control.port}/stop`, {
    method: 'POST', headers: { authorization: `Bearer ${control.token}` },
    redirect: 'error',
    signal: AbortSignal.timeout(Math.max(1000, Math.min(10000, options.timeoutMs ?? 10000))),
  });
  assert.equal(response.status, 200, 'Supervisor did not acknowledge stop');
  const trackedCurrent = options.currentPath ?? (fromDisk ? currentPath() : undefined);
  const lockPath = options.lockPath ?? (fromDisk ? supervisorLockPath() : undefined);
  if (trackedCurrent || lockPath) {
    await waitForOwnedCleanup(
      { currentPath: trackedCurrent, lockPath },
      { timeoutMs: options.timeoutMs ?? 15000 },
    );
  }
  return { stopped: true };
}

export { currentPath, repoRoot };
