#!/usr/bin/env node
/**
 * Synthetic-only outer Seatbelt probe. Does not launch DSH or touch a real DB.
 * Run with the exact Node intended for DSH, e.g. node@24/bin/node this-file.mjs.
 * Creates a retained, mode-0700 fixture below .context/dsh-b0 for auditability.
 * It never probes the user's private files, existing 8000/5173 services, or any
 * live Internet host. A TEST-NET endpoint is used for the external-denial check.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import http from 'node:http';
import { homedir } from 'node:os';
import { spawn } from 'node:child_process';
import { Worker } from 'node:worker_threads';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { runtimeCodeRoot } from './runtime-paths.mjs';

const sourceFile = fs.realpathSync(fileURLToPath(import.meta.url));
const scriptDir = path.dirname(sourceFile);
const repository = path.resolve(scriptDir, '../..');
const deniedCodes = new Set(['EPERM', 'EACCES']);
const host = '127.0.0.1';
const dshPort = 4317;
const mockPort = 4319;

function listen(server, port) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.off('error', reject);
      resolve(server.address());
    });
  });
}

function close(server) {
  return new Promise((resolve) => server.close(resolve));
}

function connectResult(address, port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: address, port });
    const finish = (result) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(result);
    };
    socket.once('connect', () => finish({ connected: true }));
    socket.once('error', (error) => finish({ code: error.code }));
    socket.setTimeout(1500, () => finish({ code: 'TIMEOUT' }));
  });
}

async function childProbe(fixture) {
  const results = [];
  async function check(name, body) {
    try {
      const detail = await body();
      results.push({ name, passed: true, ...(detail ? { detail } : {}) });
    } catch (error) {
      results.push({ name, passed: false, code: error.code, error: error.message });
    }
  }
  async function denied(name, body) {
    await check(name, async () => {
      try {
        await body();
      } catch (error) {
        assert(deniedCodes.has(error.code), `expected sandbox denial, got ${error.code}`);
        return error.code;
      }
      throw new Error('operation unexpectedly allowed');
    });
  }

  await check('node-started', () => ({ version: process.version }));
  if (process.env.HOME !== undefined) {
    await check('unchanged-home-homedir-without-os-lookup', () => {
      assert.equal(homedir(), process.env.HOME);
      return 'HOME was preserved, never redirected; no private file read';
    });
  }
  for (const key of ['state', 'workspace', 'tmp']) {
    await check(`${key}-read-write-allowed`, () => {
      const target = path.join(fixture[key], 'allowed.txt');
      fs.writeFileSync(target, 'B0_SYNTHETIC_ONLY', { mode: 0o600 });
      assert.equal(fs.readFileSync(target, 'utf8'), 'B0_SYNTHETIC_ONLY');
    });
  }
  await denied('outside-synthetic-read-denied', () => fs.readFileSync(fixture.deniedRead));
  await denied('outside-synthetic-write-denied', () => fs.writeFileSync(fixture.deniedWrite, 'DENIED'));
  await denied('readonly-source-write-denied', () => fs.writeFileSync(path.join(fixture.readonly, 'new.txt'), 'DENIED'));
  await check('config-read-allowed', () => {
    assert.equal(fs.readFileSync(path.join(fixture.config, 'synthetic-config.txt'), 'utf8'), 'B0_CONFIG_NOT_CREDENTIALS');
  });
  await denied('config-write-denied', () => fs.writeFileSync(path.join(fixture.config, 'new.txt'), 'DENIED'));
  await denied('symlink-escape-read-denied', () => fs.readFileSync(path.join(fixture.workspace, 'escape.txt')));
  await denied('symlink-escape-write-denied', () => fs.writeFileSync(path.join(fixture.workspace, 'escape.txt'), 'DENIED'));

  await check('loopback-4317-listen-allowed', async () => {
    const server = net.createServer((socket) => socket.end());
    await listen(server, dshPort);
    await close(server);
  });
  await check('loopback-4319-connect-allowed', async () => {
    const result = await connectResult(host, mockPort);
    assert.equal(result.connected, true, JSON.stringify(result));
  });
  await check('loopback-4316-private-bridge-listen-allowed', async () => {
    const server = net.createServer((socket) => socket.end());
    await listen(server, 4316);
    await close(server);
  });
  await check('loopback-4315-private-kernel-connect-allowed', async () => {
    const result = await connectResult(host, 4315);
    assert.equal(result.connected, true, JSON.stringify(result));
  });
  await check('unapproved-loopback-connect-denied', async () => {
    const result = await connectResult(host, fixture.deniedPort);
    assert(deniedCodes.has(result.code), JSON.stringify(result));
    return result.code;
  });
  await check('external-test-net-connect-denied', async () => {
    const result = await connectResult('192.0.2.1', 443);
    assert(deniedCodes.has(result.code), JSON.stringify(result));
    return result.code;
  });
  await denied('unapproved-loopback-bind-denied', async () => {
    const server = net.createServer();
    try {
      await listen(server, 0);
    } finally {
      if (server.listening) await close(server);
    }
  });
  await check('child-process-shell-denied', async () => {
    const result = await new Promise((resolve) => {
      try {
        const child = spawn('/bin/sh', ['-c', 'exit 0'], { stdio: 'ignore' });
        child.once('error', (error) => resolve({ code: error.code }));
        child.once('close', (exitCode, signal) => resolve({ exitCode, signal }));
      } catch (error) {
        resolve({ code: error.code });
      }
    });
    assert(deniedCodes.has(result.code), JSON.stringify(result));
    return result.code;
  });
  const report = { kind: 'DSH_B0_SEATBELT_SYNTHETIC_PROBE', allPassed: results.every((item) => item.passed), results };
  process.stdout.write(`${JSON.stringify(report)}\n`);
  process.exitCode = report.allPassed ? 0 : 1;
}

async function nativeProbe(fixture) {
  const results = [];
  async function check(name, body) {
    try {
      await body();
      results.push({ name, passed: true });
    } catch (error) {
      results.push({ name, passed: false, code: error.code, error: error.message });
    }
  }
  await check('native-fs-ext-load', async () => {
    const target = path.join(fixture.upstream, 'node_modules/.pnpm/fs-ext@2.1.1/node_modules/fs-ext/fs-ext.js');
    const loaded = await import(pathToFileURL(target).href);
    assert.equal(typeof loaded.default.flockSync, 'function');
  });
  await check('native-koffi-load', async () => {
    const target = path.join(fixture.upstream, 'node_modules/.pnpm/koffi@3.1.1/node_modules/koffi/index.js');
    const loaded = await import(pathToFileURL(target).href);
    assert.equal(typeof loaded.default.load, 'function');
  });
  await check('worker-thread-no-subprocess', async () => {
    await new Promise((resolve, reject) => {
      const worker = new Worker('require("node:worker_threads").parentPort.postMessage("B0_SYNTHETIC_WORKER")', { eval: true });
      worker.once('error', reject);
      worker.once('message', (value) => {
        try { assert.equal(value, 'B0_SYNTHETIC_WORKER'); resolve(); } catch (error) { reject(error); }
      });
    });
  });
  await check('homedir', () => {
    assert.equal(homedir(), process.env.HOME);
  });
  const report = { kind: 'DSH_B0_NATIVE_READONLY_PROBE', allPassed: results.every((item) => item.passed), results };
  process.stdout.write(`${JSON.stringify(report)}\n`);
  process.exitCode = report.allPassed ? 0 : 1;
}

async function parentProbe() {
  assert.equal(process.platform, 'darwin', 'This profile is macOS-only');
  const b0Root = path.join(repository, '.context/dsh-b0');
  fs.mkdirSync(b0Root, { recursive: true, mode: 0o700 });
  const fixtureRoot = fs.mkdtempSync(path.join(b0Root, 'sandbox-probe-'));
  fs.chmodSync(fixtureRoot, 0o700);
  const fixture = { root: fs.realpathSync(fixtureRoot) };
  const native = process.argv.includes('--native');
  const preserveHome = process.argv.includes('--preserve-home');
  if (native) fixture.upstream = fs.realpathSync(path.join(b0Root, 'upstream'));
  for (const key of ['state', 'workspace', 'tmp', 'readonly', 'config', 'denied']) {
    fixture[key] = path.join(fixture.root, key);
    fs.mkdirSync(fixture[key], { mode: 0o700 });
  }
  fixture.deniedRead = path.join(fixture.denied, 'synthetic-sentinel.txt');
  fixture.deniedWrite = path.join(fixture.denied, 'synthetic-write.txt');
  fs.writeFileSync(fixture.deniedRead, 'B0_SYNTHETIC_SENTINEL_NOT_PRIVATE', { mode: 0o600 });
  fs.writeFileSync(path.join(fixture.config, 'synthetic-config.txt'), 'B0_CONFIG_NOT_CREDENTIALS', { mode: 0o600 });
  fs.symlinkSync(fixture.deniedRead, path.join(fixture.workspace, 'escape.txt'));

  const mock = http.createServer((_request, response) => response.end('B0_SYNTHETIC_MOCK'));
  const kernel = http.createServer((_request, response) => response.end('B0_SYNTHETIC_KERNEL_PROBE'));
  const unapproved = net.createServer((socket) => socket.end());
  try {
    await listen(mock, mockPort); // Fails closed if another process owns 4319.
    await listen(kernel, 4315);
    const forbiddenAddress = await listen(unapproved, 0);
    fixture.deniedPort = forbiddenAddress.port;
    const nodeBinary = fs.realpathSync(process.execPath);
    const cellarRoot = runtimeCodeRoot(nodeBinary);
    const parameters = {
      NODE_BINARY: nodeBinary,
      RUNTIME_CELLAR: cellarRoot,
      READ_SOURCE: native ? fixture.upstream : fixture.readonly,
      READ_PLUGIN: scriptDir,
      READ_CONFIG: fixture.config,
      STATE_HOME: fixture.state,
      WORKSPACE: fixture.workspace,
      TEMP_DIR: fixture.tmp,
      BIND_ENDPOINT: `localhost:${dshPort}`,
      MOCK_ENDPOINT: `localhost:${mockPort}`,
      BRIDGE_ENDPOINT: 'localhost:4316',
      KERNEL_ENDPOINT: 'localhost:4315',
    };
    const args = ['-f', path.join(scriptDir, 'sandbox.sb')];
    for (const [key, value] of Object.entries(parameters)) args.push('-D', `${key}=${value}`);
    args.push(nodeBinary, sourceFile, native ? '--native-child' : '--child', JSON.stringify(fixture));
    const execution = await new Promise((resolve, reject) => {
      // No inherited API keys, proxy variables, NODE_OPTIONS, loader paths, or
      // personal config. Optional HOME is preserved byte-for-byte, never
      // repurposed as a temporary directory; file-data access remains denied.
      const child = spawn('/usr/bin/sandbox-exec', args, {
        cwd: fixture.workspace,
        env: {
          PATH: '/usr/bin:/bin',
          OPENSSL_CONF: '/dev/null',
          DSH_HOME: fixture.state,
          TMPDIR: `${fixture.tmp}/`,
          LANG: 'en_US.UTF-8',
          ...(preserveHome && process.env.HOME ? { HOME: process.env.HOME } : {}),
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      let stdout = '';
      let stderr = '';
      const timer = setTimeout(() => child.kill('SIGKILL'), 15000);
      child.stdout.setEncoding('utf8').on('data', (chunk) => { stdout += chunk; });
      child.stderr.setEncoding('utf8').on('data', (chunk) => { stderr += chunk; });
      child.once('error', (error) => { clearTimeout(timer); reject(error); });
      child.once('close', (exitCode, signal) => {
        clearTimeout(timer);
        resolve({ exitCode, signal, stdout, stderr });
      });
    });
    const report = { ...execution, fixtureRoot: fixture.root, nodeBinary, parameters };
    fs.writeFileSync(path.join(fixture.root, 'report.json'), `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    process.exitCode = execution.exitCode === 0 ? 0 : 1;
  } finally {
    if (mock.listening) await close(mock);
    if (kernel.listening) await close(kernel);
    if (unapproved.listening) await close(unapproved);
  }
}

if (process.argv[2] === '--child') await childProbe(JSON.parse(process.argv[3]));
else if (process.argv[2] === '--native-child') await nativeProbe(JSON.parse(process.argv[3]));
else await parentProbe();
