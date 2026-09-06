/** Verify the current owned B0 run against TWO durable stores and live exit proof.
 * Native prompts/stop are exercised through the browser, not synthesized here.
 * --restart-active is an explicit crash test of the supervisor-owned FastAPI child.
 */
import assert from 'node:assert/strict';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { openSync, fstatSync, closeSync, constants } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, join, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { DatabaseSync } from 'node:sqlite';
import { zstdDecompressSync } from 'node:zlib';
import { execFileSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { decodeFixture } from '../../dsh-plugins/analytics-workbench/src/model.mjs';
import { summarizeRequest } from '../../dsh-plugins/analytics-workbench/src/native-evidence.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const [mode, namedRuntime] = process.argv.slice(2);
assert.ok(['--two-questions', '--restart-active', '--restart-host', '--final', '--extended-final'].includes(mode));
assert.ok(namedRuntime, 'Explicit current runtime path required');
const currentPath = join(root, '.context/dsh-b0/current.json');
const current = JSON.parse(await readFile(currentPath, 'utf8'));
const runtime = resolve(namedRuntime);
assert.equal(current.runtime, runtime);
assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
const config = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
assert.equal(refs.sessionId, 'session-b0-synthetic-primary');
const upstream = join(root, '.context/dsh-b0/upstream');
const { flockSync } = createRequire(join(upstream, 'packages/session/session-persistence-jsonl/package.json'))('fs-ext');
const { scanZstdFrames } = await import(pathToFileURL(join(upstream, 'packages/session/session-persistence-jsonl/lib/types/zstd.js')).href);
const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
const report = { schema_version: 'analytics-b0-native-kernel/v1', stage: mode, status: 'RUNNING',
  runtime: relative(root, runtime), source_sha: current.pinned, synthetic_only: true,
  started_at: new Date().toISOString(), layers: ['FastAPI SQLite', 'native DSH durable journal', 'private Host whenIdle + flush proof'],
  limitations: ['Only a tiny read-only synthetic DuckDB and official stub provider; not real business or model evidence.',
    'Browser sends/stop and responsive screenshots are separate evidence; this script does not click UI.'] };

const rows = () => db.prepare(`SELECT r.run_id, r.attempt_id, r.status, r.error_code, r.deadline_ms, r.tool_steps_used,
  r.original_202, r.result_json, d.session_id, d.request_id, d.payload_json, d.payload_hash, d.attempts
  FROM runs r JOIN dispatch_intents d USING(run_id) ORDER BY r.rowid`).all();
const intentOf = row => ({ run_id: row.run_id, attempt_id: row.attempt_id, session_id: row.session_id, request_id: row.request_id,
  payload: JSON.parse(row.payload_json), payload_hash: row.payload_hash, deadline_ms: row.deadline_ms });
async function request(port, path, body, token = config.gateway_token) {
  const response = await fetch(`http://127.0.0.1:${port}${path}`, { method: body === undefined ? 'GET' : 'POST',
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(3000), redirect: 'error' });
  return { status: response.status, value: await response.json() };
}
async function waitFor(read, timeout = 12000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    try { const result = await read(); if (result) return result; } catch { /* bounded restart gap */ }
    await delay(100);
  }
  throw new Error('bounded B0 evidence wait expired');
}
function signalOwned(pid, commandPart, signal) {
  const command = execFileSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).trim();
  assert.ok(command.includes(commandPart), 'Owned process identity changed');
  const cwd = execFileSync('lsof', ['-a', '-p', String(pid), '-d', 'cwd', '-Fn'], { encoding: 'utf8' });
  assert.ok(cwd.split('\n').includes(`n${root}`), 'Process no longer owns this workspace');
  process.kill(pid, signal);
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
    const lines = scan.frames.flatMap(({ start, end }) => zstdDecompressSync(bytes.subarray(start, end)).toString('utf8')
      .split('\n').filter(Boolean).map(line => JSON.parse(line)));
    const header = lines.find(row => row.type === 'session');
    assert.equal(header.id, refs.sessionId);
    assert.equal(header.cwd, join(runtime, 'synthetic-workspace'));
    return { path: relative(runtime, file), events: lines.filter(row => row.type !== 'session') };
  }
  throw new Error('native journal not found');
}
try {
  if (mode === '--restart-active' || mode === '--restart-host') {
    const active = rows().filter(row => row.status === 'RUNNING');
    assert.equal(active.length, 1, 'Crash test requires exactly one currently running native question');
    const before = active[0];
    await waitFor(async () => {
      const live = await request(4316, '/observe', intentOf(before), config.runtime_token);
      return live.value.execution_exited === false && live.value.outcome === 'RUNNING';
    });
    const hostCrash = mode === '--restart-host';
    signalOwned(current.supervisorPid, 'scripts/dsh-b0/serve.mjs --python ', hostCrash ? 'SIGUSR2' : 'SIGUSR1');
    const afterCurrent = await waitFor(async () => {
      const value = JSON.parse(await readFile(currentPath, 'utf8'));
      if (value.runtime !== runtime) return false;
      if (hostCrash ? (value.hostGeneration <= current.hostGeneration || value.hostReadyGeneration !== value.hostGeneration)
        : value.kernelGeneration <= current.kernelGeneration) return false;
      const health = await request(4315, '/internal/native/context');
      const resumed = rows().find(row => row.run_id === before.run_id);
      return health.status === 200 && health.value.ready && resumed.status === (hostCrash ? 'FAILED' : 'RUNNING') ? value : false;
    }, hostCrash ? 45000 : 12000);
    const after = rows().find(row => row.run_id === before.run_id);
    for (const key of ['run_id', 'attempt_id', 'session_id', 'request_id', 'deadline_ms', 'tool_steps_used', 'attempts']) assert.equal(after[key], before[key]);
    const log = await nativeLog();
    assert.equal(log.events.filter(event => event.type === 'user/message' && event.data.source?.rpcId === before.request_id).length, 1);
    if (hostCrash) {
      assert.equal(afterCurrent.kernelPid, current.kernelPid);
      assert.equal(after.error_code, 'EXECUTION_UNKNOWN');
      assert.equal(summarizeRequest(log.events, before.request_id).reason.kind, 'interrupted');
      const exit = await request(4316, '/observe', intentOf(after), config.runtime_token);
      assert.equal(exit.value.execution_exited, true);
      assert.equal(exit.value.outcome, 'FAILED');
      const gateway = JSON.parse(await readFile(join(runtime, 'gateway-private.json'), 'utf8'));
      signalOwned(gateway.pid, 'scripts/dsh-b0/gateway.mjs', 'SIGUSR1');
      await waitFor(async () => JSON.parse(await readFile(join(runtime, 'gateway-private.json'), 'utf8'))
        .upstream_generation === afterCurrent.hostGeneration);
      report.host_owned_exit = JSON.parse(await readFile(join(runtime, `host-restart-${afterCurrent.hostGeneration}.json`), 'utf8'));
      assert.equal(report.host_owned_exit.original_owned_exit.signal, 'SIGKILL');
    }
    report.recovery = { run_id: before.run_id, attempt_id: before.attempt_id, request_id: before.request_id,
      component: hostCrash ? 'DSH_HOST' : 'FASTAPI',
      before_pid: hostCrash ? current.childPid : current.kernelPid,
      after_pid: hostCrash ? afterCurrent.childPid : afterCurrent.kernelPid,
      generations: hostCrash ? [current.hostGeneration, afterCurrent.hostGeneration] : [current.kernelGeneration, afterCurrent.kernelGeneration],
      original_deadline_preserved: true, original_attempt_preserved: true, original_dispatch_count: after.attempts,
      native_user_messages: 1, status_after_recovery: after.status };
  } else {
    const expected = mode === '--two-questions' ? ['SUCCEEDED', 'SUCCEEDED']
      : ['SUCCEEDED', 'SUCCEEDED', 'CANCELLED', 'SUCCEEDED', 'FAILED', ...(mode === '--extended-final' ? ['FAILED', 'SUCCEEDED'] : [])];
    const runs = rows();
    assert.deepEqual(runs.map(row => row.status), expected);
    const log = await nativeLog();
    const advertised = log.events.filter(event => event.type === 'request/header').flatMap(event => event.data.header.tools.map(tool => tool.name));
    assert.deepEqual([...new Set(advertised)].sort(), ['analytics_b0_query', 'analytics_b0_skill_resource', 'skill']);
    report.advertised_tools = [...new Set(advertised)].sort();
    const callIds = log.events.filter(event => event.type === 'tool/call').map(event => event.data.callId);
    assert.equal(new Set(callIds).size, callIds.length, 'Native session requires unique tool-call identities across turns');
    report.native_tool_call_ids_unique = true;
    report.native_journal = log.path;
    report.runs = [];
    for (const row of runs) {
      assert.equal(row.attempts, 1);
      assert.equal(row.session_id, refs.sessionId);
      assert.equal(log.events.filter(event => event.type === 'user/message' && event.data.source?.rpcId === row.request_id).length, 1);
      const summary = summarizeRequest(log.events, row.request_id);
      const exit = await request(4316, '/observe', intentOf(row), config.runtime_token);
      assert.equal(exit.value.execution_exited, true);
      const snapshot = await request(4315, `/api/v1/analytics/runs/${row.run_id}`);
      assert.equal(snapshot.value.diagnostics.execution_active, false);
      if (row.status === 'SUCCEEDED') {
        assert.equal(summary.reason.kind, 'completed');
        assert.equal(row.tool_steps_used, 1);
        assert.equal(JSON.parse(row.result_json).facts.repeat_ratio, 0.25);
        const tool = log.events.find(event => event.type === 'tool/result' && event.data.turn === summary.targetTurn);
        assert.ok(decodeFixture(tool?.data.meta));
        const workers = db.prepare('SELECT * FROM worker_executions WHERE run_id=?').all(row.run_id);
        assert.equal(workers.length, 1);
        const worker = workers[0];
        assert.equal(worker.state, 'EXITED');
        assert.equal(worker.exit_code, 0);
        assert.equal(worker.error_code, null);
        assert.equal(worker.active_slot, null);
        assert.match(worker.execution_id, /^exec_[a-f0-9]{32}$/);
        const fd = openSync(join(runtime, 'kernel/workers', worker.execution_id, '.lease'), constants.O_RDONLY | constants.O_NOFOLLOW);
        try {
          const info = fstatSync(fd);
          assert.deepEqual([info.dev, info.ino], [worker.lease_dev, worker.lease_ino]);
          flockSync(fd, 'exnb'); // Independent physical lease proof, no PID adoption.
        } finally { closeSync(fd); }
        const metrics = JSON.parse(worker.metrics_json);
        assert.equal(metrics.settings.access_mode.toLowerCase(), 'read_only');
        assert.equal(metrics.settings.enable_external_access, 'false');
        assert.ok(metrics.rss_peak_bytes > 0 && metrics.rss_peak_bytes <= 1024 * 1024 * 1024);
        report.worker_exits ??= [];
        report.worker_exits.push({ run_id: row.run_id, step_id: worker.step_id, execution_id: worker.execution_id,
          independently_released_lease: true, exit_code: worker.exit_code, metrics });
      }
      if (row.status === 'CANCELLED') {
        assert.deepEqual(summary.reason, { kind: 'aborted', reason: { kind: 'user' } });
        const receipt = db.prepare("SELECT response_json FROM idempotency WHERE operation='run:cancel' AND target=?").get(row.run_id);
        assert.ok(receipt, 'Native stop must reach the FastAPI authority');
        const cancelling = JSON.parse(receipt.response_json);
        assert.equal(cancelling.status, 'CANCELLING');
        assert.equal(cancelling.diagnostics.execution_active, true, 'Cancel receipt must retain its original execution slot');
        report.cancel_receipt = { run_id: row.run_id, status: 'CANCELLING', original_execution_slot_retained: true };
      }
      if (row.status === 'FAILED') {
        assert.equal(summary.reason.kind, row.error_code === 'EXECUTION_UNKNOWN' ? 'interrupted' : 'error');
        assert.equal(row.tool_steps_used, 0);
      }
      report.runs.push({ run_id: row.run_id, attempt_id: row.attempt_id, request_id: row.request_id, status: row.status,
        native_turn: summary.targetTurn, native_outcome: summary.reason.kind, tool_steps_used: row.tool_steps_used,
        dispatch_attempts: row.attempts, execution_exit_confirmed: true });
    }
    // Replaying the native original must return the ORIGINAL 202, not replace
    // it with the current terminal snapshot or start another native prompt.
    const first = runs[0];
    const original = JSON.parse(first.payload_json).native_request;
    const replay = await request(4315, '/internal/native/prompt', original);
    assert.equal(replay.status, 202);
    assert.deepEqual(replay.value, JSON.parse(first.original_202));
    const conflict = await request(4315, '/internal/native/prompt', { ...original, content: [{ type: 'text', text: 'changed synthetic input' }] });
    assert.equal(conflict.status, 409);
    assert.equal(rows().length, runs.length);
    const afterLog = await nativeLog();
    // Native Skill discovery and fresh backend context are also user-role
    // messages, but are not browser submissions. Count the RPC-backed input.
    assert.equal(afterLog.events.filter(event => event.type === 'user/message'
      && event.data.source?.kind === 'user' && typeof event.data.source?.rpcId === 'string').length, runs.length);
    report.replay = { original_202: true, changed_payload_409: true, new_run_count: 0, new_native_prompt_count: 0 };
  }
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  report.error = String(error.message).replaceAll(config.gateway_token, '[REDACTED]').replaceAll(config.runtime_token, '[REDACTED]').slice(0, 700);
  process.exitCode = 1;
} finally {
  db.close();
  report.completed_at = new Date().toISOString();
  const output = join(runtime, `kernel-native-${mode.slice(2)}-${Date.now()}.json`);
  await writeFile(output, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  console.log(JSON.stringify({ ...report, report_path: relative(root, output) }));
}
