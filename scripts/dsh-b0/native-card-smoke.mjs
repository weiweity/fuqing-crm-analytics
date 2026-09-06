/** Explicit finite synthetic native-card verification, driven only by browser UI.
 * Alters/restores only the fresh runtime's generated manifest; never a real DB.
 */
import assert from 'node:assert/strict';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { openSync, fstatSync, closeSync, constants } from 'node:fs';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { zstdDecompressSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { join, resolve, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { summarizeRequest, requestForTool } from '../../dsh-plugins/analytics-workbench/src/native-evidence.mjs';
import { decodeFixture } from '../../dsh-plugins/analytics-workbench/src/model.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const [namedRuntime, browse, tab, verifyFlag, ...extra] = process.argv.slice(2);
assert.ok(isAbsolute(namedRuntime ?? '') && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length
  && (verifyFlag === undefined || verifyFlag === '--verify-existing'),
  'Usage: node native-card-smoke.mjs /absolute/current-runtime /absolute/browse <owned-tab-id> [--verify-existing]');
const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
const runtime = resolve(namedRuntime);
assert.equal(current.runtime, runtime);
assert.equal(current.verificationScenario, 'native-cards');
assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
const config = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
const upstream = join(root, '.context/dsh-b0/upstream');
const { flockSync } = createRequire(join(upstream, 'packages/session/session-persistence-jsonl/package.json'))('fs-ext');
const { scanZstdFrames } = await import(pathToFileURL(join(upstream, 'packages/session/session-persistence-jsonl/lib/types/zstd.js')).href);
const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 4 * 1024 * 1024 });
const rows = () => db.prepare(`SELECT r.run_id,r.attempt_id,r.status,r.error_code,r.result_json,r.tool_steps_used,r.deadline_ms,
  d.session_id,d.request_id,d.payload_json,d.payload_hash,d.attempts FROM runs r JOIN dispatch_intents d USING(run_id) ORDER BY r.rowid`).all();
const report = { kind: 'B0_NATIVE_CARD_FAULT_CHAIN', runtime, tab: Number(tab), started_at: new Date().toISOString(), actions: [] };
report.plugin_hashes = Object.fromEntries(await Promise.all(['index.js', 'tool.js', 'skills.js', 'client.js']
  .map(async name => [name, createHash('sha256').update(await readFile(join(current.plugin, 'lib', name))).digest('hex')])));
