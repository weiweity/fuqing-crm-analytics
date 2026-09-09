import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createServer } from 'node:net';
import { diagnose, inspectListener } from './diagnose.mjs';
import { COMPETITION_VITE_PORT, FOREIGN_PORTS, PORTS } from './constants.mjs';
import { repoRoot } from './paths.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));

test('diagnose source never signals PIDs or binds a listen socket', async () => {
  const source = await readFile(new URL('./diagnose.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /process\.kill/);
  assert.doesNotMatch(source, /SIGTERM|SIGKILL/);
  assert.doesNotMatch(source, /createServer\(/);
  assert.doesNotMatch(source, /listen\(/);
  assert.match(source, /Never binds, never signals PIDs/);
});

test('inspectListener reports a bound owned-range port without killing it', async () => {
  let probePort;
  const server = createServer();
  await new Promise((ok, fail) => {
    server.once('error', fail);
    server.listen(0, '127.0.0.1', ok);
  });
  try {
    probePort = server.address().port;
    const snapshot = await inspectListener(probePort);
    assert.equal(snapshot.state, 'listening');
    assert.equal(snapshot.listeners[0].pid, process.pid);
  } finally {
    await new Promise((ok, fail) => server.close(e => e ? fail(e) : ok()));
  }
  const freed = await inspectListener(probePort);
  assert.equal(freed.state, 'free');
});

test('diagnose classifies foreign and user-demo ports without probing them over HTTP', async t => {
  t.mock.method(globalThis, 'fetch', async () => assert.fail('cold-state diagnosis must not send HTTP'));
  const report = await diagnose({}, async () => null);
  assert.equal(report.kind, 'DSH_DEV_DIAGNOSE');
  assert.equal(report.repo, repoRoot);
  assert.deepEqual(report.actions_not_taken, [
    'did_not_signal_any_pid',
    'did_not_bind_ports',
    'did_not_http_probe_4327',
    'did_not_http_probe_8000_or_5173',
    'did_not_start_dsh',
  ]);
  const byPort = new Map(report.ports.map(row => [row.port, row]));
  for (const port of FOREIGN_PORTS) {
    assert.equal(byPort.get(port).classification.stop, 'refuse');
    assert.equal(byPort.get(port).classification.reuse, 'refuse');
  }
  const demo = byPort.get(PORTS.web);
  if (demo.state === 'listening') {
    assert.equal(demo.classification.owner, 'user_demo');
    assert.equal(demo.classification.reuse, 'refuse');
    assert.equal(demo.classification.stop, 'refuse');
  }
  assert.equal(byPort.get(COMPETITION_VITE_PORT).classification.reuse, 'refuse_as_dsh_web');
  assert.equal(report.auth.live.status, 'NOT_RUN');
  assert.equal(report.brand.logo.status, 'ok');
  assert.equal(report.brand.mark.status, 'ok');
  assert.equal(report.brand.outfit.status, 'ok');
  assert.equal(report.auth.mechanism.never_print_token, true);
  assert.equal(report.auth.mechanism.never_disable_auth, true);
  assert.doesNotMatch(JSON.stringify(report), /[?&](?:token|b0)=(?!\[REDACTED\])[A-Za-z0-9_-]+/);
});
