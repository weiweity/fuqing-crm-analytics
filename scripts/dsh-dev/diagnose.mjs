/** Read-only start/auth/stale-build/port-owner diagnostics. Never binds, never signals PIDs. */
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { lstat, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import {
  BRAND_DIGESTS, COMPETITION_VITE_PORT, COMPETITION_WEB_PORT, FOREIGN_PORTS, HOST,
  NODE_MAJOR, PINNED_SHA, PORT_RANGE, PORTS, USER_DEMO_PORTS,
} from './constants.mjs';
import { defaultPluginPath, repoRoot } from './paths.mjs';
import { redactLaunchLog } from './launch-url.mjs';
import { readCurrent } from './serve.mjs';

const LFS_PREFIX = 'version https://git-lfs.github.com/spec/v1';

export const AUTH_MECHANISM = Object.freeze({
  unauthenticated_get: 'GET / without the launch cookie must be 401',
  launch_exchange: 'one-time launch token query parameter on the printed URL sets an HttpOnly cookie then 303 to /',
  authenticated_get: 'GET / with that cookie returns 200 and __DSH_BOOT__',
  never_print_token: true,
  never_disable_auth: true,
});

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function git(cwd, args) {
  const result = spawnSync('git', ['-C', cwd, ...args], { encoding: 'utf8', timeout: 15000, maxBuffer: 1024 * 1024 });
  if (result.error || result.status !== 0) return { ok: false, text: (result.error?.message ?? result.stderr ?? '').trim() };
  return { ok: true, text: result.stdout.trim() };
}

function lsofListen(port) {
  const result = spawnSync('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN'], {
    encoding: 'utf8', timeout: 8000, maxBuffer: 256 * 1024,
  });
  if (result.status !== 0 && !result.stdout) return [];
  const rows = [];
  for (const line of result.stdout.split('\n').slice(1)) {
    if (!line.trim()) continue;
    const parts = line.trim().split(/\s+/);
    const pid = Number(parts[1]);
    if (!Number.isInteger(pid) || pid <= 0) continue;
    rows.push({ command: parts[0], pid, name: parts.slice(-1)[0] ?? '' });
  }
  return rows;
}

function processCwd(pid) {
  const result = spawnSync('lsof', ['-a', '-p', String(pid), '-d', 'cwd', '-Fn'], {
    encoding: 'utf8', timeout: 8000, maxBuffer: 64 * 1024,
  });
  if (result.status !== 0) return null;
  for (const line of result.stdout.split('\n')) {
    if (line.startsWith('n')) return line.slice(1);
  }
  return null;
}

function processArgv(pid) {
  const result = spawnSync('ps', ['-p', String(pid), '-o', 'command='], {
    encoding: 'utf8', timeout: 8000, maxBuffer: 64 * 1024,
  });
  if (result.status !== 0) return null;
  const text = result.stdout.trim().slice(0, 400);
  return text ? redactLaunchLog(text) : null;
}

export async function inspectListener(port) {
  const listeners = lsofListen(port);
  if (listeners.length === 0) {
    return { port, host: HOST, state: 'free', listeners: [] };
  }
  return {
    port,
    host: HOST,
    state: 'listening',
    listeners: listeners.map(row => ({
      pid: row.pid,
      command: row.command,
      name: row.name,
      cwd: processCwd(row.pid),
      argv: processArgv(row.pid),
    })),
  };
}

function classifyPort(snapshot, current) {
  const pids = snapshot.listeners.map(row => row.pid);
  const ownedPids = current
    ? [current.childPid, current.supervisorPid].filter(pid => Number.isInteger(pid) && pid > 0)
    : [];
  const owned = pids.some(pid => ownedPids.includes(pid));
  if (FOREIGN_PORTS.includes(snapshot.port)) {
    return { owner: 'foreign', reuse: 'refuse', stop: 'refuse' };
  }
  if (snapshot.port === COMPETITION_VITE_PORT) {
    return { owner: snapshot.state === 'free' ? 'reserved_free' : 'foreign_or_other', reuse: 'refuse_as_dsh_web', stop: 'refuse' };
  }
  if (USER_DEMO_PORTS.includes(snapshot.port) && snapshot.state === 'listening' && !owned) {
    return { owner: 'user_demo', reuse: 'refuse', stop: 'refuse' };
  }
  if (owned) return { owner: 'this_worktree', reuse: 'already_owned', stop: 'only_via_cli_stop' };
  if (snapshot.port === COMPETITION_WEB_PORT) {
    return { owner: snapshot.state === 'free' ? 'reserved_free' : 'other', reuse: snapshot.state === 'free' ? 'allowed' : 'refuse', stop: 'refuse' };
  }
  if (PORT_RANGE.includes(snapshot.port)) {
    return {
      owner: snapshot.state === 'free' ? 'legacy_free' : 'other',
      reuse: snapshot.state === 'free' ? 'allowed_if_not_user_demo' : 'refuse',
      stop: 'refuse',
    };
  }
  return { owner: 'unknown', reuse: 'refuse', stop: 'refuse' };
}

