/** Finite dual-session native query driver. Real SQL only; mock never fabricates results. */
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
import { summarizeRequest, requestForTool } from '../../dsh-plugins/analytics-workbench/src/native-evidence.mjs';
import { decodeQueryReceipt } from '../../dsh-plugins/analytics-workbench/src/query-model.mjs';
import {
  parseComposer, nativeRequestSettled, nativeTurnHasDurableResult, waitUntil,
} from './native-state-smoke.mjs';
import {
  QUESTIONS, QUERY_CARD_EXPECT, QUERY_SESSION_IDS, QUERY_TOOL_NAME, SCENARIO,
  bindListedSessions, cardHasForeignDays, cardShowsQuery, parseNewSessionButtonRef, parseTreeitemRef,
  queryMockScript, queryRequest, sessionReadyWithoutForeign, sessionSwitchPlan,
} from './query-scenario.mjs';

export { QUESTIONS, QUERY_SESSION_IDS, SCENARIO, queryMockScript, queryRequest };

const invoked = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (!invoked) { /* imported by unit tests; native browser driver stays behind main */ }
else await main();

async function main() {
  const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
  const [namedRuntime, browse, tab, verifyFlag, ...extra] = process.argv.slice(2);
  assert.ok(isAbsolute(namedRuntime ?? '') && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length
    && (verifyFlag === undefined || verifyFlag === '--verify-existing'),
    'Usage: node native-query-smoke.mjs /absolute/current-runtime /absolute/browse <owned-tab-id> [--verify-existing]');
  const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
  const runtime = resolve(namedRuntime);
  assert.equal(current.runtime, runtime);
  assert.equal(current.verificationScenario, SCENARIO);
  assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
  const config = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
  const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
  assert.equal(config.family, 'channel_followup');
  assert.deepEqual(refs.sessionIds, [...QUERY_SESSION_IDS]);
  const upstream = join(root, '.context/dsh-b0/upstream');
  const { flockSync } = createRequire(join(upstream, 'packages/session/session-persistence-jsonl/package.json'))('fs-ext');
  const { scanZstdFrames } = await import(pathToFileURL(join(upstream, 'packages/session/session-persistence-jsonl/lib/types/zstd.js')).href);
  const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
  const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 4 * 1024 * 1024 });
  const rows = () => db.prepare(`SELECT r.run_id,r.attempt_id,r.status,r.error_code,r.result_json,r.tool_steps_used,r.deadline_ms,
    d.session_id,d.request_id,d.payload_json,d.payload_hash,d.attempts FROM runs r JOIN dispatch_intents d USING(run_id) ORDER BY r.rowid`).all();
  const workers = () => db.prepare('SELECT * FROM worker_executions ORDER BY rowid').all();
  const report = { kind: 'QUERY_NATIVE_DUAL_SESSION', runtime, tab: Number(tab), started_at: new Date().toISOString(),
    actions: [], synthetic: true, finite_mock: true, real_business: false, paid_model: false };
  report.plugin_hashes = Object.fromEntries(await Promise.all(['index.js', 'tool.js', 'skills.js', 'client.js']
    .map(async name => [name, createHash('sha256').update(await readFile(join(current.plugin, 'lib', name))).digest('hex')])));
  async function waitFor(check, milliseconds = 45000) {
    const ok = await waitUntil(check, { budgetMs: milliseconds });
    if (!ok) throw new Error('Native query verification deadline expired');
  }
  async function nativeLog(sessionId) {
    const sessions = join(runtime, 'harness/sessions');
    for (const project of await readdir(sessions, { withFileTypes: true })) {
      if (!project.isDirectory()) continue;
      const file = join(sessions, project.name, sessionId, 'session.v2.jsonl.zstd');
      let bytes;
      try { bytes = await readFile(file); } catch (error) { if (error.code === 'ENOENT') continue; throw error; }
      const scan = scanZstdFrames(bytes);
      assert.equal(scan.tornStart, undefined);
      const lines = scan.frames.flatMap(({start, end}) => zstdDecompressSync(bytes.subarray(start, end)).toString('utf8')
        .split('\n').filter(Boolean).map(JSON.parse));
      const header = lines.find(row => row.type === 'session');
      assert.equal(header.id, sessionId);
      return lines.filter(row => row.type !== 'session');
    }
    throw new Error(`Native durable journal missing for ${sessionId}`);
  }
  async function waitNativeRequestComplete(sessionId, requestId) {
    let summary;
    await waitFor(async () => {
      const log = await nativeLog(sessionId).catch(() => []);
      summary = summarizeRequest(log, requestId);
      return nativeRequestSettled(summary) && nativeTurnHasDurableResult(log, requestId);
    });
    return summary;
  }
  async function sendWhenReady(text, sessionId, previousRequestId) {
    if (previousRequestId) {
      const summary = await waitNativeRequestComplete(sessionId, previousRequestId);
      report.actions.push({ type: 'wait-native-settled', session_id: sessionId, request_id: previousRequestId,
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
    report.actions.push({ type: 'native-send', text, session_id: sessionId, previous_request_id: previousRequestId ?? null });
  }
  function expandTools() {
    for (let i = 0; i < 8; i++) {
      const match = b('snapshot', '-i').match(/(@e\d+) \[button\] "\d+ tool calls?"(?! \[expanded\])/);
      if (!match) return;
      b('click', match[1]);
    }
    throw new Error('Tool group expansion did not settle');
  }
  function listRegisteredSessions() {
    const raw = b('js', `JSON.stringify((() => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/session/list', false);
      xhr.setRequestHeader('content-type', 'application/json');
      xhr.send(JSON.stringify({
        type: 'client-request', rpcId: 'query-list-' + Date.now(), method: 'session/list',
        payload: { args: { _request: {} } },
      }));
      return JSON.parse(xhr.responseText);
    })())`);
    const envelope = JSON.parse(raw);
    assert.equal(envelope.result?.ok, true, 'session/list RPC was not accepted');
    const listed = bindListedSessions(envelope.result.value.items, [...QUERY_SESSION_IDS]);
    assert.ok(listed, 'session/list must expose exactly the two registered sessions');
    return listed;
  }
  function clickNewSessionButton() {
    const ref = parseNewSessionButtonRef(b('snapshot', '-i'));
    if (ref) { b('click', ref); return 'snapshot'; }
    const clicked = JSON.parse(b('js', `JSON.stringify((() => {
      const node = [...document.querySelectorAll('button,[role="button"]')].find(element => {
        const label = ((element.getAttribute('aria-label') || '') + ' ' + (element.textContent || '')).trim();
        return /New session/i.test(label) || label.includes('新会话') || label.includes('新建会话');
      });
      if (!node) return false;
      node.click();
      return true;
    })())`));
    assert.equal(clicked, true, 'Visible New session control was not found');
    return 'dom';
  }
  function clickTreeitem(title) {
    const ref = parseTreeitemRef(b('snapshot', '-i'), title);
    if (ref) { b('click', ref); return 'snapshot'; }
    const clicked = JSON.parse(b('js', `JSON.stringify((() => {
      const node = [...document.querySelectorAll('[role="treeitem"]')]
        .find(element => (element.textContent || '').includes(${JSON.stringify(title)}));
      if (!node) return false;
      node.click();
      return true;
    })())`));
    assert.equal(clicked, true, `Visible treeitem for title was not found`);
    return 'dom';
  }
  function selectSession(sessionId) {
    const current = cardState().session;
    const listed = listRegisteredSessions();
    const plan = sessionSwitchPlan(listed, current ?? QUERY_SESSION_IDS[0], sessionId);
    assert.notEqual(plan.action, 'reject', plan.reason ?? 'session switch rejected');
    if (plan.action === 'noop') {
      report.actions.push({ type: 'native-session-switch', session_id: sessionId, via: 'already-current', listed });
      return;
    }
    const via = plan.action === 'new-session-button' ? clickNewSessionButton() : clickTreeitem(plan.title);
    report.actions.push({ type: 'native-session-switch', session_id: sessionId, via, action: plan.action, listed });
  }
  function cardState() {
    return JSON.parse(b('js', `JSON.stringify({
      cards: [...document.querySelectorAll('.analytics-query-card,[data-testid="analytics-query-tool-result"]')].map(e => e.textContent),
      days: [...document.querySelectorAll('[data-observation-days]')].map(e => e.getAttribute('data-observation-days')),
      runIds: [...document.querySelectorAll('[data-run-id]')].map(e => e.getAttribute('data-run-id')),
      stepIds: [...document.querySelectorAll('[data-step-id]')].map(e => e.getAttribute('data-step-id')),
      runStatus: [...document.querySelectorAll('[data-run-status]')].map(e => e.getAttribute('data-run-status')),
      session: document.querySelector('[data-session-id]')?.getAttribute('data-session-id') ?? null,
    })`));
  }
  function inventory(callIds) {
    return {
      runs: rows().map(row => row.run_id),
      steps: db.prepare('SELECT COUNT(*) AS n FROM steps').get().n,
      workers: workers().map(row => row.execution_id),
      native_calls: [...callIds],
    };
  }
  async function nativeCallIds() {
    const ids = [];
    for (const sessionId of QUERY_SESSION_IDS) {
      const log = await nativeLog(sessionId);
      for (const event of log.filter(row => row.type === 'tool/call' && row.data.name === QUERY_TOOL_NAME)) {
        ids.push(event.data.callId);
      }
    }
    return ids;
  }
  async function waitVisibleQuery(sessionId, expect, foreignDays) {
    expandTools();
    await waitFor(() => {
      const ui = cardState();
      return sessionReadyWithoutForeign(ui, sessionId, foreignDays) && cardShowsQuery(ui, expect);
    });
    const ui = cardState();
    assert.equal(ui.session, sessionId);
    assert.equal(cardHasForeignDays(ui, foreignDays), false);
    assert.equal(cardShowsQuery(ui, expect), true);
    return ui;
  }
  async function waitSessionWithoutForeign(sessionId, foreignDays) {
    await waitFor(() => sessionReadyWithoutForeign(cardState(), sessionId, foreignDays));
    const listed = listRegisteredSessions();
    assert.equal(listed.length, 2);
    assert.equal(cardState().session, sessionId);
    assert.equal(cardHasForeignDays(cardState(), foreignDays), false);
    return listed;
  }
  try {
    assert.equal(rows().length, verifyFlag ? 2 : 0, 'Use a fresh runtime or verify exactly two existing prompts');
    b('tab', tab); assert.equal(b('url').trim(), 'http://127.0.0.1:4318/');
    if (verifyFlag) {
      assert.deepEqual(rows().map(row => JSON.parse(row.payload_json).native_request.content[0].text), [...QUESTIONS]);
      report.actions.push({ type: 'verify-existing', prompts_resent: 0, limited_scope: true });
    }
    if (!verifyFlag) {
      await sendWhenReady(QUESTIONS[0], QUERY_SESSION_IDS[0], null);
      await waitFor(() => rows().some(row => row.session_id === QUERY_SESSION_IDS[0] && row.status === 'SUCCEEDED'));
      const rowA = rows().find(row => row.session_id === QUERY_SESSION_IDS[0]);
      await waitNativeRequestComplete(QUERY_SESSION_IDS[0], rowA.request_id);
      await waitVisibleQuery(QUERY_SESSION_IDS[0], { ...QUERY_CARD_EXPECT[30], runId: rowA.run_id }, 60);
      selectSession(QUERY_SESSION_IDS[1]);
      await waitSessionWithoutForeign(QUERY_SESSION_IDS[1], 30);
      await sendWhenReady(QUESTIONS[1], QUERY_SESSION_IDS[1], null);
      await waitFor(() => rows().filter(row => row.status === 'SUCCEEDED').length === 2);
      const rowB = rows().find(row => row.session_id === QUERY_SESSION_IDS[1]);
      await waitNativeRequestComplete(QUERY_SESSION_IDS[1], rowB.request_id);
      await waitVisibleQuery(QUERY_SESSION_IDS[1], { ...QUERY_CARD_EXPECT[60], runId: rowB.run_id }, 30);
    }
    const runs = rows();
    assert.equal(runs.length, 2);
    assert.equal(runs[0].session_id, QUERY_SESSION_IDS[0]);
    assert.equal(runs[1].session_id, QUERY_SESSION_IDS[1]);
    assert.notEqual(runs[0].run_id, runs[1].run_id);
    assert.notEqual(runs[0].request_id, runs[1].request_id);
    const facts = runs.map(row => JSON.parse(row.result_json).facts);
    assert.equal(facts[0].observation_days, 30);
    assert.equal(facts[1].observation_days, 60);
    assert.notEqual(facts[0].totals.channel_repeat_count, facts[1].totals.channel_repeat_count);
    const logs = {};
    const tools = [];
    for (const row of runs) {
      const log = await nativeLog(row.session_id);
      logs[row.session_id] = log;
      const calls = log.filter(event => event.type === 'tool/call' && event.data.name === QUERY_TOOL_NAME);
      const results = log.filter(event => event.type === 'tool/result');
      assert.equal(calls.length, 1);
      const call = calls[0];
      assert.equal(requestForTool(log, call.data.callId), row.request_id);
      const result = results.find(event => event.data.message.content.some(block => block.type === 'tool-result' && block.toolCallId === call.data.callId));
      assert.ok(result);
      const receipt = decodeQueryReceipt(result.data.meta);
      assert.ok(receipt);
      assert.equal(receipt.run_id, row.run_id);
      assert.equal(receipt.result.facts.observation_days, facts[runs.indexOf(row)].observation_days);
      assert.notEqual(receipt.step_id, tools[0]?.step_id);
      tools.push({ session_id: row.session_id, run_id: row.run_id, request_id: row.request_id,
        call_id: call.data.callId, step_id: receipt.step_id, observation_days: receipt.result.facts.observation_days,
        result_ref: `${receipt.run_id}/${receipt.step_id}` });
    }
    assert.notEqual(tools[0].call_id, tools[1].call_id);
    assert.notEqual(tools[0].result_ref, tools[1].result_ref);
    const recorded = workers();
    assert.equal(recorded.length, 2);
    for (const worker of recorded) {
      assert.equal(worker.state, 'EXITED');
      assert.equal(worker.active_slot, null);
      assert.equal(worker.exit_code, 0);
      assert.ok(worker.pid > 0);
      const fd = openSync(join(runtime, 'kernel/workers', worker.execution_id, '.lease'), constants.O_RDONLY | constants.O_NOFOLLOW);
      try { const info = fstatSync(fd); assert.deepEqual([info.dev, info.ino], [worker.lease_dev, worker.lease_ino]); flockSync(fd, 'exnb'); }
      finally { closeSync(fd); }
    }
    report.runs = runs.map(({run_id, attempt_id, status, session_id, request_id}) => ({run_id, attempt_id, status, session_id, request_id}));
    report.tools = tools;
    selectSession(QUERY_SESSION_IDS[0]);
    await waitSessionWithoutForeign(QUERY_SESSION_IDS[0], 60);
    const restored = await waitVisibleQuery(QUERY_SESSION_IDS[0],
      { ...QUERY_CARD_EXPECT[30], runId: runs[0].run_id, stepId: tools[0].step_id }, 60);
    report.restore_a = { observation_days: 30, cards: restored.cards };
    const baseline = inventory(await nativeCallIds());
    b('reload');
    await waitFor(() => parseComposer(b('snapshot', '-i')).readyToFill);
    await waitVisibleQuery(QUERY_SESSION_IDS[0],
      { ...QUERY_CARD_EXPECT[30], runId: runs[0].run_id, stepId: tools[0].step_id }, 60);
    assert.deepEqual(inventory(await nativeCallIds()), baseline);
    selectSession(QUERY_SESSION_IDS[1]);
    await waitSessionWithoutForeign(QUERY_SESSION_IDS[1], 30);
    await waitVisibleQuery(QUERY_SESSION_IDS[1],
      { ...QUERY_CARD_EXPECT[60], runId: runs[1].run_id, stepId: tools[1].step_id }, 30);
    assert.deepEqual(inventory(await nativeCallIds()), baseline);
    selectSession(QUERY_SESSION_IDS[0]);
    await waitSessionWithoutForeign(QUERY_SESSION_IDS[0], 60);
    await waitVisibleQuery(QUERY_SESSION_IDS[0],
      { ...QUERY_CARD_EXPECT[30], runId: runs[0].run_id, stepId: tools[0].step_id }, 60);
    assert.deepEqual(inventory(await nativeCallIds()), baseline);
    report.refresh = { new_runs: 0, new_steps: 0, new_workers: 0, new_native_calls: 0, inventory: baseline };
    report.status = 'PASS';
  } catch (error) {
    report.status = 'FAIL';
    report.error = String(error.message).replace(/([?&](?:token|b0)=)[A-Za-z0-9_-]+/g, '$1[REDACTED]').slice(0, 1000);
    process.exitCode = 1;
  } finally {
    db.close();
    report.completed_at = new Date().toISOString();
    const path = join(runtime, `native-query-evidence-${Date.now()}.json`);
    await writeFile(path, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    console.log(JSON.stringify({ status: report.status, error: report.error, runs: report.runs,
      tools: report.tools, refresh: report.refresh, report_path: path }));
  }
}
