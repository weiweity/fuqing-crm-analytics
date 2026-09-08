/** Dual-session native-query-fault driver. In-flight browser cancel + unknown_schema. */
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
import { historicalSupervisorRemainsUnknown, textLeaksQueryFacts, workerReleased } from '../../dsh-plugins/analytics-workbench/src/query-fault.mjs';
import {
  parseComposer, nativeRequestSettled, nativeTurnHasDurableResult, waitUntil,
} from './native-state-smoke.mjs';
import {
  QUERY_CARD_EXPECT, QUERY_SESSION_IDS, QUERY_TOOL_NAME,
  bindListedSessions, cardHasForeignDays, cardShowsQuery, parseNewSessionButtonRef, parseTreeitemRef,
  sessionReadyWithoutForeign, sessionSwitchPlan,
} from './query-scenario.mjs';
import {
  FAIL_CARD_MARKERS, FAULT_QUESTIONS, FAULT_SCENARIO, QUERY_FAULT_PROBE_SEQUENCE,
  cardShowsFault, historicalSupervisorRecord, parseQueryCancelRef, parseStopGeneratingRef,
  sqlHoldObserved,
} from './native-query-fault-scenario.mjs';

export { FAULT_QUESTIONS, QUERY_SESSION_IDS, FAULT_SCENARIO };

const invoked = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (!invoked) { /* imported by unit tests; native browser driver stays behind main */ }
else await main();