async function inspectFile(path, digest, { allowLfs = true } = {}) {
  try {
    const bytes = await readFile(path);
    const textStart = bytes.subarray(0, Math.min(bytes.length, LFS_PREFIX.length)).toString('utf8');
    if (textStart === LFS_PREFIX) {
      return { path, status: allowLfs ? 'lfs_pointer' : 'unexpected_lfs', bytes: bytes.length, digest: null, expected: digest };
    }
    const actual = sha256(bytes);
    return { path, status: actual === digest ? 'ok' : 'hash_mismatch', bytes: bytes.length, digest: actual, expected: digest };
  } catch (error) {
    return { path, status: 'missing', error: error.code ?? error.message, expected: digest };
  }
}

async function newestMtime(path) {
  try {
    return (await lstat(path)).mtimeMs;
  } catch {
    return null;
  }
}

function findNode24() {
  const running = process.versions.node;
  const runningMajor = Number(running.split('.')[0]);
  const candidates = [
    process.env.DSH_DEV_NODE,
    runningMajor === NODE_MAJOR ? process.execPath : null,
    '/Users/hutou/homebrew/opt/node@24/bin/node',
    '/opt/homebrew/opt/node@24/bin/node',
  ].filter(value => typeof value === 'string' && value.length > 0);
  for (const candidate of candidates) {
    if (!existsSync(candidate)) continue;
    const probe = spawnSync(candidate, ['-p', 'process.versions.node'], { encoding: 'utf8', timeout: 5000 });
    if (probe.status === 0 && Number(probe.stdout.trim().split('.')[0]) === NODE_MAJOR) {
      return { path: candidate, version: probe.stdout.trim() };
    }
  }
  return null;
}

async function inspectUpstream(explicit) {
  let upstream = null;
  const candidates = [
    explicit,
    process.env.DSH_DEV_UPSTREAM,
    join(repoRoot, '.context/dsh-b0/upstream'),
    resolve(repoRoot, '../../fuqing-crm-analytics/.context/dsh-b0/upstream'),
  ].filter(value => typeof value === 'string' && value.length > 0);
  const tried = [];
  for (const candidate of candidates) {
    const path = resolve(candidate);
    tried.push(path);
    if (existsSync(join(path, 'apps/cli/lib/bin.js'))) {
      upstream = path;
      break;
    }
  }
  if (!upstream) {
    return { status: 'missing', tried };
  }
  const pinPath = join(repoRoot, 'dsh-plugins/analytics-workbench/toolchain.json');
  const pin = JSON.parse(await readFile(pinPath, 'utf8'));
  const head = git(upstream, ['rev-parse', 'HEAD']);
  const dirty = git(upstream, ['status', '--porcelain', '--untracked-files=no']);
  let lockDigest = null;
  try { lockDigest = sha256(await readFile(join(upstream, 'pnpm-lock.yaml'))); } catch { lockDigest = null; }
  const cliBin = join(upstream, 'apps/cli/lib/bin.js');
  const webDist = join(upstream, 'apps/web/dist/index.html');
  const webSrc = join(upstream, 'apps/web/src');
  const cliSrc = join(upstream, 'apps/cli/src');
  const cliMtime = await newestMtime(cliBin);
  const distMtime = await newestMtime(webDist);
  const webSrcMtime = await newestMtime(webSrc);
  const cliSrcMtime = await newestMtime(cliSrc);
  const stale = [];
  if (!existsSync(cliBin)) stale.push('cli_bin_missing');
  if (!existsSync(webDist)) stale.push('web_dist_missing');
  if (distMtime && webSrcMtime && webSrcMtime > distMtime + 1000) stale.push('web_src_newer_than_dist');
  if (cliMtime && cliSrcMtime && cliSrcMtime > cliMtime + 1000) stale.push('cli_src_newer_than_bin');
  if (head.ok && head.text !== pin.upstream_sha) stale.push('upstream_sha_drift');
  if (lockDigest && lockDigest !== pin.upstream_lock_sha256) stale.push('lockfile_sha_drift');
  return {
    status: stale.length ? 'stale_or_drift' : 'ready',
    path: upstream,
    pin_sha: pin.upstream_sha,
    actual_sha: head.ok ? head.text : null,
    lock_ok: lockDigest === pin.upstream_lock_sha256,
    dirty: dirty.ok ? dirty.text : dirty.text,
    cli_bin: existsSync(cliBin),
    web_dist: existsSync(webDist),
    stale_reasons: stale,
  };
}

