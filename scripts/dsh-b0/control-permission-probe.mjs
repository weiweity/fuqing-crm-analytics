/** Regression: lose the current permission authority, fail closed on HTTP and WS.
 * Only an explicitly named current synthetic runner may be paused; always resume
 * its exact verified kernel PID. Does not submit prompts or touch real identity.
 */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const [target, ...extra] = process.argv.slice(2);
assert.ok(target && !extra.length, 'Pass the exact current synthetic runtime');
const runtime = resolve(target);
const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
assert.equal(runtime, current.runtime);
assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
assert.match(execFileSync('ps', ['-p', String(current.kernelPid), '-o', 'args='], { encoding: 'utf8' }), /-m backend\.analytics_runtime/);
const { launchUrl } = JSON.parse(await readFile(join(runtime, 'gateway-private.json'), 'utf8'));
assert.equal(new URL(launchUrl).origin, 'http://127.0.0.1:4318');
const { sessionId } = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
const exchange = await fetch(launchUrl, { redirect: 'manual', signal: AbortSignal.timeout(3000) });
const cookie = exchange.headers.getSetCookie().map(value => value.split(';')[0]).join('; ');
assert.ok(cookie);
const { WebSocket } = createRequire(join(root, '.context/dsh-b0/upstream/packages/api/gateway/package.json'))('ws');
const report = { schema_version: 'b0-current-permission-probe/v1', started_at: new Date().toISOString(),
  tests: [], valid_prompts_sent: 0, restored_kernel: false, status: 'RUNNING' };
let socket, paused = false;
const frames = [];
const path = join(runtime, `permission-probe-${Date.now()}.json`);
async function rpc() {
  const response = await fetch('http://127.0.0.1:4318/api/session/modelCatalog', { method: 'POST',
    headers: { cookie, 'content-type': 'application/json' },
    body: JSON.stringify({ type: 'client-request', rpcId: 'permission-probe', method: 'session/modelCatalog', payload: { args: {} } }),
    signal: AbortSignal.timeout(8000), redirect: 'error' });
  await response.arrayBuffer();
  return response.status;
}
async function wait(check, timeout = 8000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = check(); if (value) return value; await delay(25); }
  throw new Error('Bounded permission observation timed out');
}
try {
  assert.equal(await rpc(), 200);
  socket = new WebSocket('ws://127.0.0.1:4318/api/remote.mux', { headers: { cookie, origin: 'http://127.0.0.1:4318' }, handshakeTimeout: 6000 });
  socket.on('error', () => {});
  socket.on('message', bytes => { frames.push(JSON.parse(String(bytes))); });
  await wait(() => socket.readyState === WebSocket.OPEN);
  socket.send(JSON.stringify({ type: 'open', streamId: 'before', endpoint: 'session/control', payload: { args: {} } }));
  await wait(() => frames.some(frame => frame.type === 'item' && frame.streamId === 'before'));
  process.kill(current.kernelPid, 'SIGSTOP');
  paused = true;
  const status = await rpc();
  report.tests.push({ name: 'HTTP metadata when permission authority unavailable', status: status >= 400 ? 'PASS' : 'FAIL', http_status: status });
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'open', streamId: 'after', endpoint: 'session/follow', payload: {
      args: { request: { address: { kind: 'session', sessionId }, maxMessages: 20 } },
    } }));
    await wait(() => socket.readyState !== WebSocket.OPEN || frames.some(frame => frame.streamId === 'after'));
  }
  const data = frames.some(frame => frame.type === 'item' && frame.streamId === 'after');
  const refused = socket.readyState !== WebSocket.OPEN || frames.some(frame => frame.type === 'error' && frame.streamId === 'after');
  report.tests.push({ name: 'existing WS connection after permission authority unavailable', status: !data && refused ? 'PASS' : 'FAIL', data_delivered: data, refused });
  report.status = report.tests.every(row => row.status === 'PASS') ? 'PASS' : 'FAIL';
  if (report.status !== 'PASS') process.exitCode = 1;
} catch {
  report.status = 'FAIL'; report.error = 'Current permission probe did not complete'; process.exitCode = 1;
} finally {
  if (paused) { process.kill(current.kernelPid, 'SIGCONT'); report.restored_kernel = true; }
  socket?.terminate();
  report.completed_at = new Date().toISOString();
  await writeFile(path, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ ...report, report_path: path }));
}
