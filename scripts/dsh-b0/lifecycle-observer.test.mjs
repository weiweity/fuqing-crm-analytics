import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, stat, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { observeLifecycle } from './lifecycle-observer.mjs';

const cwd = dirname(fileURLToPath(import.meta.url));
const moduleUrl = new URL('./lifecycle-observer.mjs', import.meta.url).href;
const fresh = () => mkdtemp(join(tmpdir(), 'b0-lifecycle-test-'));
const rows = async directory => (await readFile(join(directory, 'supervisor-lifecycle.jsonl'), 'utf8'))
  .trim().split('\n').map(JSON.parse);
async function probe(body) {
  const directory = await fresh();
  const code = `import {observeLifecycle} from ${JSON.stringify(moduleUrl)};
const observer = observeLifecycle(${JSON.stringify(directory)});\n${body}`;
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', code], {
    cwd, encoding: 'utf8', timeout: 10000,
    env: { PATH: dirname(process.execPath), NODE_NO_WARNINGS: '1' },
  });
  assert.ifError(result.error);
  return { result, rows: await rows(directory) };
}

test('passive heartbeat does not keep a normal child alive; exit code is retained', async () => {
  const { result, rows } = await probe('process.exitCode = 7;');
  assert.equal(result.status, 7);
  assert.deepEqual(rows.map(row => row.event), ['start', 'exit']);
  assert.equal(rows.at(-1).exitCode, 7);
});

for (const [name, body, origin] of [
  ['uncaught exception', 'setImmediate(() => { throw Object.assign(new Error("sensitive-message"), {code:"EPIPE"}); });', 'uncaughtException'],
  ['unhandled rejection', 'Promise.reject(new Error("sensitive-message"));', 'unhandledRejection'],
]) test(`${name} is observed without preventing default process failure`, async () => {
  const { result, rows } = await probe(body);
  assert.equal(result.status, 1);
  assert.deepEqual(rows.map(row => row.event), ['start', 'fatal', 'exit']);
  assert.equal(rows[1].origin, origin);
  assert.ok(!JSON.stringify(rows).includes('sensitive-message'));
});

for (const signal of ['SIGTERM', 'SIGKILL']) test(`${signal} is not intercepted or falsely reported as clean exit`, async () => {
  const { result, rows } = await probe(`process.kill(process.pid, ${JSON.stringify(signal)}); setInterval(() => {}, 1000);`);
  assert.equal(result.signal, signal);
  assert.deepEqual(rows.map(row => row.event), ['start']);
});

test('metadata allowlist omits raw messages, arbitrary strings, paths and secrets', async () => {
  const directory = await fresh();
  const observer = observeLifecycle(directory);
  try {
    observer.record('host-ready', { childPid: 123, generation: 2, message: 'secret', token: 'secret',
      reason: 'secret', signal: 'secret', errorCode: 'secret', origin: 'secret' });
    assert.equal(observer.record('secret'), false);
    assert.equal((await stat(join(directory, 'supervisor-lifecycle.jsonl'))).mode & 0o777, 0o600);
  } finally { observer.dispose(); }
  const recorded = await rows(directory);
  assert.ok(!JSON.stringify(recorded).includes('secret'));
  assert.equal(recorded[1].generation, 2);
  assert.equal(recorded[1].errorCode, 'OTHER');
});

test('bounded evidence reserves fatal and exit events after ordinary event cap', async () => {
  const directory = await fresh();
  const observer = observeLifecycle(directory);
  try {
    for (let i = 0; i < 1000; i++) observer.record('heartbeat');
    observer.record('fatal'); observer.record('fatal'); observer.record('exit', {exitCode: 1});
  } finally { observer.dispose(); }
  const recorded = await rows(directory);
  assert.equal(recorded.length, 503);
  assert.deepEqual(recorded.slice(-3).map(row => row.event), ['limit-reached', 'fatal', 'exit']);
});

test('existing evidence and symlink targets are not overwritten', async () => {
  const directory = await fresh();
  const path = join(directory, 'supervisor-lifecycle.jsonl');
  await writeFile(path, 'retained');
  assert.throws(() => observeLifecycle(directory), { code: 'EEXIST' });
  assert.equal(await readFile(path, 'utf8'), 'retained');
  const linked = await fresh();
  await symlink(path, join(linked, 'supervisor-lifecycle.jsonl'));
  assert.throws(() => observeLifecycle(linked), { code: 'EEXIST' });
  assert.equal(await readFile(path, 'utf8'), 'retained');
});
