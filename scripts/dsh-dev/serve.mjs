/** Full DSH web supervisor. Owns only this runtime and 4325-4329. */
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, writeFile, readFile, access } from 'node:fs/promises';
import { dirname, isAbsolute, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { API_KEY_ENV, HOST, NODE_MAJOR, PINNED_SHA, PORTS } from './constants.mjs';
import { findReadyUrl, originOf, redactLaunchLog } from './launch-url.mjs';
import { assertNoB0Disables, assertPluginRoot, buildPluginDisable, buildPluginOverlay, pluginEnabled } from './overlay.mjs';
import { readToolchain, verifyUpstream } from './pin.mjs';
import { assertOwnedHost, assertOwnedPort, assertFree } from './ports.mjs';
import { assertCli, contextRoot, currentPath, defaultPluginPath, defaultRuntimeRoot, ensureDir, repoRoot, resolveUpstream } from './paths.mjs';

function writeJson(path, value) {
  return writeFile(path, JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
}

export function parseServeArgs(argv) {
  const options = {
    plugin: 'off',
    host: HOST,
    webPort: PORTS.web,
    detach: false,
    fresh: false,
    extraPatch: [],
  };
  const args = [...argv];
  while (args.length) {
    const flag = args.shift();
    const valueFlags = ['--upstream', '--plugin', '--plugin-path', '--extra-patch', '--runtime', '--web-port', '--host'];
    if (valueFlags.includes(flag)) assert.ok(args[0] && !args[0].startsWith('--'), `missing value for ${flag}`);
    if (flag === '--upstream') options.upstream = args.shift();
    else if (flag === '--plugin') options.plugin = args.shift();
    else if (flag === '--plugin-path') options.pluginPath = args.shift();
    else if (flag === '--extra-patch') options.extraPatch.push(args.shift());
    else if (flag === '--runtime') options.runtime = args.shift();
    else if (flag === '--web-port') options.webPort = Number(args.shift());
    else if (flag === '--host') options.host = args.shift();
    else if (flag === '--detach') options.detach = true;
    else if (flag === '--fresh') options.fresh = true;
    else throw new Error(`unknown flag ${flag}`);
  }
  assert.ok(options.plugin === 'on' || options.plugin === 'off', 'Usage: --plugin on|off');
  assertOwnedHost(options.host);
  assertOwnedPort(options.webPort);
  for (const patch of options.extraPatch) {
    assert.ok(patch && patch.startsWith('/'), '--extra-patch must be an absolute path');
  }
  return options;
}

export function isolatedEnv(runtime, home) {
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
  return {
    ...kept,
    ...competition,
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
  if (enabled) {
    pluginPath = await assertPluginRoot(options.pluginPath ?? defaultPluginPath());
    const overlay = buildPluginOverlay(pluginPath);
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
    pin, upstream, verified, cli, enabled, pluginPath, overlayPath, patches,
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

/**
 * Install the local workbench into this runtime's web profile.
 * `--plugin off` must not call this; off only disables the already-installed row.
 */
export function installProfilePlugin(prepared) {
  assert.equal(prepared.enabled, true, 'installProfilePlugin is plugin-on only');
  const args = profilePluginAddArgs(prepared.cli, prepared.pluginPath).slice(1);
  const result = spawnSync(process.execPath, [prepared.cli, ...args], {
    cwd: prepared.workspace,
    env: pluginInstallEnv(prepared.runtime, prepared.home),
    encoding: 'utf8',
    timeout: 180000,
    maxBuffer: 8 * 1024 * 1024,
  });
  const detail = (result.stderr || result.stdout || result.error?.message || '').slice(-2000);
  assert.ok(!result.error && result.status === 0, `dsh plugin add failed: ${detail}`);
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
    env: isolatedEnv(prepared.runtime, prepared.home),
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
    env: isolatedEnv(prepared.runtime, prepared.home),
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

export async function writeCurrent(state) {
  await writeJson(currentPath(), {
    runtime: state.runtime,
    control: state.control,
    supervisorPid: process.pid,
    childPid: state.child?.pid ?? null,
    webPort: state.webPort,
    host: state.host,
    pinned: PINNED_SHA,
    pluginEnabled: state.enabled,
    plugin: state.pluginPath,
    upstream: state.upstream,
    ownedPorts: [PORTS.kernel, PORTS.bridge, PORTS.web, PORTS.gateway, PORTS.mock],
    boundPorts: [state.webPort],
    foreignPortsUntouched: [8000, 5173, 4315, 4316, 4317, 4318, 4319],
  });
}

export async function readCurrent() {
  try {
    return JSON.parse(await readFile(currentPath(), 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

export async function terminateChild(child, exited) {
  if (child.exitCode !== null || child.signalCode !== null) return;
  child.kill('SIGTERM');
  let timer;
  const drained = await Promise.race([
    exited.then(() => true),
    new Promise(resolve => { timer = setTimeout(() => resolve(false), 3000); }),
  ]);
  clearTimeout(timer);
  if (!drained) { child.kill('SIGKILL'); await exited; }
}

export async function stopOwned(current = undefined) {
  current ??= await readCurrent();
  if (!current) return { stopped: false };
  const control = current.control;
  assert.ok(control && Number.isInteger(control.port) && control.port > 0 && control.port <= 65535
    && typeof control.token === 'string' && control.token.length >= 32,
    'No verified supervisor control endpoint; refusing to signal stored PIDs');
  const response = await fetch(`http://127.0.0.1:${control.port}/stop`, {
    method: 'POST', headers: { authorization: `Bearer ${control.token}` },
    redirect: 'error', signal: AbortSignal.timeout(10000),
  });
  assert.equal(response.status, 200, 'Supervisor did not acknowledge stop');
  return { stopped: true };
}

export { currentPath, repoRoot };