async function main() {
  const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
  const [namedRuntime, browse, tab, ...extra] = process.argv.slice(2);
  assert.ok(isAbsolute(namedRuntime ?? '') && isAbsolute(browse ?? '') && /^[1-9][0-9]*$/.test(tab ?? '') && !extra.length,
    'Usage: node native-query-fault-smoke.mjs /absolute/current-runtime /absolute/browse <owned-tab-id>');
  const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
  const runtime = resolve(namedRuntime);
  assert.equal(current.runtime, runtime);
  assert.equal(current.verificationScenario, FAULT_SCENARIO);
  assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
  const config = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
  const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
  assert.equal(config.family, 'channel_followup');
  assert.deepEqual(refs.sessionIds, [...QUERY_SESSION_IDS]);
  const probeDir = join(runtime, 'probe');
  const sequence = JSON.parse(await readFile(join(probeDir, 'sequence.json'), 'utf8'));
  assert.deepEqual(sequence, [...QUERY_FAULT_PROBE_SEQUENCE]);
  assert.ok(!sequence.includes('illegal_facts'));
  const upstream = join(root, '.context/dsh-b0/upstream');
  const { flockSync } = createRequire(join(upstream, 'packages/session/session-persistence-jsonl/package.json'))('fs-ext');
  const { scanZstdFrames } = await import(pathToFileURL(join(upstream, 'packages/session/session-persistence-jsonl/lib/types/zstd.js')).href);
  const db = new DatabaseSync(join(runtime, 'kernel/runs.sqlite3'), { readOnly: true });
  const b = (...args) => execFileSync(browse, args, { cwd: root, encoding: 'utf8', timeout: 20000, maxBuffer: 4 * 1024 * 1024 });
  function readDb(fn) {
    for (let i = 0; i < 25; i++) {
      try { return fn(); } catch (error) {
        if (!/locked|busy/i.test(String(error?.message)) || i === 24) throw error;
      }
    }
  }
  const rows = () => readDb(() => db.prepare(`SELECT r.run_id,r.attempt_id,r.status,r.error_code,r.result_json,r.tool_steps_used,r.deadline_ms,r.version,
    d.session_id,d.request_id,d.payload_json,d.payload_hash,d.attempts FROM runs r JOIN dispatch_intents d USING(run_id) ORDER BY r.rowid`).all());
  const workers = () => readDb(() => db.prepare('SELECT * FROM worker_executions ORDER BY rowid').all());
  const stepCount = () => readDb(() => db.prepare('SELECT COUNT(*) AS n FROM steps').get().n);
  const report = { kind: 'QUERY_NATIVE_FAULT', runtime, tab: Number(tab), started_at: new Date().toISOString(),
    actions: [], synthetic: true, finite_mock: true, real_business: false, paid_model: false,
    probe_sequence: sequence,
    historical_supervisor_exits: historicalSupervisorRecord(),
    component_unknown_version_fallback: 'separate component evidence; native rejection is a failure card' };
  report.plugin_hashes = Object.fromEntries(await Promise.all(['index.js', 'tool.js', 'skills.js', 'client.js']
    .map(async name => [name, createHash('sha256').update(await readFile(join(current.plugin, 'lib', name))).digest('hex')])));
  async function waitFor(check, milliseconds = 45000) {
    const ok = await waitUntil(check, { budgetMs: milliseconds });
    if (!ok) throw new Error('Native query fault verification deadline expired');
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
    assert.equal(clicked, true, 'Visible treeitem for title was not found');
    return 'dom';
  }
  function selectSession(sessionId) {
    const currentSession = cardState().session;
    const listed = listRegisteredSessions();
    const plan = sessionSwitchPlan(listed, currentSession ?? QUERY_SESSION_IDS[0], sessionId);
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
      faults: [...document.querySelectorAll('[data-query-fault]')].map(e => e.getAttribute('data-query-fault')),
      runStatus: [...document.querySelectorAll('[data-run-status]')].map(e => e.getAttribute('data-run-status')),
      cancelButtons: document.querySelectorAll('[data-testid="analytics-query-cancel"]').length,
      session: document.querySelector('[data-session-id]')?.getAttribute('data-session-id') ?? null,
    })`));
  }
  function inventory(callIds) {
    return {
      runs: rows().map(row => row.run_id),
      steps: stepCount(),
      workers: workers().map(row => row.execution_id),
      native_calls: [...callIds],
    };
  }
  async function nativeCallIds() {
    const ids = [];
    for (const sessionId of QUERY_SESSION_IDS) {
      const log = await nativeLog(sessionId).catch(() => []);
      for (const event of log.filter(row => row.type === 'tool/call' && row.data.name === QUERY_TOOL_NAME)) {
        ids.push(event.data.callId);
      }
    }
    return ids;
  }
  async function latestProof() {
    try {
      const text = await readFile(join(probeDir, 'proof.jsonl'), 'utf8');
      const lines = text.split('\n').filter(Boolean);
      return lines.length ? JSON.parse(lines.at(-1)) : null;
    } catch (error) {
      if (error.code === 'ENOENT') return null;
      throw error;
    }
  }
  async function kernelCancel(sessionId, runId, version, key) {
    const response = await fetch(`http://127.0.0.1:4315/api/v1/analytics-query/runs/${runId}/cancel`, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${config.gateway_token}`, 'content-type': 'application/json',
        'x-runtime-session-id': sessionId, 'idempotency-key': key, 'if-match': String(version),
      },
      body: JSON.stringify({ reason: 'USER_REQUEST' }), signal: AbortSignal.timeout(5000), redirect: 'error',
    });
    return { status: response.status, body: await response.json() };
  }
  function assertLeaseReleased(worker) {
    assert.equal(workerReleased(worker), true);
    assert.ok(worker.pid > 0);
    const fd = openSync(join(runtime, 'kernel/workers', worker.execution_id, '.lease'), constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      const info = fstatSync(fd);
      assert.deepEqual([info.dev, info.ino], [worker.lease_dev, worker.lease_ino]);
      flockSync(fd, 'exnb');
    } finally { closeSync(fd); }
  }
  function clickVisibleCancel() {
    expandTools();
    const snapshot = b('snapshot', '-i');
    const queryRef = parseQueryCancelRef(snapshot);
    const stopVisible = parseStopGeneratingRef(snapshot) != null;
    let via;
    let observedRef = queryRef;
    if (queryRef) {
      b('click', queryRef);
      via = 'query-card-button';
    } else {
      const dom = JSON.parse(b('js', `JSON.stringify((() => {
        const node = document.querySelector('[data-testid="analytics-query-cancel"]');
        if (!node || node.disabled) return false;
        node.click();
        return true;
      })())`));
      assert.equal(dom, true, 'Visible query cancel control was not found');
      via = 'query-card-dom';
      observedRef = null;
    }
    return { via, observed_ref: observedRef, stop_visible: stopVisible, snapshot };
  }
  function questionText(row) {
    return JSON.parse(row.payload_json).native_request.content[0].text;
  }
  function resultDays(row) {
    if (row.result_json == null) return null;
    const result = typeof row.result_json === 'string' ? JSON.parse(row.result_json) : row.result_json;
    return result?.facts?.observation_days ?? null;
  }
  try {
    assert.equal(historicalSupervisorRemainsUnknown(), true);
    assert.equal(rows().length, 0, 'Use a fresh runtime');
    b('tab', tab); assert.equal(b('url').trim(), 'http://127.0.0.1:4318/');
    await sendWhenReady(FAULT_QUESTIONS[0], QUERY_SESSION_IDS[0], null);
    await waitFor(async () => {
      expandTools();
      const proof = await latestProof();
      const active = workers().filter(row => row.active_slot === 1);
      const rowA = rows().find(row => row.session_id === QUERY_SESSION_IDS[0]);
      const ui = cardState();
      if (!rowA || !sqlHoldObserved(proof, active[0], rowA)) return false;
      if (ui.session !== QUERY_SESSION_IDS[0] || !ui.faults.includes('running')) return false;
      const log = await nativeLog(QUERY_SESSION_IDS[0]).catch(() => []);
      const calls = log.filter(event => event.type === 'tool/call' && event.data.name === QUERY_TOOL_NAME);
      const results = log.filter(event => event.type === 'tool/result');
      return calls.length >= 1 && results.length === 0;
    });
    const live = await latestProof();
    const rowALive = rows().find(row => row.session_id === QUERY_SESSION_IDS[0]);
    const holdWorker = workers().find(row => row.execution_id === live.execution_id);
    assert.ok(sqlHoldObserved(live, holdWorker, rowALive), 'cancel requires a live SQL hold, not QUEUED');
    expandTools();
    const runningUi = cardState();
    assert.equal(runningUi.faults.includes('running'), true);
    assert.equal(textLeaksQueryFacts(runningUi.cards.join('\n')), false);
    const screenshotPath = join(runtime, `native-query-fault-running-${Date.now()}.png`);
    b('screenshot', screenshotPath);
    const snapshotPath = join(runtime, 'native-query-fault-running-snapshot.txt');
    const runningSnapshot = b('snapshot', '-i');
    await writeFile(snapshotPath, runningSnapshot, { mode: 0o600 });
    report.sql_active = {
      at: new Date().toISOString(),
      session_id: QUERY_SESSION_IDS[0],
      run_id: live.run_id,
      attempt_id: live.attempt_id,
      request_id: rowALive.request_id,
      execution_id: live.execution_id,
      step_id: live.step_id,
      pid: live.pid,
      screenshot: screenshotPath,
      snapshot_path: snapshotPath,
    };
    const clicked = clickVisibleCancel();
    assert.ok(clicked.via === 'query-card-button' || clicked.via === 'query-card-dom');
    assert.notEqual(clicked.via, 'script-post');
    report.actions.push({
      type: 'browser-inflight-cancel', via: clicked.via, observed_ref: clicked.observed_ref,
      stop_visible: clicked.stop_visible, clicks: 1,
      session_id: QUERY_SESSION_IDS[0], run_id: live.run_id, attempt_id: live.attempt_id,
      request_id: rowALive.request_id, execution_id: live.execution_id,
    });
    await waitFor(() => rows().some(row => row.run_id === live.run_id && row.status === 'CANCELLED'));
    const cancelledA = rows().find(row => row.run_id === live.run_id);
    assert.equal(cancelledA.status, 'CANCELLED');
    assert.equal(cancelledA.result_json, null);
    assert.notEqual(cancelledA.status, 'CANCELLING');
    await waitNativeRequestComplete(QUERY_SESSION_IDS[0], cancelledA.request_id);
    expandTools();
    await waitFor(() => {
      const ui = cardState();
      return ui.session === QUERY_SESSION_IDS[0] && cardShowsFault(ui, 'tool-error')
        && !textLeaksQueryFacts(ui.cards.join('\n'));
    });
    const cancelUi = cardState();
    assert.equal(cardShowsFault(cancelUi, 'tool-error'), true);
    assert.equal(textLeaksQueryFacts(cancelUi.cards.join('\n')), false);
    assert.equal(cancelUi.cards.some(text => String(text).includes(FAIL_CARD_MARKERS.toolError)), true);
    const workerA = workers().find(row => row.run_id === cancelledA.run_id);
    assertLeaseReleased(workerA);
    assert.equal(workers().filter(row => row.active_slot != null).length, 0);
    const again = await kernelCancel(QUERY_SESSION_IDS[0], cancelledA.run_id, cancelledA.version, 'native-fault-cancel-a-repeat');
    assert.equal(again.status, 200);
    assert.equal(again.body.status, 'CANCELLED');
    assert.equal(again.body.result, null);
    report.actions.push({ type: 'kernel-cancel-repeat', session_id: QUERY_SESSION_IDS[0], run_id: cancelledA.run_id,
      status: again.body.status });
    selectSession(QUERY_SESSION_IDS[1]);
    await waitFor(() => sessionReadyWithoutForeign(cardState(), QUERY_SESSION_IDS[1], 30));
    const crossed = await kernelCancel(QUERY_SESSION_IDS[1], cancelledA.run_id, cancelledA.version, 'native-fault-cancel-cross');
    assert.equal(crossed.status, 404);
    report.actions.push({ type: 'kernel-cancel-wrong-session', session_id: QUERY_SESSION_IDS[1], run_id: cancelledA.run_id,
      status: crossed.status });
    await sendWhenReady(FAULT_QUESTIONS[1], QUERY_SESSION_IDS[1], null);
    await waitFor(() => rows().some(row => row.session_id === QUERY_SESSION_IDS[1] && ['FAILED', 'SUCCEEDED', 'CANCELLED'].includes(row.status)), 60000);
    const rowB = rows().find(row => row.session_id === QUERY_SESSION_IDS[1]);
    assert.equal(rowB.status, 'FAILED');
    assert.equal(rowB.error_code, 'TOOL_FAILED');
    assert.equal(rowB.result_json, null);
    assert.notEqual(rowB.status, 'CANCELLED');
    assert.equal(questionText(rowB), FAULT_QUESTIONS[1]);
    assert.equal(resultDays(rowB), null);
    await waitNativeRequestComplete(QUERY_SESSION_IDS[1], rowB.request_id);
    expandTools();
    await waitFor(() => {
      const ui = cardState();
      return ui.session === QUERY_SESSION_IDS[1] && cardShowsFault(ui, 'tool-error')
        && !textLeaksQueryFacts(ui.cards.join('\n'));
    });
    const failUi = cardState();
    assert.equal(cardShowsFault(failUi, 'tool-error'), true);
    assert.equal(failUi.cards.some(text => String(text).includes('版本不支持')), false);
    assert.equal(failUi.cards.some(text => String(text).includes(FAIL_CARD_MARKERS.toolError)), true);
    assert.equal(rows().find(row => row.run_id === cancelledA.run_id).status, 'CANCELLED');
    const workerB = workers().find(row => row.run_id === rowB.run_id);
    assertLeaseReleased(workerB);
    selectSession(QUERY_SESSION_IDS[0]);
    await waitFor(() => cardState().session === QUERY_SESSION_IDS[0]);
    await sendWhenReady(FAULT_QUESTIONS[2], QUERY_SESSION_IDS[0], cancelledA.request_id);
    await waitFor(() => rows().some(row => row.session_id === QUERY_SESSION_IDS[0] && row.status === 'SUCCEEDED'));
    const rowSuccess = rows().find(row => row.session_id === QUERY_SESSION_IDS[0] && row.status === 'SUCCEEDED');
    await waitNativeRequestComplete(QUERY_SESSION_IDS[0], rowSuccess.request_id);
    assert.equal(questionText(cancelledA), FAULT_QUESTIONS[0]);
    assert.equal(questionText(rowSuccess), FAULT_QUESTIONS[2]);
    assert.ok(FAULT_QUESTIONS[2].includes('30 日'));
    assert.equal(resultDays(rowSuccess), 30);
    expandTools();
    await waitFor(() => cardShowsQuery(cardState(), { ...QUERY_CARD_EXPECT[30], runId: rowSuccess.run_id }));
    assert.equal(cardHasForeignDays(cardState(), 60), false, 'A restore is N=30 only');
    const beforeLate = rows().find(row => row.run_id === rowSuccess.run_id);
    const late = await kernelCancel(QUERY_SESSION_IDS[0], rowSuccess.run_id, beforeLate.version, 'native-fault-cancel-late');
    assert.equal(late.status, 200);
    assert.equal(late.body.status, 'SUCCEEDED');
    assert.ok(late.body.result);
    assert.equal(late.body.result.facts.observation_days, 30);
    report.actions.push({ type: 'kernel-cancel-after-success', session_id: QUERY_SESSION_IDS[0], run_id: rowSuccess.run_id,
      status: late.body.status });
    assert.equal(rows().find(row => row.run_id === cancelledA.run_id).status, 'CANCELLED');
    assert.equal(rows().find(row => row.run_id === rowB.run_id).status, 'FAILED');
    const workerSuccess = workers().find(row => row.run_id === rowSuccess.run_id);
    assertLeaseReleased(workerSuccess);
    selectSession(QUERY_SESSION_IDS[1]);
    await waitFor(() => sessionReadyWithoutForeign(cardState(), QUERY_SESSION_IDS[1], 30));
    await sendWhenReady(FAULT_QUESTIONS[3], QUERY_SESSION_IDS[1], rowB.request_id);
    await waitFor(() => rows().some(row => row.session_id === QUERY_SESSION_IDS[1] && row.status === 'SUCCEEDED'));
    const rowBSuccess = rows().find(row => row.session_id === QUERY_SESSION_IDS[1] && row.status === 'SUCCEEDED');
    await waitNativeRequestComplete(QUERY_SESSION_IDS[1], rowBSuccess.request_id);
    assert.equal(questionText(rowBSuccess), FAULT_QUESTIONS[3]);
    assert.ok(FAULT_QUESTIONS[3].includes('60 日'));
    assert.equal(resultDays(rowBSuccess), 60);
    expandTools();
    await waitFor(() => cardShowsQuery(cardState(), { ...QUERY_CARD_EXPECT[60], runId: rowBSuccess.run_id }));
    assert.equal(cardHasForeignDays(cardState(), 30), false, 'B follow-up is N=60 only');
    assert.equal(rows().find(row => row.run_id === rowB.run_id).status, 'FAILED');
    assert.equal(rows().find(row => row.run_id === cancelledA.run_id).status, 'CANCELLED');
    const workerBSuccess = workers().find(row => row.run_id === rowBSuccess.run_id);
    assertLeaseReleased(workerBSuccess);
    report.request_binding = [
      { question: FAULT_QUESTIONS[0], session_id: QUERY_SESSION_IDS[0], expected_days: 30, status: 'CANCELLED', result_days: null },
      { question: FAULT_QUESTIONS[1], session_id: QUERY_SESSION_IDS[1], expected_days: 60, status: 'FAILED', result_days: null },
      { question: FAULT_QUESTIONS[2], session_id: QUERY_SESSION_IDS[0], expected_days: 30, status: 'SUCCEEDED', result_days: 30 },
      { question: FAULT_QUESTIONS[3], session_id: QUERY_SESSION_IDS[1], expected_days: 60, status: 'SUCCEEDED', result_days: 60 },
    ];
    report.runs = rows().map(({run_id, attempt_id, status, error_code, session_id, request_id}) => (
      {run_id, attempt_id, status, error_code, session_id, request_id}));
    report.workers = workers().map(({execution_id, run_id, state, pid, exit_code, error_code, active_slot}) => (
      {execution_id, run_id, state, pid, exit_code, error_code, active_slot}));
    const baseline = inventory(await nativeCallIds());
    b('reload');
    await waitFor(() => {
      const snap = b('snapshot', '-i');
      const cont = snap.match(/(@e\d+) \[button\] "Continue"/);
      if (cont) b('click', cont[1]);
      return parseComposer(b('snapshot', '-i')).readyToFill;
    }, 60000);
    selectSession(QUERY_SESSION_IDS[1]);
    await waitFor(() => sessionReadyWithoutForeign(cardState(), QUERY_SESSION_IDS[1], 30));
    expandTools();
    await waitFor(() => {
      const ui = cardState();
      return ui.faults.includes('tool-error') && cardShowsQuery(ui, { ...QUERY_CARD_EXPECT[60], runId: rowBSuccess.run_id });
    });
    assert.deepEqual(inventory(await nativeCallIds()), baseline);
    selectSession(QUERY_SESSION_IDS[0]);
    await waitFor(() => sessionReadyWithoutForeign(cardState(), QUERY_SESSION_IDS[0], 60));
    expandTools();
    await waitFor(() => cardShowsQuery(cardState(), { ...QUERY_CARD_EXPECT[30], runId: rowSuccess.run_id }));
    assert.equal(rows().find(row => row.run_id === cancelledA.run_id).status, 'CANCELLED');
    assert.equal(rows().find(row => row.run_id === rowBSuccess.run_id).status, 'SUCCEEDED');
    assert.deepEqual(inventory(await nativeCallIds()), baseline);
    report.refresh = { new_runs: 0, fail_card_preserved: true, success_card_preserved: true,
      cancelled_preserved: true, b_success_preserved: true, inventory: baseline };
    report.status = 'PASS';
  } catch (error) {
    report.status = 'FAIL';
    report.error = String(error.message).replace(/([?&](?:token|b0)=)[A-Za-z0-9_-]+/g, '$1[REDACTED]').slice(0, 1000);
    process.exitCode = 1;
  } finally {
    db.close();
    report.completed_at = new Date().toISOString();
    const path = join(runtime, `native-query-fault-evidence-${Date.now()}.json`);
    await writeFile(path, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    console.log(JSON.stringify({ status: report.status, error: report.error, runs: report.runs,
      workers: report.workers, refresh: report.refresh, sql_active: report.sql_active,
      historical_supervisor_exits: report.historical_supervisor_exits, report_path: path }));
  }
}
