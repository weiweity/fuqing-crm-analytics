import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer as createHttpServer } from 'node:http';
import { createServer as createNetServer } from 'node:net';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { access, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import {
  acquireSupervisorLock,
  readCurrent,
  runOwnedSupervisor,
  stopOwned,
  terminateChild,
  waitForOwnedCleanup,
  watchDetachedStart,
  watchOwnedStart,
} from './serve.mjs';

const self = fileURLToPath(import.meta.url);
const TOKEN = () => randomBytes(32).toString('hex');

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
}

async function listenHttp(handler) {
  const server = createHttpServer(handler);
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  return server;
}

async function reservePort() {
  const server = createNetServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

function controlAuth(req, token) {
  const actual = Buffer.from(req.headers.authorization ?? '');
  const expected = Buffer.from(`Bearer ${token}`);
  return actual.length === expected.length && actual.equals(expected);
}

function spawnFixture(env) {
  return spawn(process.execPath, [self, '--owned-supervisor-fixture'], {
    cwd: process.cwd(),
    env: { ...process.env, ...env },
    detached: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

async function runFixtureSupervisor() {
  const contextDir = process.env.DSH_DEV_FIXTURE_CONTEXT;
  const runtime = process.env.DSH_DEV_FIXTURE_RUNTIME;
  const startId = process.env.DSH_DEV_START_ID;
  const webPort = Number(process.env.DSH_DEV_FIXTURE_WEB_PORT);
  const listenDelayMs = Number(process.env.DSH_DEV_FIXTURE_LISTEN_DELAY_MS || 0);
  assert.ok(contextDir && runtime && startId && webPort > 0);
  await mkdir(runtime, { recursive: true, mode: 0o700 });
  const abort = new AbortController();
  process.once('SIGTERM', () => abort.abort());
  process.once('SIGINT', () => abort.abort());
  await runOwnedSupervisor({
    contextDir,
    startId,
    signal: abort.signal,
    boot: async ({ signal }) => {
      if (listenDelayMs) await delay(listenDelayMs, null, { signal });
      const origin = `http://127.0.0.1:${webPort}`;
      if (process.env.DSH_DEV_FIXTURE_SKIP_LAUNCH !== '1') {
        await writeFile(join(runtime, 'browser-private.json'), `${JSON.stringify({
          launchOrigin: origin,
          launchUrl: `${origin}/?token=synthetic-ready-token`,
        })}\n`, { mode: 0o600 });
      }
      if (process.env.DSH_DEV_FIXTURE_STUBBORN_WEB === '1') {
        const child = spawn(process.execPath, [self, '--stubborn-web'], {
          env: { ...process.env, DSH_DEV_FIXTURE_WEB_PORT: String(webPort) },
          stdio: ['ignore', 'pipe', 'pipe'],
        });
        const started = Date.now();
        while (Date.now() - started < 3000) {
          try {
            const response = await fetch(origin, { redirect: 'manual', signal: AbortSignal.timeout(300) });
            if (response.status === 401) break;
          } catch { /* still binding */ }
          await delay(50, null, { signal });
        }
        return {
          child, origin, webPort, host: '127.0.0.1', runtime,
          enabled: false, pluginPath: null, upstream: runtime,
        };
      }
      const web = createHttpServer((_req, res) => res.writeHead(401).end());
      await new Promise((resolve, reject) => {
        web.once('error', reject);
        web.listen(webPort, '127.0.0.1', resolve);
      });
      const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
      return {
        child,
        origin,
        webPort,
        host: '127.0.0.1',
        runtime,
        enabled: false,
        pluginPath: null,
        upstream: runtime,
        cleanup: () => new Promise(resolve => web.close(resolve)),
      };
    },
  });
}

if (process.argv.includes('--held-stdio')) {
  setTimeout(() => {}, 1500);
} else if (process.argv.includes('--racy-child')) {
  spawn(process.execPath, [self, '--held-stdio'], { stdio: 'inherit' });
  process.on('message', value => { if (value === 'exit-now') process.exit(7); });
  setTimeout(() => process.exit(8), 4000);
  process.send?.({ type: 'ready' });
} else if (process.argv.includes('--stubborn-web')) {
  process.on('SIGTERM', () => {});
  const port = Number(process.env.DSH_DEV_FIXTURE_WEB_PORT);
  const server = createHttpServer((req, res) => {
    if (req.method === 'POST' && req.url === '/fixture-stop'
      && req.headers.authorization === 'Bearer fixture-owned-cleanup') {
      res.writeHead(200).end();
      setTimeout(() => process.exit(0), 30);
      return;
    }
    res.writeHead(401).end();
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', resolve);
  });
  setTimeout(() => process.exit(0), 20000);
} else if (process.argv.includes('--owned-launcher-fixture')) {
  const origin = `http://127.0.0.1:${process.env.DSH_DEV_FIXTURE_WEB_PORT}`;
  const child = spawnFixture({
    DSH_DEV_FIXTURE_CONTEXT: process.env.DSH_DEV_FIXTURE_CONTEXT,
    DSH_DEV_FIXTURE_RUNTIME: process.env.DSH_DEV_FIXTURE_RUNTIME,
    DSH_DEV_START_ID: process.env.DSH_DEV_START_ID,
    DSH_DEV_FIXTURE_WEB_PORT: process.env.DSH_DEV_FIXTURE_WEB_PORT,
  });
  child.stdout?.unref();
  child.stderr?.unref();
  child.unref();
  await watchOwnedStart(child, {
    origin,
    runtime: process.env.DSH_DEV_FIXTURE_RUNTIME,
    currentPath: join(process.env.DSH_DEV_FIXTURE_CONTEXT, 'current.json'),
    startId: process.env.DSH_DEV_START_ID,
    timeoutMs: 5000,
  });
  process.stdout.write(`${JSON.stringify({ pid: child.pid })}\n`);
} else if (process.argv.includes('--owned-supervisor-fixture')) {
  await runFixtureSupervisor();
} else {
test('stopOwned does not return while the owned lock and current.json still exist', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-stop-'));
  const lockPath = join(root, 'supervisor.lock');
  const currentPath = join(root, 'current.json');
  await mkdir(lockPath, { mode: 0o700 });
  await writeFile(currentPath, '{}\n', { mode: 0o600 });
  const token = TOKEN();
  let cleaned;
  const done = new Promise(resolve => { cleaned = resolve; });
  const server = await listenHttp((req, res) => {
    if (req.method === 'POST' && req.url === '/stop' && controlAuth(req, token)) {
      res.writeHead(200).end();
      setTimeout(() => {
        void rm(currentPath, { force: true })
          .then(() => rm(lockPath, { recursive: true }))
          .then(() => { server.close(); cleaned(); });
      }, 400);
      return;
    }
    res.writeHead(404).end();
  });
  try {
    await stopOwned({
      control: { port: server.address().port, token },
    }, { currentPath, lockPath, timeoutMs: 2000 });
    assert.equal(await exists(lockPath), false);
    assert.equal(await exists(currentPath), false);
    await acquireSupervisorLock(lockPath);
    await rm(lockPath, { recursive: true });
  } finally {
    await done.catch(() => {});
    await rm(root, { recursive: true, force: true });
  }
});

test('stopOwned timeout leaves an unknown lock in place and does not signal stored PIDs', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-timeout-'));
  const lockPath = join(root, 'supervisor.lock');
  const currentPath = join(root, 'current.json');
  await mkdir(lockPath, { mode: 0o700 });
  await writeFile(currentPath, '{}\n', { mode: 0o600 });
  const token = TOKEN();
  const foreign = createNetServer();
  await new Promise(resolve => foreign.listen(0, '127.0.0.1', resolve));
  const server = await listenHttp((req, res) => {
    if (req.method === 'POST' && req.url === '/stop' && controlAuth(req, token)) {
      res.writeHead(200).end();
      return;
    }
    res.writeHead(404).end();
  });
  try {
    await assert.rejects(
      stopOwned({
        control: { port: server.address().port, token },
        childPid: process.pid,
        supervisorPid: process.pid,
        webPort: foreign.address().port,
      }, { currentPath, lockPath, timeoutMs: 250 }),
      /cleanup/,
    );
    assert.equal(await exists(lockPath), true);
    assert.equal(await exists(currentPath), true);
    process.kill(process.pid, 0);
    await new Promise((resolve, reject) => {
      const probe = createNetServer();
      probe.once('error', reject);
      probe.listen(foreign.address().port, '127.0.0.1', () => {
        probe.close(resolve);
      });
    }).then(
      () => assert.fail('foreign listener was released'),
      error => assert.equal(error.code, 'EADDRINUSE'),
    );
  } finally {
    await new Promise(resolve => server.close(resolve));
    await new Promise(resolve => foreign.close(resolve));
    await rm(root, { recursive: true, force: true });
  }
});

test('acquireSupervisorLock does not delete a pre-existing unknown lock', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-lock-'));
  const lockPath = join(root, 'supervisor.lock');
  await mkdir(lockPath, { mode: 0o700 });
  await writeFile(join(lockPath, 'owner'), 'foreign\n', { mode: 0o600 });
  try {
    await assert.rejects(acquireSupervisorLock(lockPath), /supervisor\.lock exists/);
    assert.equal(await exists(join(lockPath, 'owner')), true);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('waitForOwnedCleanup times out without removing files or killing PIDs', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-wait-'));
  const lockPath = join(root, 'supervisor.lock');
  const currentPath = join(root, 'current.json');
  await mkdir(lockPath, { mode: 0o700 });
  await writeFile(currentPath, '{}\n', { mode: 0o600 });
  try {
    await assert.rejects(waitForOwnedCleanup({
      currentPath, lockPath, control: { port: 1, token: TOKEN() },
    }, { timeoutMs: 200 }), /cleanup/);
    assert.equal(await exists(lockPath), true);
    assert.equal(await exists(currentPath), true);
    process.kill(process.pid, 0);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('detached start failure returns a redacted error instead of waiting out the ready timeout', async () => {
  const child = spawn(process.execPath, ['-e', `
    console.error('boot http://127.0.0.1:4328/?token=secret-token-value');
    console.error('DSH_DEV_LOCK supervisor.lock exists');
    process.exit(7);
  `], { stdio: ['ignore', 'pipe', 'pipe'] });
  const started = Date.now();
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-redact-'));
  try {
    await assert.rejects(
      watchDetachedStart(child, {
        origin: 'http://127.0.0.1:1',
        runtime: root,
        currentPath: join(root, 'current.json'),
        startId: 'none',
        timeoutMs: 90000,
      }),
      error => {
        assert.match(String(error.message), /exited before ready/);
        assert.match(String(error.message), /supervisor\.lock exists/);
        assert.equal(String(error.message).includes('secret-token-value'), false);
        assert.match(String(error.message), /\[REDACTED\]/);
        assert.equal(error.exitCode, 7);
        return true;
      },
    );
    assert.ok(Date.now() - started < 5000);
  } finally {
    if (child.exitCode === null && child.signalCode === null) {
      await terminateChild(child, new Promise(resolve => child.once('close', resolve)));
    }
    await rm(root, { recursive: true, force: true });
  }
});

test('foreign 401 is not owned start ready', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-foreign-'));
  const foreign = await listenHttp((_req, res) => res.writeHead(401).end());
  const origin = `http://127.0.0.1:${foreign.address().port}`;
  const idle = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const closed = new Promise(resolve => idle.once('close', resolve));
  try {
    await assert.rejects(
      watchOwnedStart(idle, {
        origin,
        runtime: root,
        currentPath: join(root, 'current.json'),
        startId: 'foreign-none',
        timeoutMs: 800,
      }),
      /did not become ready|owned ready|exited before ready/,
    );
  } finally {
    if (idle.exitCode === null && idle.signalCode === null) {
      await terminateChild(idle, closed);
    }
    await new Promise(resolve => foreign.close(resolve));
    await rm(root, { recursive: true, force: true });
  }
});

test('child exit is detected while inherited stdio stays open', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-exit-'));
  const early = spawn(process.execPath, ['--input-type=module', '-e', `
    import { spawn } from 'node:child_process';
    const g = spawn(process.execPath, ['-e', 'setTimeout(() => {}, 2500)'], { stdio: 'inherit' });
    console.error('FIXTURE_EXIT_7 grandchild=' + g.pid);
    process.exit(7);
  `], { stdio: ['ignore', 'pipe', 'pipe'] });
  let grandchild;
  early.stderr.on('data', chunk => {
    const match = String(chunk).match(/grandchild=(\d+)/);
    if (match) grandchild = Number(match[1]);
  });
  const began = Date.now();
  try {
    await assert.rejects(
      watchOwnedStart(early, {
        origin: 'http://127.0.0.1:1',
        runtime: root,
        currentPath: join(root, 'current.json'),
        startId: 'exit-none',
        timeoutMs: 900,
      }),
      error => {
        assert.equal(error.exitCode, 7);
        assert.match(String(error.message), /exited before ready/);
        assert.ok(Date.now() - began < 400);
        return true;
      },
    );
  } finally {
    if (Number.isInteger(grandchild)) {
      try { process.kill(grandchild, 'SIGKILL'); } catch { /* already gone */ }
    }
    await rm(root, { recursive: true, force: true });
  }
});

test('timeout cancels the owned start and leaves a foreign listener', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-cancel-'));
  const foreign = createNetServer();
  await new Promise(resolve => foreign.listen(0, '127.0.0.1', resolve));
  const latePort = await reservePort();
  const late = spawn(process.execPath, ['--input-type=module', '-e', `
    import { createServer } from 'node:http';
    const server = createServer((_req, res) => res.writeHead(401).end());
    setTimeout(() => server.listen(${latePort}, '127.0.0.1'), 1200);
    setTimeout(() => process.exit(0), 4000);
  `], { stdio: ['ignore', 'pipe', 'pipe'] });
  const closed = new Promise(resolve => late.once('close', resolve));
  try {
    await assert.rejects(
      watchOwnedStart(late, {
        origin: `http://127.0.0.1:${latePort}`,
        runtime: root,
        currentPath: join(root, 'current.json'),
        startId: 'late-none',
        timeoutMs: 400,
      }),
      /did not become ready/,
    );
    assert.equal(late.exitCode === null && late.signalCode === null, false);
    await assert.rejects(
      fetch(`http://127.0.0.1:${latePort}/`, { redirect: 'manual', signal: AbortSignal.timeout(500) }),
    );
    await new Promise((resolve, reject) => {
      const probe = createNetServer();
      probe.once('error', reject);
      probe.listen(foreign.address().port, '127.0.0.1', () => probe.close(resolve));
    }).then(
      () => assert.fail('foreign listener was released'),
      error => assert.equal(error.code, 'EADDRINUSE'),
    );
  } finally {
    if (late.exitCode === null && late.signalCode === null) {
      await terminateChild(late, closed);
    } else {
      await closed.catch(() => {});
    }
    await new Promise(resolve => foreign.close(resolve));
    await rm(root, { recursive: true, force: true });
  }
});

test('owned supervisor ready binds startId, control, 401 and launch file', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-owned-'));
  const contextDir = join(root, 'context');
  const runtime = join(root, 'runtime');
  const startId = TOKEN();
  const webPort = await reservePort();
  const origin = `http://127.0.0.1:${webPort}`;
  const child = spawnFixture({
    DSH_DEV_FIXTURE_CONTEXT: contextDir,
    DSH_DEV_FIXTURE_RUNTIME: runtime,
    DSH_DEV_START_ID: startId,
    DSH_DEV_FIXTURE_WEB_PORT: String(webPort),
  });
  const closed = new Promise(resolve => child.once('exit', resolve));
  try {
    await watchOwnedStart(child, {
      origin,
      runtime,
      currentPath: join(contextDir, 'current.json'),
      startId,
      timeoutMs: 4000,
    });
    const current = await readCurrent(join(contextDir, 'current.json'));
    assert.equal(current.startId, startId);
    assert.equal(current.supervisorPid, child.pid);
    assert.equal(current.webPort, webPort);
    const unauth = await fetch(`${origin}/`, { redirect: 'manual', signal: AbortSignal.timeout(1500) });
    assert.equal(unauth.status, 401);
    await stopOwned(undefined, {
      currentPath: join(contextDir, 'current.json'),
      lockPath: join(contextDir, 'supervisor.lock'),
      timeoutMs: 3000,
    });
    await Promise.race([closed, delay(3000)]);
    assert.equal(await exists(join(contextDir, 'supervisor.lock')), false);
    assert.equal(child.exitCode === null && child.signalCode === null, false);
  } finally {
    if (child.exitCode === null && child.signalCode === null) {
      await terminateChild(child, closed);
    }
    await rm(root, { recursive: true, force: true });
  }
});

test('stale current.json and delayed listen lose to cancel, not a late ready', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-race-'));
  const contextDir = join(root, 'context');
  const runtime = join(root, 'runtime');
  const startId = TOKEN();
  const webPort = await reservePort();
  const child = spawnFixture({
    DSH_DEV_FIXTURE_CONTEXT: contextDir,
    DSH_DEV_FIXTURE_RUNTIME: runtime,
    DSH_DEV_START_ID: startId,
    DSH_DEV_FIXTURE_WEB_PORT: String(webPort),
    DSH_DEV_FIXTURE_LISTEN_DELAY_MS: '1200',
  });
  const closed = new Promise(resolve => child.once('exit', resolve));
  try {
    await assert.rejects(watchOwnedStart(child, {
      origin: `http://127.0.0.1:${webPort}`,
      runtime,
      currentPath: join(contextDir, 'current.json'),
      startId,
      timeoutMs: 400,
    }), /did not become ready/);
    assert.equal(child.exitCode === null && child.signalCode === null, false);
    await delay(900);
    await assert.rejects(
      fetch(`http://127.0.0.1:${webPort}/`, { redirect: 'manual', signal: AbortSignal.timeout(500) }),
    );
  } finally {
    if (child.exitCode === null && child.signalCode === null) {
      await terminateChild(child, closed);
    } else {
      await closed.catch(() => {});
    }
    await rm(root, { recursive: true, force: true });
  }
});

test('launcher may exit after owned ready while the supervisor keeps serving', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-launcher-'));
  const contextDir = join(root, 'context');
  const runtime = join(root, 'runtime');
  const startId = TOKEN();
  const webPort = await reservePort();
  const origin = `http://127.0.0.1:${webPort}`;
  const launcher = spawn(process.execPath, [self, '--owned-launcher-fixture'], {
    cwd: process.cwd(),
    env: {
      ...process.env,
      DSH_DEV_FIXTURE_CONTEXT: contextDir,
      DSH_DEV_FIXTURE_RUNTIME: runtime,
      DSH_DEV_START_ID: startId,
      DSH_DEV_FIXTURE_WEB_PORT: String(webPort),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let stdout = '';
  launcher.stdout.on('data', chunk => { stdout += String(chunk); });
  const launcherClosed = new Promise(resolve => launcher.once('exit', resolve));
  try {
    const launcherCode = await Promise.race([
      launcherClosed,
      delay(6000).then(() => { throw new Error('launcher did not exit'); }),
    ]);
    assert.equal(launcherCode, 0);
    const reported = JSON.parse(stdout.trim());
    const unauth = await fetch(`${origin}/`, { redirect: 'manual', signal: AbortSignal.timeout(1500) });
    assert.equal(unauth.status, 401);
    process.kill(reported.pid, 0);
    await stopOwned(undefined, {
      currentPath: join(contextDir, 'current.json'),
      lockPath: join(contextDir, 'supervisor.lock'),
      timeoutMs: 3000,
    });
    await delay(200);
    assert.throws(() => process.kill(reported.pid, 0), { code: 'ESRCH' });
  } finally {
    if (launcher.exitCode === null && launcher.signalCode === null) {
      await terminateChild(launcher, launcherClosed);
    }
    await rm(root, { recursive: true, force: true });
  }
});

test('in-flight ready cannot win after child exit 7', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-inflight-'));
  const runtime = join(root, 'runtime');
  await mkdir(runtime, { recursive: true, mode: 0o700 });
  const child = spawn(process.execPath, [self, '--racy-child'], {
    stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
  });
  const directExit = new Promise(resolve => child.once('exit', (code, signal) => resolve({ code, signal })));
  const fullyClosed = new Promise(resolve => child.once('close', resolve));
  await new Promise(resolve => child.once('message', resolve));
  const web = await listenHttp((_req, res) => res.writeHead(401).end());
  const origin = `http://127.0.0.1:${web.address().port}`;
  const controlToken = TOKEN();
  const control = await listenHttp((req, res) => {
    if (req.headers.authorization !== `Bearer ${controlToken}`) { res.writeHead(401).end(); return; }
    child.send('exit-now');
    void directExit.then(() => res.writeHead(200).end());
  });
  await writeFile(join(root, 'current.json'), `${JSON.stringify({
    runtime, startId: 'race-generation', supervisorPid: child.pid,
    host: '127.0.0.1', webPort: web.address().port,
    control: { port: control.address().port, token: controlToken },
  })}\n`);
  await writeFile(join(runtime, 'browser-private.json'), `${JSON.stringify({
    launchOrigin: origin, launchUrl: `${origin}/?token=synthetic-ready-token`,
  })}\n`);
  try {
    await assert.rejects(
      watchOwnedStart(child, {
        origin, runtime, currentPath: join(root, 'current.json'),
        startId: 'race-generation', timeoutMs: 2000,
      }),
      error => {
        assert.equal(error.exitCode, 7);
        assert.match(String(error.message), /exited before ready/);
        assert.equal(String(error.message).includes('synthetic-ready-token'), false);
        return true;
      },
    );
    assert.equal(child.exitCode, 7);
  } finally {
    if (child.exitCode === null && child.signalCode === null) {
      await terminateChild(child, directExit);
    }
    await new Promise(resolve => control.close(resolve));
    await new Promise(resolve => web.close(resolve));
    await fullyClosed.catch(() => {});
    await rm(root, { recursive: true, force: true });
  }
});

test('nested cancel reaps stubborn web and this generation files', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-reload-nested-'));
  const contextDir = join(root, 'context');
  const runtime = join(root, 'runtime');
  const startId = TOKEN();
  const webPort = await reservePort();
  const origin = `http://127.0.0.1:${webPort}`;
  const foreign = createNetServer();
  await new Promise(resolve => foreign.listen(0, '127.0.0.1', resolve));
  const child = spawnFixture({
    DSH_DEV_FIXTURE_CONTEXT: contextDir,
    DSH_DEV_FIXTURE_RUNTIME: runtime,
    DSH_DEV_START_ID: startId,
    DSH_DEV_FIXTURE_WEB_PORT: String(webPort),
    DSH_DEV_FIXTURE_STUBBORN_WEB: '1',
    DSH_DEV_FIXTURE_SKIP_LAUNCH: '1',
  });
  const closed = new Promise(resolve => child.once('exit', resolve));
  try {
    await assert.rejects(watchOwnedStart(child, {
      origin, runtime, currentPath: join(contextDir, 'current.json'),
      lockPath: join(contextDir, 'supervisor.lock'),
      startId, timeoutMs: 600,
    }), /did not become ready|cleanup incomplete/);
    await assert.rejects(
      fetch(origin, { redirect: 'manual', signal: AbortSignal.timeout(800) }),
    );
    assert.equal(await exists(join(contextDir, 'current.json')), false);
    assert.equal(await exists(join(contextDir, 'supervisor.lock')), false);
    assert.equal(child.exitCode === null && child.signalCode === null, false);
    await new Promise((resolve, reject) => {
      const probe = createNetServer();
      probe.once('error', reject);
      probe.listen(foreign.address().port, '127.0.0.1', () => probe.close(resolve));
    }).then(
      () => assert.fail('foreign listener was released'),
      error => assert.equal(error.code, 'EADDRINUSE'),
    );
  } finally {
    await fetch(`${origin}/fixture-stop`, {
      method: 'POST',
      headers: { authorization: 'Bearer fixture-owned-cleanup' },
      signal: AbortSignal.timeout(1000),
    }).catch(() => {});
    if (child.exitCode === null && child.signalCode === null) {
      await terminateChild(child, closed);
    } else {
      await closed.catch(() => {});
    }
    await new Promise(resolve => foreign.close(resolve));
    await rm(root, { recursive: true, force: true });
  }
});
}