async function inspectPlugin() {
  const plugin = defaultPluginPath();
  const lib = join(plugin, 'lib/index.js');
  const client = join(plugin, 'lib/client.js');
  const src = join(plugin, 'src/index.ts');
  const srcMtime = await newestMtime(src);
  const libMtime = await newestMtime(lib);
  const reasons = [];
  if (!existsSync(lib)) reasons.push('lib_index_missing');
  if (!existsSync(client)) reasons.push('lib_client_missing');
  if (srcMtime && libMtime && srcMtime > libMtime + 1000) reasons.push('src_newer_than_lib');
  return {
    path: plugin,
    lib: existsSync(lib),
    client: existsSync(client),
    status: reasons.length ? 'stale_or_missing' : 'present',
    reasons,
  };
}

async function inspectAuth(current) {
  const live = {
    status: 'NOT_RUN',
    reason: 'no owned supervisor in this worktree; refusing to probe 127.0.0.1:4327 or any foreign listener',
  };
  if (!current || !Number.isInteger(current.webPort) || current.host !== HOST) {
    return { mechanism: AUTH_MECHANISM, live };
  }
  if (FOREIGN_PORTS.includes(current.webPort)) {
    return { mechanism: AUTH_MECHANISM, live: { status: 'NOT_RUN', reason: 'current.json points at a foreign port; refusing probe' } };
  }
  const ownedPids = [current.childPid, current.supervisorPid].filter(pid => Number.isInteger(pid) && pid > 0);
  const snapshot = await inspectListener(current.webPort);
  const ours = snapshot.listeners.some(row => ownedPids.includes(row.pid));
  if (!ours) {
    return { mechanism: AUTH_MECHANISM, live };
  }
  try {
    const origin = `http://${current.host}:${current.webPort}`;
    const unauth = await fetch(`${origin}/`, { redirect: 'manual', signal: AbortSignal.timeout(1500) });
    return {
      mechanism: AUTH_MECHANISM,
      live: {
        status: unauth.status === 401 ? 'PASS' : 'FAIL',
        reason: `owned origin unauthenticated GET / → ${unauth.status}`,
        unauth_status: unauth.status,
        origin: origin,
      },
    };
  } catch (error) {
    return {
      mechanism: AUTH_MECHANISM,
      live: {
        status: 'FAIL',
        reason: `owned origin probe failed: ${error instanceof Error ? error.message : String(error)}`,
      },
    };
  }
}

