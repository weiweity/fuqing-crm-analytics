/** Explicit finite native running + parent-protocol rejection driver.
 * Fresh runtime only for live SQL_ACTIVE; verify-existing never infers running.
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

export const SCENARIO = 'native-state';
export const RUNNING_TOOL_CARD = 'B0 合成工具运行中';
export const QUESTIONS = Object.freeze([
  'B0 状态第一问：真实 SQL 运行中后再展示固定合成渠道复购样例。',
  'B0 状态第二问：未知 schema 版本应由真实父协议拒绝。',
  'B0 状态第三问：非法 facts 结果应由真实父协议拒绝。',
  'B0 状态第四问：拒绝后再次查询固定合成渠道。',
]);

export function runningCannotBeInferredFromSuccess(row) {
  return row?.status === 'SUCCEEDED' ? false : null;
}

export function hasRunningToolCard(cards) {
  return Array.isArray(cards) && cards.some(text => typeof text === 'string' && text.includes(RUNNING_TOOL_CARD));
}

export function verifyExistingScope() {
  return { running_live_observed: false, live_running_pass: false, scope: 'durable-only', limited_scope: true };
}

const COMPOSER_INPUT = /(@e\d+) \[textbox\] "(?:Describe what you want to build|Message or run a task)\.\.\. \/ commands, @ files or sessions"/;
const SEND_PRESENT = /(@e\d+) \[button\] "Send message"(?: \[disabled\])?/;
const SEND_ENABLED = /(@e\d+) \[button\] "Send message"(?! \[disabled\])/;

export function parseComposer(snapshot) {
  const text = String(snapshot ?? '');
  const input = text.match(COMPOSER_INPUT);
  const send = text.match(SEND_PRESENT);
  const enabled = text.match(SEND_ENABLED);
  return { inputRef: input?.[1] ?? null, sendRef: send?.[1] ?? null, sendEnabled: Boolean(enabled),
    readyToFill: Boolean(input && send) };
}

export function canSendNextPrompt({ backendTerminal, nativeSettled, composerReady }) {
  return Boolean(nativeSettled && composerReady);
}

export function nativeRequestSettled(summary) {
  return Boolean(summary?.received && !summary.ambiguous && summary.reason?.kind);
}

export function nativeTurnHasDurableResult(events, requestId) {
  const summary = summarizeRequest(events, requestId);
  if (summary.targetTurn == null) return false;
  return events.some(event => event.type === 'tool/result' && event.data?.turn === summary.targetTurn
    && (event.data.message?.content ?? []).some(block => block.type === 'tool-result'));
}

export async function waitUntil(check, { budgetMs = 20000, tickMs = 100, clock = { now: Date.now, sleep: delay } } = {}) {
  const until = clock.now() + budgetMs;
  while (clock.now() < until) {
    if (await check()) return true;
    await clock.sleep(tickMs);
  }
  return false;
}

export function assertReleaseTarget(probeDir, executionId) {
  assert.match(executionId ?? '', /^exec_[0-9a-f]{32}$/);
  const releaseRoot = resolve(probeDir, 'release');
  const target = resolve(releaseRoot, executionId);
  assert.ok(target.startsWith(releaseRoot + '/') && !executionId.includes('..') && !executionId.includes('/'));
  return target;
}

export async function writeOwnedRelease(probeDir, executionId, nonce) {
  assert.equal(typeof nonce, 'string');
  assert.ok(nonce.length >= 16 && nonce.length <= 128);
  const target = assertReleaseTarget(probeDir, executionId);
  await writeFile(target, nonce, { flag: 'wx', mode: 0o600 });
}

export function redactHold(value) {
  if (!value || typeof value !== 'object') return value;
  const { release_nonce: nonce, ...rest } = value;
  return { ...rest, release_nonce_present: Boolean(nonce),
    release_nonce_sha256: nonce ? createHash('sha256').update(nonce).digest('hex') : null };
}

export async function abortOwnedHold(probeDir, { waitMs = 2000 } = {}) {
  const until = Date.now() + waitMs;
  while (Date.now() <= until) {
    let hold;
    try { hold = JSON.parse(await readFile(join(probeDir, 'current.json'), 'utf8')); }
    catch (error) {
      if (error.code !== 'ENOENT') throw error;
      await delay(50);
      continue;
    }
    if (hold?.execution_id && hold.release_nonce) {
      try {
        await writeOwnedRelease(probeDir, hold.execution_id, hold.release_nonce);
        return { released: true, execution_id: hold.execution_id, prompts_resent: 0 };
      } catch (error) {
        if (error.code === 'EEXIST') return { released: false, reason: 'already-released', execution_id: hold.execution_id, prompts_resent: 0 };
        throw error;
      }
    }
    await delay(50);
  }
  return { released: false, reason: 'no-hold', prompts_resent: 0 };
}

const invoked = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (!invoked) { /* imported by unit tests; native browser driver stays behind main */ }
else await main();

