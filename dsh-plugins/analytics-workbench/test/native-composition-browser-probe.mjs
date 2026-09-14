/** Explicit full pinned DSH browser fixture. No global runtime metadata, real data or model keys. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { prepareRuntime, installProfilePlugin, bootHost, terminateChild } from '../../../scripts/dsh-dev/serve.mjs';
import { assertFree } from '../../../scripts/dsh-dev/ports.mjs';

const root = fileURLToPath(new URL('../../..', import.meta.url));
const python = process.env.FQ_B0_PYTHON;
assert.ok(python?.startsWith('/'), 'FQ_B0_PYTHON must identify the authorized absolute interpreter');
const port = Number(process.env.COMPOSITION_WEB_PORT ?? 4328);
assert.notEqual(port, 4327, 'Never reuse the existing user demo');
await assertFree(port);
const evidence = join(root, '.context/checks/ai-cockpit-goal');
await mkdir(evidence, { recursive: true });
const runtime = await mkdtemp(join(evidence, 'native-composition-runtime-'));
const child = spawn(python, ['-m', 'backend.tests.library_board_http_probe'], { cwd: root,
  env: { PATH: process.env.PATH, PYTHONPATH: root, PYTHONNOUSERSITE: '1', PYTHON_DOTENV_DISABLED: '1', PYTHONDONTWRITEBYTECODE: '1' },
  stdio: ['pipe', 'pipe', 'pipe'] });
const terminal = new Promise(resolve => { child.once('exit', (code, signal) => resolve({ code, signal })); child.once('error', error => resolve({ error: error.message })); });
let stderr = '', host, bootstrap, counter = 0;
child.stderr.on('data', data => { if (stderr.length < 6000) stderr += data; });
try {
  const lines = createInterface({ input: child.stdout }); let timer;
  const ready = await Promise.race([
    new Promise((resolve, reject) => lines.once('line', line => { try { resolve(JSON.parse(line)); } catch (error) { reject(error); } })),
    terminal.then(() => { throw new Error('isolated Python stopped before ready'); }),
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('readiness timeout')), 15000); }),
  ]).finally(() => { clearTimeout(timer); lines.close(); });
  assert.equal(ready.contains_real_data, false);
  process.env.COMPETITION_HTTP_BASE = `http://127.0.0.1:${ready.port}`;
  process.env.COMPETITION_HTTP_TOKEN = 'isolated-native-board-integration-token';
  const diagnosticPatch = join(runtime, 'diagnostic.patch.json');
  await writeFile(diagnosticPatch, JSON.stringify([{ insert: [{ id: 'composition-fixture-diagnostic',
    name: new URL('./helpers/native-composition-diagnostic.mjs', import.meta.url).href },
  { id: 'composition-fixture-history', name: new URL('./helpers/native-composition-history.mjs', import.meta.url).href }] }]), { mode: 0o600 });
  let pluginMode = 'on';
  let prepared = await prepareRuntime({ plugin: pluginMode, runtime, extraPatch: [diagnosticPatch], host: '127.0.0.1', webPort: port });
  await writeFile(join(prepared.workspace, 'composition-proof.md'), '# 原生侧栏合成验收\n\n本文件只用于检查文件预览与驾驶舱共存。不含真实业务数据，没有调用模型。\n', { mode: 0o600 });
  console.log(JSON.stringify({ stage: 'install-local-plugin', runtime, model_calls: 0 }));
  installProfilePlugin(prepared);
  host = await bootHost(prepared);
  const auth = await fetch(host.launchUrl, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
  const cookie = auth.headers.getSetCookie().map(value => value.split(';')[0]).join('; ');
  await auth.arrayBuffer(); assert.ok(cookie, 'native auth exchange failed');
  async function nativeCall(method, request) {
    const response = await fetch(`${host.origin}/api/${method}`, { method: 'POST',
      headers: { 'content-type': 'application/json', cookie },
      body: JSON.stringify({ type: 'client-request', rpcId: `composition-${++counter}`, method,
        payload: { args: { request } } }), signal: AbortSignal.timeout(10000) });
    const reply = await response.json();
    assert.equal(reply.result?.ok, true, `${method} rejected: ${JSON.stringify(reply.result?.error)}`);
    return reply.result.value;
  }
  const workspace = await nativeCall('workspace/create', { path: prepared.workspace });
  const sessionId = 'session-composition-synthetic';
  await nativeCall('session/create', { workspaceId: workspace.workspace.workspaceId, sessionId });
  const historySeed = await fetch(`${host.origin}/__composition_seed__`, { method: 'POST', headers: { cookie }, signal: AbortSignal.timeout(10000) });
  assert.equal(historySeed.status, 200, 'isolated native history seed failed');
  assert.equal((await historySeed.json()).messages, 1);
  async function boardCall(path, body, key) {
    const response = await fetch(`${process.env.COMPETITION_HTTP_BASE}/api/v1/analytics/board-spec${path}`, {
      method: 'POST', headers: { authorization: `Bearer ${process.env.COMPETITION_HTTP_TOKEN}`,
        'content-type': 'application/json', ...(key ? { 'idempotency-key': key } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(10000) });
    assert.ok(response.ok, `synthetic board ${path}: ${response.status}`); return response.json();
  }
  const preview = await boardCall('/previews', { title: '原生并排 · 合成验收看板', session_id: sessionId, blocks: [
    { block_id: 'note', kind: 'TEXT', title: '可编辑说明', library_version: 'board-components/v1',
      props: { content: '这是一份隔离的合成验收看板。调整布局不应清空右侧原生对话的未发送草稿。' }, layout: { x: 0, y: 0, w: 6, h: 5 } },
    { block_id: 'neighbour', kind: 'TEXT', title: '保持不变的组件', library_version: 'board-components/v1',
      props: { content: '用于核对相邻组件和保存重开。没有调用模型或读取真实业务数据。' }, layout: { x: 6, y: 0, w: 6, h: 5 } },
  ] });
  const saved = await boardCall(`/previews/${preview.preview_id}/confirm`, null, 'composition-seed');
  // Disposable loopback-only login redirect. Never expose the native credential in tool output.
  bootstrap = createServer((req, res) => {
    if (req.method !== 'GET' || req.url !== '/start' || req.headers.origin
      || req.headers.host !== `127.0.0.1:${bootstrap.address().port}`) { res.writeHead(404); res.end(); return; }
    res.writeHead(302, { location: host.launchUrl, 'cache-control': 'no-store', 'referrer-policy': 'no-referrer' }); res.end();
  });
  bootstrap.listen(0, '127.0.0.1'); await once(bootstrap, 'listening');
  console.log(JSON.stringify({ stage: 'ready', url: `http://127.0.0.1:${bootstrap.address().port}/start`,
    origin: host.origin, runtime, board_id: saved.spec.board_id, session_id: sessionId,
    contains_real_data: false, model_calls: 0, scope: 'full pinned native shell + production plugin + SQLite; seeded board, not AI generation' }));
  const controls = createInterface({ input: process.stdin });
  const commands = controls[Symbol.asyncIterator]();
  const stopped = new Promise(resolve => { process.once('SIGTERM', () => resolve({ done: true })); process.once('SIGINT', () => resolve({ done: true })); });
  try {
    while (true) {
      const command = await Promise.race([commands.next(), stopped,
        terminal.then(() => { throw new Error('owned Python exited during browser probe'); }),
        host.childExit.then(() => { throw new Error('owned DSH exited during browser probe'); })]);
      if (command.done || !['restart', 'plugin-on', 'plugin-off'].includes(command.value)) break;
      await terminateChild(host.child, host.childExit);
      if (command.value !== 'restart') {
        pluginMode = command.value === 'plugin-on' ? 'on' : 'off';
        prepared = await prepareRuntime({ plugin: pluginMode, runtime, extraPatch: [diagnosticPatch], host: '127.0.0.1', webPort: port });
        if (pluginMode === 'on') installProfilePlugin(prepared);
      }
      host = await bootHost(prepared);
      console.log(JSON.stringify({ stage: 'restarted-owned-host', plugin: pluginMode, origin: host.origin, runtime, model_calls: 0 }));
    }
  } finally { controls.close(); }
} finally {
  if (bootstrap) { bootstrap.closeAllConnections(); await new Promise(resolve => bootstrap.close(resolve)); }
  if (host) await terminateChild(host.child, host.childExit);
  child.stdin.end();
  const timer = setTimeout(() => child.kill('SIGTERM'), 12000);
  const result = await terminal; clearTimeout(timer); process.stdin.pause();
  assert.deepEqual(result, { code: 0, signal: null }, stderr);
  console.log('NATIVE_COMPOSITION_PROBE_CLOSED');
}