export async function diagnose(options = {}, readState = readCurrent) {
  const current = await readState();
  const node24 = findNode24();
  const runningMajor = Number(process.versions.node.split('.')[0]);
  const upstream = await inspectUpstream(options.upstream);
  const plugin = await inspectPlugin();
  const brand = {
    logo: await inspectFile(join(repoRoot, 'frontend-vue3/src/assets/brand/shine-mage.png'), BRAND_DIGESTS.logoPng),
    mark: await inspectFile(join(repoRoot, 'frontend-vue3/public/shine-mage-mark.svg'), BRAND_DIGESTS.markSvg),
    outfit: await inspectFile(join(repoRoot, 'frontend-vue3/src/assets/fonts/Outfit-Variable.ttf'), BRAND_DIGESTS.outfitTtf),
  };
  const portsToScan = [...new Set([
    ...FOREIGN_PORTS, ...PORT_RANGE, COMPETITION_WEB_PORT, COMPETITION_VITE_PORT,
  ])];
  const ports = [];
  for (const port of portsToScan) {
    const snapshot = await inspectListener(port);
    ports.push({ ...snapshot, classification: classifyPort(snapshot, current) });
  }
  const auth = await inspectAuth(current);
  const recommendations = [];
  if (runningMajor !== NODE_MAJOR) {
    recommendations.push(`PATH node is v${process.versions.node}; start/check require Node ${NODE_MAJOR}. Use ${node24?.path ?? 'node@24'} explicitly.`);
  }
  const demo = ports.find(row => row.port === PORTS.web);
  if (demo?.state === 'listening' && demo.classification.owner === 'user_demo') {
    recommendations.push(`127.0.0.1:${PORTS.web} is the user DSH demo (pid ${(demo.listeners[0] ?? {}).pid}); do not stop or reuse. Independent DSH must use --web-port ${COMPETITION_WEB_PORT}.`);
  }
  const reserved = ports.find(row => row.port === COMPETITION_WEB_PORT);
  if (reserved?.state === 'free') {
    recommendations.push(`Competition DSH port ${COMPETITION_WEB_PORT} is free. This batch does not start it by default.`);
  }
  if (brand.logo.status === 'lfs_pointer') {
    recommendations.push('Worktree shine-mage.png is a Git LFS pointer; do not smudge/copy automatically. Brand shell still references /b0/brand/logo.png.');
  }
  if (plugin.status !== 'present') {
    recommendations.push('Plugin lib/ is missing or stale in this worktree. --plugin on needs a built lib/index.js; do not pnpm install here.');
  }
  if (upstream.status !== 'ready') {
    recommendations.push('Pinned upstream is missing or stale relative to toolchain.json; pass --upstream /absolute/pinned/dsh. Do not copy node_modules.');
  }
  recommendations.push('Auth stays on: unauthenticated / is 401. Never print launch tokens. probe.mjs only against an owned current.json.');
  return {
    kind: 'DSH_DEV_DIAGNOSE',
    at: new Date().toISOString(),
    repo: repoRoot,
    current: current ? {
      runtime: current.runtime,
      host: current.host,
      webPort: current.webPort,
      childPid: current.childPid ?? null,
      pluginEnabled: current.pluginEnabled ?? false,
    } : null,
    node: {
      running: process.version,
      running_major: runningMajor,
      required_major: NODE_MAJOR,
      recommended: node24,
      start_ready: runningMajor === NODE_MAJOR,
    },
    pin: { upstream_sha: PINNED_SHA },
    upstream,
    plugin,
    brand,
    auth,
    ports,
    actions_not_taken: [
      'did_not_signal_any_pid',
      'did_not_bind_ports',
      'did_not_http_probe_4327',
      'did_not_http_probe_8000_or_5173',
      'did_not_start_dsh',
    ],
    recommendations,
  };
}

export function printDiagnose(report) {
  console.log(`DSH_DEV_DIAGNOSE node=${report.node.running} start_ready=${report.node.start_ready}`);
  console.log(`DSH_DEV_UPSTREAM ${report.upstream.status} ${report.upstream.path ?? '(none)'}`);
  console.log(`DSH_DEV_PLUGIN ${report.plugin.status}`);
  console.log(`DSH_DEV_BRAND logo=${report.brand.logo.status} mark=${report.brand.mark.status} outfit=${report.brand.outfit.status}`);
  console.log(`DSH_DEV_AUTH live=${report.auth.live.status}`);
  for (const row of report.ports) {
    const pid = row.listeners[0]?.pid ?? '-';
    console.log(`DSH_DEV_PORT ${row.port} ${row.state} owner=${row.classification.owner} reuse=${row.classification.reuse} pid=${pid}`);
  }
  for (const line of report.recommendations) console.log(`DSH_DEV_HINT ${line}`);
  console.log('DSH_DEV_JSON_BEGIN');
  console.log(JSON.stringify(report, null, 2));
  console.log('DSH_DEV_JSON_END');
}

export { COMPETITION_WEB_PORT, COMPETITION_VITE_PORT };