async function main() {
  const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
  const [namedRuntime, browse, tab, verifyFlag, ...extra] = process.argv.slice(2);
  assert.ok(isAbsolute(namedRuntime ?? '') && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length
    && (verifyFlag === undefined || verifyFlag === '--verify-existing'),
    'Usage: node native-state-smoke.mjs /absolute/current-runtime /absolute/browse <owned-tab-id> [--verify-existing]');
  const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
  const runtime = resolve(namedRuntime);
  assert.equal(current.runtime, runtime);
  assert.equal(current.verificationScenario, SCENARIO);
  assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
  const config = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
  const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
  const probeDir = join(runtime, 'probe');
  const upstream = join(root, '.context/dsh-b0/upstream');
  const { flockSync } = createRequire(join(upstream, 'packages/session/session-persistence-jsonl/package.json'))('fs-ext');
  const { scanZstdFrames } = await import(pathToFileURL(join(upstream, 'packages/session/session-persistence-jsonl/lib/types/zstd.js')).href);
  const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
  const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 4 * 1024 * 1024 });
  const rows = () => db.prepare(`SELECT r.run_id,r.attempt_id,r.status,r.error_code,r.result_json,r.tool_steps_used,r.deadline_ms,
    d.session_id,d.request_id,d.payload_json,d.payload_hash,d.attempts FROM runs r JOIN dispatch_intents d USING(run_id) ORDER BY r.rowid`).all();
  const workers = () => db.prepare('SELECT * FROM worker_executions ORDER BY rowid').all();
  const report = { kind: 'B0_NATIVE_STATE_CHAIN', runtime, tab: Number(tab), started_at: new Date().toISOString(),
    actions: [], running_live_observed: false, component_unknown_version_fallback: 'separate component evidence; not this native rejection chain',
    historical_supervisor_exits: 'OPEN / UNKNOWN; not closed by this scenario' };
  report.plugin_hashes = Object.fromEntries(await Promise.all(['index.js', 'tool.js', 'skills.js', 'client.js']
    .map(async name => [name, createHash('sha256').update(await readFile(join(current.plugin, 'lib', name))).digest('hex')])));
  async function waitFor(check, milliseconds = 20000) {
    const ok = await waitUntil(check, { budgetMs: milliseconds });
    if (!ok) throw new Error('Native state verification deadline expired');
  }
  async function waitNativeRequestComplete(requestId) {
    let summary;
    await waitFor(async () => {
      const log = await nativeLog().catch(() => []);
      summary = summarizeRequest(log, requestId);
      return nativeRequestSettled(summary) && nativeTurnHasDurableResult(log, requestId);
    });
    return summary;
  }
  async function sendWhenReady(text, previousRequestId) {
    if (previousRequestId) {
      const summary = await waitNativeRequestComplete(previousRequestId);
      report.actions.push({ type: 'wait-native-settled', request_id: previousRequestId,
        turn: summary.targetTurn, reason: summary.reason?.kind });
    }
    await waitFor(() => parseComposer(b('snapshot', '-i')).readyToFill);
    const before = parseComposer(b('snapshot', '-i'));
    assert.ok(before.readyToFill && before.inputRef && before.sendRef, 'Native composer not ready');
    b('fill', before.inputRef, text);
    await waitFor(() => parseComposer(b('snapshot', '-i')).sendEnabled);
    const after = parseComposer(b('snapshot', '-i'));
    assert.ok(after.sendEnabled && after.sendRef, 'Native send control is not enabled');
    b('click', after.sendRef);
    report.actions.push({ type: 'native-send', text, previous_request_id: previousRequestId ?? null });
  }
  function expandTools() {
    for (let i = 0; i < 8; i++) {
      const match = b('snapshot', '-i').match(/(@e\d+) \[button\] "\d+ tool calls?"(?! \[expanded\])/);
      if (!match) return;
      b('click', match[1]);
    }
    throw new Error('Tool group expansion did not settle');
  }
  function cardState() {
    return JSON.parse(b('js', `JSON.stringify({cards: [...document.querySelectorAll('.analytics-b0-card')].map(e => e.textContent),
      runStatus: [...document.querySelectorAll('[data-run-status]')].map(e => e.getAttribute('data-run-status')),
      skill: [...document.querySelectorAll('button,[role="button"]')].some(e => e.textContent.includes('Skill') && e.textContent.includes('growth-analysis-b0'))})`));
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
  async function latestProof() {
    try { const text = await readFile(join(probeDir, 'proof.jsonl'), 'utf8');
      const lines = text.split('\n').filter(Boolean);
      return lines.length ? JSON.parse(lines.at(-1)) : null;
    } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  }
  try {
    assert.equal(rows().length, verifyFlag ? 4 : 0, 'Use a fresh runtime or verify exactly four existing prompts');
    b('tab', tab); assert.equal(b('url').trim(), 'http://127.0.0.1:4318/');
    report.source_hashes = Object.fromEntries(await Promise.all([
      'backend/tests/analytics_worker_probe.py', 'backend/tests/analytics_native_probe.py',
      'scripts/dsh-b0/serve.mjs', 'scripts/dsh-b0/native-state-smoke.mjs',
    ].map(async rel => [rel, createHash('sha256').update(await readFile(join(root, rel))).digest('hex')])));
    if (verifyFlag) {
      assert.deepEqual(rows().map(row => JSON.parse(row.payload_json).native_request.content[0].text), QUESTIONS);
      Object.assign(report, verifyExistingScope());
      report.actions.push({ type: 'verify-existing', prompts_resent: 0, limited_scope: true });
      assert.equal(runningCannotBeInferredFromSuccess(rows()[0]), false);
      assert.equal(report.live_running_pass, false);
    }
    if (!verifyFlag) {
      await sendWhenReady(QUESTIONS[0], null);
      await waitFor(async () => {
        expandTools();
        const proof = await latestProof();
        const active = workers().filter(row => row.active_slot === 1);
        const ui = cardState();
        const holding = proof?.event === 'SQL_ACTIVE' && active.length === 1
          && active[0].execution_id === proof.execution_id
          && hasRunningToolCard(ui.cards);
        if (!holding) return false;
        const log = await nativeLog().catch(() => []);
        const calls = log.filter(event => event.type === 'tool/call');
        const results = log.filter(event => event.type === 'tool/result');
        if (!calls.length) return false;
        assert.equal(results.length, 0, 'running call must not already have a durable result');
        return true;
      });
      const live = await latestProof();
      const hold = redactHold(JSON.parse(await readFile(join(probeDir, 'current.json'), 'utf8')));
      assert.equal(live.event, 'SQL_ACTIVE');
      assert.equal(hold.execution_id, live.execution_id);
      assert.equal(hold.run_id, rows()[0].run_id);
      expandTools();
      const ui = cardState();
      assert.ok(hasRunningToolCard(ui.cards), 'native running requires .analytics-b0-card 合成工具运行中');
      const log = await nativeLog();
      const calls = log.filter(event => event.type === 'tool/call');
      const results = log.filter(event => event.type === 'tool/result');
      assert.ok(calls.length >= 1);
      assert.equal(results.length, 0, 'durable tool/result must not exist before release');
      const call = calls[0];
      const requestId = requestForTool(log, call.data.callId);
      assert.equal(requestId, rows()[0].request_id);
      const snapshot = b('snapshot');
      const screenshotPath = join(runtime, `native-state-running-${Date.now()}.png`);
      b('screenshot', screenshotPath);
      const snapshotPath = join(runtime, 'native-state-running-snapshot.txt');
      await writeFile(snapshotPath, snapshot, { mode: 0o600 });
      const observe = await fetch('http://127.0.0.1:4316/observe', { method: 'POST',
        headers: { authorization: `Bearer ${config.runtime_token}`, 'content-type': 'application/json' },
        body: JSON.stringify({ ...rows()[0], payload: JSON.parse(rows()[0].payload_json) }), signal: AbortSignal.timeout(5000) });
      const observed = await observe.json();
      assert.equal(observe.status, 200);
      assert.equal(observed.outcome, 'RUNNING');
      assert.equal(observed.execution_exited, false);
      report.running_live_observed = true;
      report.running = { observed_at: new Date().toISOString(),
        card_text: ui.cards.find(text => text.includes(RUNNING_TOOL_CARD)), cards: ui.cards,
        snapshot_path: snapshotPath, screenshot: screenshotPath, snapshot,
        call_id: call.data.callId, request_id: requestId, turn: call.data.turn,
        run_id: live.run_id, attempt_id: live.attempt_id, execution_id: live.execution_id,
        step_id: live.step_id, pid: live.pid, observe_outcome: observed.outcome, durable_result: false };
      report.sql_active = { execution_id: live.execution_id, run_id: live.run_id, attempt_id: live.attempt_id,
        step_id: live.step_id, pid: live.pid, observe_outcome: observed.outcome };
      const nonce = JSON.parse(await readFile(join(probeDir, 'current.json'), 'utf8')).release_nonce;
      await writeOwnedRelease(probeDir, live.execution_id, nonce);
      report.actions.push({ type: 'release-current-hold', execution_id: live.execution_id, nonce_written: true });
      await waitFor(() => rows()[0]?.status === 'SUCCEEDED');
      assert.equal(runningCannotBeInferredFromSuccess(rows()[0]), false);
      for (const index of [1, 2, 3]) {
        await sendWhenReady(QUESTIONS[index], rows()[index - 1].request_id);
        await waitFor(() => ['SUCCEEDED', 'FAILED'].includes(rows()[index]?.status));
        assert.equal(rows()[index].status, index === 3 ? 'SUCCEEDED' : 'FAILED');
        if (index !== 3) assert.equal(rows()[index].error_code, 'TOOL_FAILED');
      }
      await waitNativeRequestComplete(rows()[3].request_id);
    }
    const runs = rows();
    assert.deepEqual(runs.map(row => row.status), ['SUCCEEDED', 'FAILED', 'FAILED', 'SUCCEEDED']);
    assert.equal(runs[1].error_code, 'TOOL_FAILED');
    assert.equal(runs[2].error_code, 'TOOL_FAILED');
    assert.equal(runs[0].result_json && JSON.parse(runs[0].result_json).facts.repeat_ratio, 0.25);
    assert.equal(runs[3].result_json && JSON.parse(runs[3].result_json).facts.repeat_ratio, 0.25);
    assert.equal(runs[1].result_json, null);
    assert.equal(runs[2].result_json, null);
    for (const row of runs) {
      assert.equal(row.attempts, 1); assert.equal(row.session_id, refs.sessionId);
      const response = await fetch('http://127.0.0.1:4316/observe', { method: 'POST',
        headers: {authorization: `Bearer ${config.runtime_token}`, 'content-type': 'application/json'},
        body: JSON.stringify({...row, payload: JSON.parse(row.payload_json)}), signal: AbortSignal.timeout(5000) });
      const proof = await response.json(); assert.equal(response.status, 200); assert.equal(proof.execution_exited, true);
    }
    const log = await nativeLog();
    const calls = log.filter(event => event.type === 'tool/call');
    assert.equal(calls.length, 4); assert.equal(new Set(calls.map(event => event.data.callId)).size, 4);
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
      const failed = row === runs[1] || row === runs[2];
      assert.equal(blocks[0].isError, failed);
      if (call.data.name === 'analytics_b0_query') {
        assert.equal(Boolean(decodeFixture(result.data.meta)), !failed);
        if (failed) {
          assert.equal(row.result_json, null);
          assert.ok(!String(blocks[0].content ?? '').includes('25%'));
        } else assert.equal(JSON.parse(row.result_json).facts.repeat_ratio, 0.25);
      }
      report.tools.push({name: call.data.name, call_id: call.data.callId, request_id: requestId, run_id: row.run_id,
        attempt_id: row.attempt_id, turn: call.data.turn, is_error: blocks[0].isError,
        fixture_meta: Boolean(decodeFixture(result.data.meta))});
    }
    if (!verifyFlag) {
      assert.equal(report.tools[0].call_id, report.running.call_id);
      assert.equal(report.tools[0].request_id, report.running.request_id);
      assert.equal(report.tools[0].turn, report.running.turn);
      assert.equal(report.tools[0].run_id, report.running.run_id);
      assert.equal(report.tools[0].attempt_id, report.running.attempt_id);
      assert.equal(report.tools[0].is_error, false);
      assert.equal(report.running.durable_result, false);
    }
    const recorded = workers();
    assert.equal(recorded.length, 4);
    for (const worker of recorded) {
      assert.equal(worker.state, 'EXITED'); assert.equal(worker.active_slot, null); assert.ok(worker.pid > 0);
      const failed = worker.run_id === runs[1].run_id || worker.run_id === runs[2].run_id;
      assert.equal(worker.error_code, failed ? 'TOOL_FAILED' : null);
      const fd = openSync(join(runtime, 'kernel/workers', worker.execution_id, '.lease'), constants.O_RDONLY | constants.O_NOFOLLOW);
      try { const info = fstatSync(fd); assert.deepEqual([info.dev, info.ino], [worker.lease_dev, worker.lease_ino]); flockSync(fd, 'exnb'); }
      finally { closeSync(fd); }
    }
    report.runs = runs.map(({run_id, attempt_id, status, error_code, tool_steps_used}) => ({run_id, attempt_id, status, error_code, tool_steps_used}));
    report.workers = recorded.map(({execution_id, run_id, state, pid, exit_code, error_code}) => ({execution_id, run_id, state, pid, exit_code, error_code}));
    expandTools();
    const before = cardState();
    assert.equal(before.cards.filter(text => text.includes('100 位客户中 25 位复购')).length, 2);
    assert.equal(before.cards.filter(text => text.includes('B0 工具失败')).length, 2);
    assert.ok(before.cards.filter(text => text.includes('B0 工具失败')).every(text => !text.includes('25%')));
    assert.ok(before.cards.every(text => !text.includes('版本不支持')),
      'native rejection is a failure card, not the component unknown-version fallback');
    report.before_refresh = { cards: before.cards, runStatus: before.runStatus };
    b('reload'); await waitFor(() => b('snapshot').includes(QUESTIONS[3])); expandTools();
    const after = cardState();
    assert.equal(after.cards.filter(text => text.includes('100 位客户中 25 位复购')).length, 2);
    assert.equal(after.cards.filter(text => text.includes('B0 工具失败')).length, 2);
    assert.deepEqual(rows(), runs);
    const refreshedLog = await nativeLog();
    assert.deepEqual(refreshedLog.filter(event => ['tool/call', 'tool/result'].includes(event.type)),
      log.filter(event => ['tool/call', 'tool/result'].includes(event.type)));
    report.refresh = { cards_preserved: true, new_runs: 0, same_call_ids: true };
    report.after_refresh = b('snapshot');
    await writeFile(join(runtime, 'native-state-snapshot.txt'), report.after_refresh, { mode: 0o600 });
    report.status = 'PASS';
  } catch (error) {
    report.status = 'FAIL'; report.error = String(error.message).replace(/([?&](?:token|b0)=)[A-Za-z0-9_-]+/g, '$1[REDACTED]').slice(0, 1000);
    process.exitCode = 1;
    if (!verifyFlag) {
      const abort = await abortOwnedHold(probeDir);
      report.actions.push({ type: 'abort-hold-on-error', released: abort.released, reason: abort.reason,
        execution_id: abort.execution_id, prompts_resent: 0 });
    }
  } finally {
    db.close();
    report.completed_at = new Date().toISOString();
    const path = join(runtime, `native-state-evidence-${Date.now()}.json`);
    await writeFile(path, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    console.log(JSON.stringify({ status: report.status, error: report.error, runs: report.runs,
      running_live_observed: report.running_live_observed, limited_scope: report.limited_scope === true,
      screenshot: report.running?.screenshot, report_path: path }));
  }
}
