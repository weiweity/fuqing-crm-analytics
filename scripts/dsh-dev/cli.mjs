#!/usr/bin/env node
/** Local DSH-base entry. Does not manage 8000/5173/4315-4319. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { COMPETITION_VITE_PORT, COMPETITION_WEB_PORT, NATIVE_WEB_IDS, PLUGIN_UI_ID } from './constants.mjs';
import { repoRoot, contextRoot, currentPath } from './paths.mjs';
import { createServer } from 'node:http';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { bootHost, dumpConfig, parseServeArgs, prepareRuntime, readCurrent, stopOwned, writeCurrent, terminateChild } from './serve.mjs';
import { diagnose, printDiagnose } from './diagnose.mjs';

const USAGE = `Usage: node scripts/dsh-dev/cli.mjs <check|dump-config|start|stop|status|diagnose>
  --upstream /absolute/pinned/dsh
  --plugin on|off
  --plugin-path /absolute/plugin
  --extra-patch /absolute/overlay.yml
  --runtime /absolute/runtime
  --web-port 4327|14327
  --host 127.0.0.1
  --detach          start only
  --fresh           new runtime dir under .context/dsh-dev/

Node 24 required for check/start. diagnose is read-only: it never binds ports or signals PIDs.
User demo 127.0.0.1:4327 / 8000 / 5173 must not be stopped or reused.
Independent DSH: --web-port ${COMPETITION_WEB_PORT}. Vite ${COMPETITION_VITE_PORT} is reserved and not bound here.
Launch tokens are never printed. Unauthenticated GET / must stay 401.`;

function parseArgv(argv) {
  const [command, ...rest] = argv;
  assert.ok(['check', 'dump-config', 'start', 'stop', 'status', 'diagnose'].includes(command), USAGE);
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
  const dump = await dumpConfig(prepared);
  await writeFile(join(prepared.runtime, 'dump-config.txt'), dump, { mode: 0o600 });
  assertDumpContainsNative(dump);
  if (prepared.enabled) {
    assert.ok(dump.includes(PLUGIN_UI_ID), 'plugin overlay was not composed into dump-config');
  } else {
    assert.equal(dump.includes(PLUGIN_UI_ID), false, 'plugin overlay leaked into plugin-off dump');
  }
  console.log(`DSH_DEV_CHECK pinned=${prepared.verified.upstream_sha} plugin=${prepared.enabled ? 'on' : 'off'}`);
  console.log(`DSH_DEV_DUMP ${join(prepared.runtime, 'dump-config.txt')}`);
  return prepared;
}

async function runStart(options) {
  await mkdir(contextRoot(), { recursive: true, mode: 0o700 });
  const lock = join(contextRoot(), 'supervisor.lock');
  await mkdir(lock, { mode: 0o700 }); // Exclusive; stale lock requires inspection, never PID killing.
  const abort = new AbortController();
  const onSignal = () => abort.abort();
  process.once('SIGTERM', onSignal);
  process.once('SIGINT', onSignal);
  let booted, server;
  try {
    const prepared = await prepareRuntime(options);
    booted = await bootHost(prepared, { signal: abort.signal });
    const token = randomBytes(32).toString('hex');
    let finish;
    let askedToStop = false;
    const requested = new Promise(resolve => { finish = resolve; });
    server = createServer((req, res) => {
      const actual = Buffer.from(req.headers.authorization ?? '');
      const expected = Buffer.from(`Bearer ${token}`);
      if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) { res.writeHead(401).end(); return; }
      if (req.method === 'GET' && req.url === '/status') { res.writeHead(200).end(); return; }
      if (req.method !== 'POST' || req.url !== '/stop') { res.writeHead(404).end(); return; }
      askedToStop = true;
      void terminateChild(booted.child, booted.childExit).then(() => {
        res.writeHead(200).end(); finish();
      }).catch(() => { res.writeHead(500).end(); finish(); });
    });
    await new Promise((resolve, reject) => {
      server.once('error', reject); server.listen(0, '127.0.0.1', resolve);
    });
    await writeCurrent({ ...prepared, child: booted.child, control: { port: server.address().port, token } });
    console.log(`DSH_DEV_READY ${booted.origin}/ (launch token not printed)`);
    console.log(`DSH_DEV_RUNTIME ${prepared.runtime}`);
    const aborted = new Promise(resolve => {
      if (abort.signal.aborted) resolve();
      else abort.signal.addEventListener('abort', resolve, { once: true });
    });
    const outcome = await Promise.race([requested, booted.childExit.then(exit => ({ exit })), aborted]);
    if (outcome?.exit && !askedToStop && !abort.signal.aborted) process.exitCode = outcome.exit.code ?? 1;
  } finally {
    if (booted) await terminateChild(booted.child, booted.childExit);
    if (server) await new Promise(resolve => server.close(resolve));
    await rm(currentPath(), { force: true });
    await rm(lock, { recursive: true });
    process.removeListener('SIGTERM', onSignal);
    process.removeListener('SIGINT', onSignal);
  }
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
} else if (command === 'stop') {
  const result = await stopOwned();
  console.log(result.stopped ? 'DSH_DEV_STOPPED acknowledged by owned supervisor' : 'DSH_DEV_STATUS stopped');
} else if (command === 'status') await runStatus();
