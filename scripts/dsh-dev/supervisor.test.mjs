import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'node:net';
import { bootHost, stopOwned, terminateChild } from './serve.mjs';

async function fixture(source) {
  const runtime = await mkdtemp(join(tmpdir(), 'dsh-supervisor-'));
  const cli = join(runtime, 'fake.mjs');
  await writeFile(cli, source);
  await mkdir(join(runtime, 'tmp'));
  return { runtime, home: runtime, workspace: runtime, cli, patches: [], host: '127.0.0.1', webPort: 4327 };
}
test('legacy PID metadata never authorizes stopping a process', async () => {
  await assert.rejects(stopOwned({ childPid: process.pid, supervisorPid: process.pid }), /refusing to signal stored PIDs/);
});
test('startup timeout reaps its child before rejecting', async () => {
  const prepared = await fixture(`import { writeFileSync } from 'node:fs'; writeFileSync('pid', String(process.pid)); setInterval(() => {}, 1000);`);
  await assert.rejects(bootHost(prepared, { timeoutMs: 500 }), /ready URL/);
  const pid = Number(await readFile(join(prepared.runtime, 'pid'), 'utf8'));
  assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' });
});
test('a running sibling kernel does not block the web supervisor', async () => {
  const sibling = createServer();
  await new Promise(resolve => sibling.listen(4325, '127.0.0.1', resolve));
  let booted;
  try {
    const prepared = await fixture(`console.log('http://127.0.0.1:4327/?token=synthetic-ready-token'); setInterval(() => {}, 1000);`);
    booted = await bootHost(prepared, { timeoutMs: 1000 });
    assert.equal(booted.origin, 'http://127.0.0.1:4327');
  } finally {
    if (booted) await terminateChild(booted.child, booted.childExit);
    await new Promise(resolve => sibling.close(resolve));
  }
});


test('excess startup output stays bounded and the child is reaped', async () => {
  const prepared = await fixture(`import {writeFileSync} from 'node:fs'; writeFileSync('pid', String(process.pid)); setInterval(() => process.stdout.write('x'.repeat(65536)), 1);`);
  await assert.rejects(bootHost(prepared, { timeoutMs: 3000 }), /log exceeds bound/);
  const pid = Number(await readFile(join(prepared.runtime, 'pid'), 'utf8'));
  assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' });
  assert.ok((await readFile(join(prepared.runtime, 'boot.log'))).length <= 2 * 1024 * 1024);
});