const manifest = join(runtime, 'fixture/manifest.json');
const original = await readFile(manifest);
let manifestAltered = false;
async function waitFor(check, milliseconds = 12000) {
  const until = Date.now() + milliseconds;
  while (Date.now() < until) { if (await check()) return; await delay(100); }
  throw new Error('Native card verification deadline expired');
}
function send(text) {
  const snapshot = b('snapshot', '-i');
  const input = snapshot.match(/(@e\d+) \[textbox\] "(?:Describe what you want to build|Message or run a task)\.\.\. \/ commands, @ files or sessions"/);
  const button = snapshot.match(/(@e\d+) \[button\] "Send message"/);
  assert.ok(input && button, 'Native composer not ready');
  b('fill', input[1], text); b('click', button[1]);
  report.actions.push({ type: 'native-send', text });
}
function expandTools() {
  for (let i = 0; i < 8; i++) {
    const match = b('snapshot', '-i').match(/(@e\d+) \[button\] "\d+ tool calls?"(?! \[expanded\])/);
    if (!match) return;
    b('click', match[1]);
  }
  throw new Error('Tool group expansion did not settle');
}
async function nativeLog() {
  const sessions = join(runtime, 'harness/sessions');
  for (const project of await readdir(sessions, { withFileTypes: true })) {
    if (!project.isDirectory()) continue;
    const file = join(sessions, project.name, refs.sessionId, 'session.v2.jsonl.zstd');
    let bytes;
    try { bytes = await readFile(file); } catch (error) { if (error.code === 'ENOENT') continue; throw error; }
    const scan = scanZstdFrames(bytes);
    assert.equal(scan.tornStart, undefined);
    const lines = scan.frames.flatMap(({start, end}) => zstdDecompressSync(bytes.subarray(start, end)).toString('utf8')
      .split('\n').filter(Boolean).map(JSON.parse));
    const header = lines.find(row => row.type === 'session');
    assert.equal(header.id, refs.sessionId); assert.equal(header.cwd, join(runtime, 'synthetic-workspace'));
    return lines.filter(row => row.type !== 'session');
  }
  throw new Error('Native durable journal missing');
}
function cardState() {
  return JSON.parse(b('js', `JSON.stringify({cards: [...document.querySelectorAll('.analytics-b0-card')].map(e => e.textContent),
    skill: [...document.querySelectorAll('button,[role="button"]')].some(e => e.textContent.includes('Skill') && e.textContent.includes('growth-analysis-b0'))})`));
}
try {
  assert.equal(rows().length, verifyFlag ? 4 : 0, 'Use a fresh runtime or verify exactly four existing prompts');
  b('tab', tab); assert.equal(b('url').trim(), 'http://127.0.0.1:4318/');
  const questions = ['B0 卡片第一问：展示固定合成渠道复购样例。',
    'B0 卡片第二问：验证合成夹具损坏后的真实工具失败。',
    'B0 卡片第三问：读取 growth-analysis-b0 方法后查询固定合成渠道。',
    'B0 卡片第四问：失败恢复后再次查询固定合成渠道。'];
  if (verifyFlag) {
    assert.deepEqual(rows().map(row => JSON.parse(row.payload_json).native_request.content[0].text), questions);
    report.actions.push({type: 'verify-existing', prompts_resent: 0});
  }
  for (let index = 0; !verifyFlag && index < questions.length; index++) {
    if (index === 1) {
      await writeFile(manifest, Buffer.concat([original, Buffer.from('\n')]));
      manifestAltered = true;
      report.actions.push({ type: 'alter-owned-synthetic-manifest', database_written: false });
    }
    try {
      send(questions[index]);
      await waitFor(() => ['SUCCEEDED', 'FAILED'].includes(rows()[index]?.status));
      assert.equal(rows()[index].status, index === 1 ? 'FAILED' : 'SUCCEEDED');
      if (index === 1) assert.equal(rows()[index].error_code, 'TOOL_FAILED');
    } finally { if (manifestAltered) { await writeFile(manifest, original); manifestAltered = false; } }
  }
  const runs = rows();
  assert.deepEqual(runs.map(row => row.status), ['SUCCEEDED', 'FAILED', 'SUCCEEDED', 'SUCCEEDED']);
  assert.equal(runs[1].error_code, 'TOOL_FAILED');
  for (const row of runs) {
    assert.equal(row.attempts, 1); assert.equal(row.session_id, refs.sessionId);
    const response = await fetch('http://127.0.0.1:4316/observe', { method: 'POST',
      headers: {authorization: `Bearer ${config.runtime_token}`, 'content-type': 'application/json'},
      body: JSON.stringify({...row, payload: JSON.parse(row.payload_json)}), signal: AbortSignal.timeout(5000) });
    const proof = await response.json(); assert.equal(response.status, 200); assert.equal(proof.execution_exited, true);
  }
  const log = await nativeLog();
  const calls = log.filter(event => event.type === 'tool/call');
  assert.equal(calls.length, 5); assert.equal(new Set(calls.map(event => event.data.callId)).size, 5);
  const results = log.filter(event => event.type === 'tool/result');
  report.tools = [];
  for (const call of calls) {
    const result = results.find(event => event.data.message.content.some(block => block.type === 'tool-result' && block.toolCallId === call.data.callId));
    assert.ok(result, 'Each actual native call needs its own durable result');
    const blocks = result.data.message.content.filter(block => block.type === 'tool-result');
    assert.equal(blocks.length, 1); assert.equal(blocks[0].toolCallId, call.data.callId);
    const requestId = requestForTool(log, call.data.callId);
    const row = runs.find(run => run.request_id === requestId); assert.ok(row);
    const summary = summarizeRequest(log, requestId); assert.equal(summary.targetTurn, call.data.turn);
    assert.equal(log.filter(event => event.type === 'user/message' && event.data.source?.rpcId === requestId).length, 1);
    const failed = row === runs[1];
    assert.equal(blocks[0].isError, failed);
    if (call.data.name === 'analytics_b0_query') {
      assert.equal(Boolean(decodeFixture(result.data.meta)), !failed);
      if (failed) assert.equal(row.result_json, null);
      else assert.equal(JSON.parse(row.result_json).facts.repeat_ratio, 0.25);
    }
    report.tools.push({name: call.data.name, call_id: call.data.callId, request_id: requestId, run_id: row.run_id,
      turn: call.data.turn, is_error: blocks[0].isError, fixture_meta: Boolean(decodeFixture(result.data.meta))});
  }
  const workers = db.prepare('SELECT * FROM worker_executions ORDER BY rowid').all();
  assert.equal(workers.length, 4);
  for (const worker of workers) {
    assert.equal(worker.state, 'EXITED'); assert.equal(worker.active_slot, null); assert.ok(worker.pid > 0);
    assert.equal(worker.error_code, worker.run_id === runs[1].run_id ? 'TOOL_FAILED' : null);
    const fd = openSync(join(runtime, 'kernel/workers', worker.execution_id, '.lease'), constants.O_RDONLY | constants.O_NOFOLLOW);
    try { const info = fstatSync(fd); assert.deepEqual([info.dev, info.ino], [worker.lease_dev, worker.lease_ino]); flockSync(fd, 'exnb'); }
    finally { closeSync(fd); }
  }
  report.runs = runs.map(({run_id, attempt_id, status, error_code, tool_steps_used}) => ({run_id, attempt_id, status, error_code, tool_steps_used}));
  report.workers = workers.map(({execution_id, run_id, state, pid, exit_code, error_code}) => ({execution_id, run_id, state, pid, exit_code, error_code}));
  expandTools();
  const before = cardState();
  assert.equal(before.cards.length, 4); assert.equal(before.cards.filter(text => text.includes('100 位客户中 25 位复购')).length, 3);
  assert.equal(before.cards.filter(text => text.includes('B0 工具失败')).length, 1); assert.equal(before.skill, true);
  assert.ok(before.cards.filter(text => text.includes('B0 工具失败')).every(text => !text.includes('25%')));
  report.before_refresh = before;
  b('reload'); await waitFor(() => b('snapshot').includes(questions[3])); expandTools();
  const after = cardState(); assert.deepEqual(after, before); assert.deepEqual(rows(), runs);
  const refreshedLog = await nativeLog();
  assert.deepEqual(refreshedLog.filter(event => ['tool/call', 'tool/result'].includes(event.type)),
    log.filter(event => ['tool/call', 'tool/result'].includes(event.type)));
  report.refresh = {cards_preserved: true, new_runs: 0, same_call_ids: true};
  report.after_refresh = b('snapshot');
  await writeFile(join(runtime, 'native-card-snapshot.txt'), report.after_refresh, {mode: 0o600});
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL'; report.error = String(error.message).replace(/([?&](?:token|b0)=)[A-Za-z0-9_-]+/g, '$1[REDACTED]').slice(0, 1000);
  process.exitCode = 1;
} finally {
  if (manifestAltered) await writeFile(manifest, original);
  db.close();
  report.completed_at = new Date().toISOString();
  const path = join(runtime, `native-card-evidence-${Date.now()}.json`);
  await writeFile(path, JSON.stringify(report, null, 2) + '\n', {flag: 'wx', mode: 0o600});
  console.log(JSON.stringify({status: report.status, error: report.error, runs: report.runs, report_path: path}));
}
