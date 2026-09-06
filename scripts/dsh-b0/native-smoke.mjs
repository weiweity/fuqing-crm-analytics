/** B0 synthetic native API verification. Never prints credentials or stops DSH. */
import assert from 'node:assert/strict';
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { resolve, join, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { zstdDecompressSync } from 'node:zlib';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const runtime = resolve(process.argv[2] ?? join(root, '.context/dsh-b0/runtime-xlXpXV'));
assert.equal(runtime, join(root, '.context/dsh-b0/runtime-xlXpXV'), 'This smoke is authorized only for the named B0 runtime');
const upstream = join(root, '.context/dsh-b0/upstream');
const { scanZstdFrames } = await import(pathToFileURL(join(upstream, 'packages/session/session-persistence-jsonl/lib/types/zstd.js')).href);
const { decodeFixture } = await import(pathToFileURL(join(root, 'dsh-plugins/analytics-workbench/src/model.mjs')).href);
const gatewayRequire = createRequire(join(upstream, 'packages/api/gateway/package.json'));
const WebSocket = gatewayRequire('ws');
const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
assert.equal(refs.sessionId, 'session-b0-synthetic-primary');
assert.equal(typeof refs.workspaceId, 'string');
const reportPath = join(runtime, 'native-smoke-report.json');
const report = {
  schema_version: 'analytics-b0-native-smoke/v1',
  runtime: relative(root, runtime), started_at: new Date().toISOString(),
  status: 'RUNNING', stage: 'auth', synthetic_only: true,
  limitations: ['Native DSH only; not A1 business run binding or production authorization.',
    'No browser/DOM validation. Provider socket close must be checked against supervisor mock evidence separately.'],
};
// A repeated run must not consume the mock FIFO a second time.
await writeFile(reportPath, JSON.stringify(report, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
const save = () => writeFile(reportPath, JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
const sockets = new Set();
let launchUrl = '', cookie = '';
const safeError = value => {
  let message = value instanceof Error ? value.message : 'Unknown native smoke failure';
  for (const secret of [launchUrl, cookie, ...new URL(launchUrl || 'http://127.0.0.1').searchParams.values()]) {
    if (secret) message = message.split(secret).join('[REDACTED]');
  }
  return message.replace(/([?&](?:token|b0)=)[^\s&]+/g, '$1[REDACTED]').slice(0, 400);
};
async function waitFor(read, timeout = 20000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    const value = await read();
    if (value) return value;
    await delay(100);
  }
  throw new Error(`B0 bounded wait expired in stage ${report.stage}`);
}
async function call(method, request) {
  assert.ok(['session/create', 'session/prompt', 'session/cancel', 'session/page'].includes(method));
  const response = await fetch(`http://127.0.0.1:4317/api/${method}`, {
    method: 'POST', headers: { 'content-type': 'application/json', cookie },
    body: JSON.stringify({ type: 'client-request', rpcId: `b0-native-${Date.now()}`, method, payload: { args: { request } } }),
    signal: AbortSignal.timeout(10000), redirect: 'error',
  });
  const value = await response.json();
  if (response.status !== 200 || value.result?.ok !== true) {
    const code = value.result?.error?.code;
    throw new Error(`${method}: HTTP ${response.status}; code ${typeof code === 'string' && /^[\w/-]+$/.test(code) ? code : 'unavailable'}`);
  }
  return value.result.value;
}
async function follow(sessionId) {
  const socket = new WebSocket('ws://127.0.0.1:4317/api/remote.mux', { headers: { cookie }, handshakeTimeout: 5000 });
  sockets.add(socket);
  const frames = [];
  let failure;
  socket.on('error', () => { failure = new Error('B0 native WebSocket transport error'); });
  socket.on('message', bytes => {
    try {
      const envelope = JSON.parse(bytes.toString());
      if (envelope.type === 'item' && envelope.streamId === 'b0-session') frames.push(envelope.value);
      if (envelope.type === 'error') failure = new Error('B0 native follow returned a stream error');
    } catch { failure = new Error('B0 native follow returned malformed JSON'); }
  });
  await waitFor(() => { if (failure) throw failure; return socket.readyState === WebSocket.OPEN; }, 6000);
  socket.send(JSON.stringify({ type: 'open', streamId: 'b0-session', endpoint: 'session/follow',
    payload: { args: { request: { address: { kind: 'session', sessionId }, assistantStream: true, maxMessages: 100 } } } }));
  const snapshot = await waitFor(() => { if (failure) throw failure; return frames.find(frame => frame.type === 'snapshot'); });
  assert.equal(snapshot.header.id, sessionId);
  assert.ok(Number.isSafeInteger(snapshot.cursor));
  return { frames, snapshot, check() { if (failure) throw failure; }, close() { socket.close(); sockets.delete(socket); } };
}
async function readLog(sessionId) {
  const sessionsRoot = join(runtime, 'harness/sessions');
  for (const project of await readdir(sessionsRoot, { withFileTypes: true })) {
    if (!project.isDirectory()) continue;
    const file = join(sessionsRoot, project.name, sessionId, 'session.v2.jsonl.zstd');
    let bytes;
    try { bytes = await readFile(file); } catch (error) { if (error.code === 'ENOENT') continue; throw error; }
    const scan = scanZstdFrames(bytes);
    const rows = scan.frames.flatMap(({ start, end }) => zstdDecompressSync(bytes.subarray(start, end))
      .toString('utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)));
    const header = rows.find(row => row.type === 'session');
    assert.equal(header?.id, sessionId);
    assert.equal(header?.cwd, join(runtime, 'synthetic-workspace'));
    assert.equal(header?.agentPreset, 'analytics-b0');
    return { file: relative(runtime, file), frame_count: scan.frames.length,
      incomplete_tail: scan.tornStart !== undefined, events: rows.filter(row => row.type !== 'session') };
  }
  return { events: [] };
}
function summarize(log) {
  return { log: log.file, frame_count: log.frame_count, incomplete_tail: log.incomplete_tail,
    event_types: log.events.map(event => ({ type: event.type, seq: event.seq })),
    tool_names: [...new Set(log.events.filter(event => event.type === 'tool/call').map(event => event.data.name))],
    turn_ends: log.events.filter(event => event.type === 'turn/end').map(event => ({ seq: event.seq, turn: event.data.turn,
      kind: event.data.reason.kind, cancel_cause: event.data.reason.reason?.kind,
      error_code: event.data.reason.error?.code, http_status: event.data.reason.error?.status })) };
}
async function pageAtOpening(sessionId) {
  const stream = await follow(sessionId);
  try {
    const throughSeq = stream.snapshot.cursor;
    const page = await call('session/page', { address: { kind: 'session', sessionId }, throughSeq, maxMessages: 100 });
    assert.ok(Array.isArray(page.records));
    assert.ok(page.records.every(row => row.type === 'event' && row.event.seq <= throughSeq));
    return { address: { kind: 'session', sessionId }, throughSeq, records: page.records.length,
      hasMore: page.hasMore, end_kinds: page.records.filter(row => row.event.type === 'turn/end').map(row => row.event.data.reason.kind) };
  } finally { stream.close(); }
}

try {
  ({ launchUrl } = JSON.parse(await readFile(join(runtime, 'browser-private.json'), 'utf8')));
  assert.equal(new URL(launchUrl).origin, 'http://127.0.0.1:4317');
  const auth = await fetch(launchUrl, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
  cookie = auth.headers.getSetCookie().map(value => value.split(';')[0]).join('; ');
  assert.ok(cookie, 'B0 cookie exchange did not return a session cookie');

  report.stage = 'verify-primary';
  const primary = await readLog(refs.sessionId);
  const calls = primary.events.filter(event => event.type === 'tool/call');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].data.name, 'analytics_b0_query');
  const advertised = primary.events.filter(event => event.type === 'request/header').flatMap(event => event.data.header.tools.map(tool => tool.name));
  assert.deepEqual([...new Set(advertised)], ['analytics_b0_query']);
  const result = primary.events.find(event => event.type === 'tool/result');
  assert.ok(result && decodeFixture(result.data.meta), 'Primary metadata was not the exact versioned B0 fixture');
  const output = result.data.message.content.find(part => part.type === 'tool-result');
  assert.equal(output.isError, false);
  assert.equal(output.toolCallId, calls[0].data.callId);
  assert.equal(primary.events.at(-1)?.data.reason?.kind, 'completed');
  report.primary = { ...summarize(primary), advertised_tool_names: advertised, result_seq: result.seq,
    result_is_error: output.isError, meta: decodeFixture(result.data.meta), page: await pageAtOpening(refs.sessionId), status: 'PASS' };
  await save();
  console.log('B0 primary: durable tool result and completed turn verified.');

  report.stage = 'cancel-slow-provider';
  const cancelSession = 'session-b0-native-cancel';
  const created = await call('session/create', { workspaceId: refs.workspaceId, sessionId: cancelSession, agentPreset: 'analytics-b0' });
  assert.equal(created.sessionId, cancelSession);
  const slow = await follow(cancelSession);
  try {
    const receipt = await call('session/prompt', { sessionId: cancelSession, requestId: 'b0-native-cancel-v1', mode: 'queue',
      content: [{ type: 'text', text: 'B0 合成取消测试。只输出固定合成验证文字，不访问其他数据。' }], clientTimeZone: 'Asia/Shanghai' });
    assert.equal(receipt.accepted, true);
    const chunk = await waitFor(() => { slow.check(); return slow.frames.find(frame => frame.type === 'assistant-stream' && frame.frame.type === 'chunk'); });
    const before = Date.now();
    const cancellation = await call('session/cancel', { sessionId: cancelSession });
    assert.equal(cancellation.accepted, true);
    const end = await waitFor(() => { slow.check(); return slow.frames.find(frame => frame.type === 'event' && frame.event.type === 'turn/end'); });
    assert.equal(end.event.data.reason.kind, 'aborted');
    assert.equal(end.event.data.reason.reason?.kind, 'user');
    const durable = await waitFor(async () => { const log = await readLog(cancelSession); return log.events.some(event => event.type === 'turn/end') ? log : false; });
    assert.equal(durable.events.find(event => event.type === 'turn/end').data.reason.kind, 'aborted');
    report.cancellation = { sessionId: cancelSession, prompt_accepted: receipt.accepted, cancel_accepted: cancellation.accepted,
      provider_started_evidence: { source: 'session/follow assistant-stream chunk', attemptId: chunk.frame.attemptId, index: chunk.frame.index },
      cancel_to_durable_observation_ms: Date.now() - before, ...summarize(durable), page: await pageAtOpening(cancelSession), status: 'PASS' };
  } finally { slow.close(); }
  await save();
  console.log('B0 cancellation: provider chunk preceded cancel; durable user-aborted turn verified.');

  report.stage = 'server-error';
  const errorSession = 'session-b0-native-error';
  const errorCreated = await call('session/create', { workspaceId: refs.workspaceId, sessionId: errorSession, agentPreset: 'analytics-b0' });
  assert.equal(errorCreated.sessionId, errorSession);
  const failing = await follow(errorSession);
  try {
    const receipt = await call('session/prompt', { sessionId: errorSession, requestId: 'b0-native-error-v1', mode: 'queue',
      content: [{ type: 'text', text: 'B0 合成服务错误测试。不访问其他数据。' }], clientTimeZone: 'Asia/Shanghai' });
    assert.equal(receipt.accepted, true);
    const end = await waitFor(() => { failing.check(); return failing.frames.find(frame => frame.type === 'event' && frame.event.type === 'turn/end'); });
    assert.equal(end.event.data.reason.kind, 'error');
    const durable = await waitFor(async () => { const log = await readLog(errorSession); return log.events.some(event => event.type === 'turn/end') ? log : false; });
    assert.equal(durable.events.find(event => event.type === 'turn/end').data.reason.kind, 'error');
    assert.equal(durable.events.filter(event => event.type === 'tool/result').length, 0);
    assert.equal(durable.events.filter(event => event.type === 'assistant/message').length, 0);
    report.server_error = { sessionId: errorSession, prompt_accepted: receipt.accepted, ...summarize(durable),
      successful_tool_results: 0, completed_assistant_messages: 0, page: await pageAtOpening(errorSession), status: 'PASS' };
  } finally { failing.close(); }
  report.status = 'PASS';
  report.stage = 'complete';
  report.completed_at = new Date().toISOString();
  await save();
  console.log(JSON.stringify({ status: report.status, report: relative(root, reportPath),
    primary: report.primary.status, cancellation: report.cancellation.status, server_error: report.server_error.status }));
} catch (error) {
  report.status = 'FAIL';
  report.failure = safeError(error);
  report.failed_at = new Date().toISOString();
  await save();
  console.error(JSON.stringify({ status: report.status, stage: report.stage, error: report.failure, report: relative(root, reportPath) }));
  process.exitCode = 1;
} finally {
  // Close only this test's observation sockets; never cancel another Session or stop DSH.
  for (const socket of sockets) socket.close();
}
