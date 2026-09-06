/** Live synthetic-only B0 gateway negative tests. Never submits a valid prompt.
 * Only business launch credentials are read; no native DSH credential is read.
 * Own WebSockets are closed, but no service or Session is stopped/cancelled.
 */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const b0 = join(root, '.context/dsh-b0');
const current = JSON.parse(await readFile(join(b0, 'current.json'), 'utf8'));
const runtime = resolve(current.runtime);
const [target, ...extra] = process.argv.slice(2);
assert.ok(target && !extra.length, 'Pass the exact current synthetic runtime');
assert.equal(runtime, resolve(target));
assert.ok(runtime.startsWith(join(b0, 'runtime-')));
const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
const nativeReport = JSON.parse(await readFile(join(runtime, 'current-native-fixtures.json'), 'utf8'));
assert.equal(nativeReport.status, 'PASS', 'Foreign synthetic fixtures must have prior native evidence');
const foreign = nativeReport.sessionIds;
assert(foreign.every((id) => typeof id === 'string' && id.startsWith('session-b0-native-') && id !== refs.sessionId));
const { launchUrl } = JSON.parse(await readFile(join(runtime, 'gateway-private.json'), 'utf8'));
assert.equal(new URL(launchUrl).origin, 'http://127.0.0.1:4318', 'Business credential must target the gateway only');
const origin = 'http://127.0.0.1:4318';
const nativeOrigin = 'http://127.0.0.1:4317';
const gatewayRequire = createRequire(join(b0, 'upstream/packages/api/gateway/package.json'));
const { WebSocket } = gatewayRequire('ws');
const reportPath = join(runtime, `gateway-smoke-report-${Date.now()}.json`);
const sentinel = 'B0_SYNTHETIC_SECRET_MUST_NOT_ECHO';
const fakePrivatePath = '/synthetic/forbidden/private-config.json';
let cookie = '';
let rpcCounter = 0;
let reportReserved = false;
const sockets = new Set();
const report = { schema_version: 'analytics-b0-gateway-smoke/v1', status: 'RUNNING',
  started_at: new Date().toISOString(), runtime: relative(root, runtime), synthetic_only: true,
  primary_session: refs.sessionId, foreign_fixture_sessions: foreign,
  valid_prompts_sent: 0, tests: [], limitations: [
    'B0 single synthetic actor sample, not a production authorization or penetration-test certification.',
    'No paid provider, native credential, true private file, legitimate prompt, or service stop is used.',
    'Control/workspace isolation is checked against previously proven native synthetic foreign fixtures.',
  ] };
const save = () => reportReserved
  ? writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 })
  : Promise.resolve();

function safeError(error) {
  let value = error instanceof Error ? error.message : 'Unclassified gateway probe failure';
  const credentials = [launchUrl, cookie, ...new URL(launchUrl).searchParams.values(),
    ...cookie.split(';').map((part) => part.slice(part.indexOf('=') + 1))];
  for (const secret of credentials) if (secret) value = value.split(secret).join('[REDACTED]');
  return value.split(sentinel).join('[SYNTHETIC_SENTINEL]')
    .split(fakePrivatePath).join('[SYNTHETIC_PATH]')
    .replace(/([?&](?:token|b0)=)[^\s&]+/g, '$1[REDACTED]').slice(0, 300);
}

async function test(name, run) {
  const started = Date.now();
  try {
    const evidence = await run();
    report.tests.push({ name, status: 'PASS', duration_ms: Date.now() - started, ...(evidence ? { evidence } : {}) });
  } catch (error) {
    report.tests.push({ name, status: 'FAIL', duration_ms: Date.now() - started, failure: safeError(error) });
  }
  await save();
}

function assertScrubbed(text) {
  assert(!text.includes(sentinel), 'Response echoed a synthetic secret sentinel');
  assert(!text.includes(fakePrivatePath), 'Response echoed a synthetic private-path sentinel');
  assert(!text.includes(launchUrl), 'Response exposed business launch credentials');
  if (cookie) {
    assert(!text.includes(cookie), 'Response exposed a business cookie');
    for (const token of cookie.split(';').map((part) => part.slice(part.indexOf('=') + 1))) {
      if (token.length > 20) assert(!text.includes(token), 'Response exposed a business session token');
    }
  }
}

async function http(pathname, options = {}) {
  const response = await fetch(`${options.native ? nativeOrigin : origin}${pathname}`, {
    method: options.method ?? 'GET', redirect: 'manual', signal: AbortSignal.timeout(5000),
    headers: { ...(options.auth === false ? {} : { cookie }), ...options.headers },
    ...(options.body === undefined ? {} : { body: options.body }),
  });
  const text = await response.text();
  return { status: response.status, text, headers: response.headers };
}

async function rpc(method, payload, options = {}) {
  // This guard prevents a coding mistake from consuming the exhausted mock FIFO.
  if (method === 'session/prompt') {
    assert(foreign.includes(payload?.args?.request?.sessionId), 'Valid prompt is forbidden by this probe');
  }
  if (method === 'session/cancel') {
    assert(foreign.includes(payload?.args?.request?.sessionId), 'Own-session cancellation is forbidden by this probe');
  }
  const envelope = { type: 'client-request', rpcId: `b0-gateway-negative-${++rpcCounter}`, method, payload };
  const response = await http(`/api/${method}`, { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify(envelope), ...options });
  let json;
  try { json = JSON.parse(response.text); } catch { /* Report only bounded status, not raw body. */ }
  return { ...response, json };
}

function requireForbidden(response, expected = 403) {
  assert.equal(response.json?.type, 'server-response', 'Expected a typed failure envelope');
  assert.equal(response.json?.result?.ok, false, 'Forbidden request was admitted');
  assert.deepEqual(response.json.result.error.details, {}, 'Failure details were not scrubbed');
  assertScrubbed(response.text);
  assert.equal(response.status, expected, 'Gateway rejection status differs from explicit policy');
  return { http_status: response.status, error_code: response.json.result.error.code, scrubbed: true };
}

async function connectWs({ auth = true, native = false, originHeader = origin } = {}) {
  const url = `${native ? 'ws://127.0.0.1:4317' : 'ws://127.0.0.1:4318'}/api/remote.mux`;
  const socket = new WebSocket(url, { headers: { ...(auth ? { cookie } : {}), origin: originHeader }, handshakeTimeout: 5000 });
  sockets.add(socket);
  const frames = [];
  const waiters = new Set();
  let failure = null;
  socket.on('message', (bytes, binary) => {
    try {
      assert(!binary, 'Gateway unexpectedly emitted binary data');
      const text = bytes.toString();
      assertScrubbed(text);
      frames.push(JSON.parse(text));
    } catch (error) { failure = error; }
    for (const wake of waiters) wake();
  });
  socket.on('error', () => { failure = new Error('Gateway WebSocket transport failed'); for (const wake of waiters) wake(); });
  await new Promise((resolveReady, reject) => {
    socket.once('open', resolveReady);
    socket.once('unexpected-response', (_request, response) => {
      response.resume(); socket.terminate(); reject(new Error(`WebSocket upgrade rejected with HTTP ${response.statusCode}`));
    });
    socket.once('error', () => reject(new Error('WebSocket handshake failed')));
  });
  function waitFor(predicate, start = 0) {
    return new Promise((resolveFrame, reject) => {
      let timer;
      const finish = (value, error) => {
        clearTimeout(timer); waiters.delete(wake); error ? reject(error) : resolveFrame(value);
      };
      const wake = () => {
        if (failure) return finish(null, failure);
        const found = frames.slice(start).find(predicate);
        if (found) finish(found);
      };
      timer = setTimeout(() => finish(null, new Error('Bounded gateway WS frame wait expired')), 5000);
      waiters.add(wake); wake();
    });
  }
  return { socket, frames, waitFor, send: (message) => socket.send(JSON.stringify(message)),
    close() { socket.close(); sockets.delete(socket); } };
}

async function deniedHandshake(auth, native = false) {
  return new Promise((resolveStatus, reject) => {
    const socket = new WebSocket(`${native ? 'ws://127.0.0.1:4317' : 'ws://127.0.0.1:4318'}/api/remote.mux`, {
      headers: { ...(auth ? { cookie } : {}), origin: native ? nativeOrigin : origin }, handshakeTimeout: 5000 });
    sockets.add(socket);
    let settled = false;
    const finish = (status, error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      sockets.delete(socket);
      socket.terminate();
      error ? reject(error) : resolveStatus(status);
    };
    const timer = setTimeout(() => finish(null, new Error('Unauthorized handshake check timed out')), 5500);
    socket.on('error', () => finish(null, new Error('Unauthorized handshake transport failed before an HTTP response')));
    socket.once('open', () => finish(null, new Error('Unauthorized WebSocket unexpectedly opened')));
    socket.once('unexpected-response', (_request, response) => {
      const status = response.statusCode; response.resume(); finish(status);
    });
  });
}

function onlyOwnIds(items, ownId) {
  assert(Array.isArray(items) && items.every((id) => id === ownId), 'A foreign identifier crossed the gateway');
}

try {
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { flag: 'wx', mode: 0o600 });
  reportReserved = true;
  const exchange = await fetch(launchUrl, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
  assert.equal(exchange.status, 303, 'Business launch exchange failed');
  const cookies = exchange.headers.getSetCookie();
  assert(cookies.length === 1 && cookies[0].startsWith('shine-b0='), 'Expected only a business cookie');
  assert(cookies[0].includes('HttpOnly') && cookies[0].includes('SameSite=Strict'));
  cookie = cookies.map((item) => item.split(';')[0]).join('; ');
  report.auth = { business_cookie_only: true, http_only: true, same_site_strict: true, launch_redirect: 303 };
  await save();

  await test('gateway-no-cookie-401', async () => {
    const result = await rpc('session/modelCatalog', { args: {} }, { auth: false });
    return requireForbidden(result, 401);
  });
  await test('business-cookie-cannot-authenticate-native-root-or-api', async () => {
    const page = await http('/', { native: true });
    const api = await rpc('session/modelCatalog', { args: {} }, { native: true });
    assert.equal(page.status, 401); assert.equal(api.status, 401);
    assertScrubbed(page.text); assertScrubbed(api.text);
    return { root_status: page.status, api_status: api.status };
  });
  await test('gateway-static-bootstrap-has-no-native-cookie', async () => {
    const result = await http('/');
    assert.equal(result.status, 200);
    assert.equal(result.headers.getSetCookie().length, 0);
    assert(!/[?&]token=[A-Za-z0-9_-]{20,}/.test(result.text), 'HTML contains a native launch token');
    assertScrubbed(result.text);
    return { http_status: 200, set_cookie_count: 0 };
  });
  for (const method of ['session/modelCatalog', 'agentPresets/list', 'session/canOpenWorkspacePath', 'settings/canOpenAgentPresetDirectory']) {
    await test(`allowed-metadata-${method}`, async () => {
      const result = await rpc(method, { args: {} });
      assert.equal(result.status, 200); assert.equal(result.json?.result?.ok, true); assertScrubbed(result.text);
      return { http_status: 200 };
    });
    await test(`metadata-extra-field-denied-${method}`, async () => requireForbidden(await rpc(method, { args: { path: fakePrivatePath } })));
  }
  await test('own-session-page-allowed', async () => {
    const result = await rpc('session/page', { args: { request: { address: { kind: 'session', sessionId: refs.sessionId }, throughSeq: 0, maxMessages: 10 } } });
    assert.equal(result.status, 200); assert.equal(result.json?.result?.ok, true); return { http_status: 200 };
  });
  await test('session-page-too-many-messages-denied', async () => requireForbidden(await rpc('session/page', {
    args: { request: { address: { kind: 'session', sessionId: refs.sessionId }, throughSeq: 0, maxMessages: 101 } },
  })));
  await test('oversized-json-body-denied', async () => {
    const result = await http('/api/session/modelCatalog', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ type: 'client-request', rpcId: 'oversized', method: 'session/modelCatalog', payload: { text: 'x'.repeat(65537) } }) });
    assert.equal(result.status, 400); return { http_status: 400 };
  });
  for (const [name, method, args] of [
    ['settings-write-denied', 'settings/update', { ns: 'ui-theme', patch: { preference: 'dark', secret: sentinel, path: fakePrivatePath } }],
    ['directory-list-denied', 'directoryPicker/list', { path: fakePrivatePath }],
    ['file-reference-denied', 'fileReferences/list', { agentId: refs.sessionId, query: fakePrivatePath }],
    ['attachment-read-denied', 'session/attachment', { request: { sessionId: refs.sessionId, attachmentId: sentinel } }],
    ['unknown-endpoint-denied', 'future/notRegistered', { path: fakePrivatePath, secret: sentinel }],
    ['workspace-create-denied', 'workspace/create', { request: { path: fakePrivatePath } }],
    ['preset-change-denied', 'session/updateAgentPreset', { request: { sessionId: refs.sessionId, agentPreset: 'standard' } }],
    ['model-change-denied', 'session/updateModel', { request: { sessionId: refs.sessionId, model: 'unapproved' } }],
    ['native-command-denied', 'session/runCommand', { request: { sessionId: refs.sessionId, name: 'compact' } }],
  ]) await test(name, async () => requireForbidden(await rpc(method, { args })));

  await test('real-binary-fetch-route-get-denied', async () => {
    const result = await http(`/api/session/uploadFileBinary?sessionId=${encodeURIComponent(refs.sessionId)}&name=synthetic.txt`);
    const json = JSON.parse(result.text);
    return requireForbidden({ ...result, json });
  });
  await test('real-binary-fetch-route-post-denied', async () => {
    const result = await http(`/api/session/uploadFileBinary?sessionId=${encodeURIComponent(refs.sessionId)}&name=synthetic.txt`, {
      method: 'POST', headers: { 'content-type': 'application/octet-stream' }, body: `SYNTHETIC ONLY ${sentinel} ${fakePrivatePath}` });
    const json = JSON.parse(result.text);
    return requireForbidden({ ...result, json });
  });
  await test('json-fetch-route-cannot-bypass-rpc-policy', async () => requireForbidden(await rpc('session/uploadFileBinary', {
    args: { request: { sessionId: refs.sessionId, data: sentinel, path: fakePrivatePath } } })));

  for (const sessionId of foreign) {
    await test(`foreign-page-denied-${sessionId}`, async () => requireForbidden(await rpc('session/page', { args: { request: {
      address: { kind: 'session', sessionId }, throughSeq: 0, maxMessages: 10,
    } } })));
    await test(`foreign-prompt-denied-${sessionId}`, async () => requireForbidden(await rpc('session/prompt', { args: { request: {
      sessionId, requestId: `gateway-negative-${sessionId}`, mode: 'queue', content: [{ type: 'text', text: sentinel }], clientTimeZone: 'Asia/Shanghai',
    } } })));
    await test(`foreign-cancel-denied-${sessionId}`, async () => requireForbidden(await rpc('session/cancel', { args: { request: { sessionId } } })));
  }
  await test('cross-origin-cookie-use-denied', async () => requireForbidden(await rpc('session/modelCatalog', { args: {} }, {
    headers: { 'content-type': 'application/json', origin: 'https://synthetic-attacker.invalid', 'sec-fetch-site': 'cross-site' } })));
  await test('brand-and-isolated-condition-specimen-are-exact-read-only-paths', async () => {
    for (const path of ['/b0/brand/logo.png', '/favicon.svg', '/b0/board-sample?ref=b0-condition-specimen-v1']) {
      assert.equal((await http(path)).status, 200);
      assert.equal((await http(path, { auth: false })).status, 401);
      assert.equal((await http(path, { method: 'POST', body: '{}' })).status, 403);
    }
    return { authenticated_gets: 3, anonymous_denied: 3, writes_denied: 3 };
  });
  await test('condition-specimen-rejects-old-filters-and-arbitrary-return', async () => {
    for (const path of ['/b0/board-sample?ref=b0-condition-specimen-v1&channel=old',
      '/b0/board-sample?ref=b0-condition-specimen-v1&return=https://example.com',
      '/b0/board-sample?ref=other', '/b0/brand/logo.png?path=other', '/audience?channel=old']) {
      assert.equal((await http(path)).status, 403);
    }
    return { rejected_paths: 5 };
  });
  await test('encoded-operation-name-cannot-bypass-manifest', async () => {
    for (const method of ['session%2FmodelCatalog', '%73ession/modelCatalog', 'session/modelCatalog%2f..%2fcreate']) {
      assert.equal((await rpc(method, { args: {} })).status, 403);
    }
    return { rejected_paths: 3 };
  });

  await test('session-list-hides-proven-foreign-fixtures', async () => {
    const result = await rpc('session/list', { args: { _request: {} } });
    assert.equal(result.status, 200); assert.equal(result.json?.result?.ok, true);
    onlyOwnIds(result.json.result.value.items.map((item) => item.sessionId), refs.sessionId);
    assert.equal(result.json.result.value.items.length, 1);
    assert(foreign.every((id) => !result.text.includes(id)), 'Foreign fixture appeared in session list');
    return { visible_session_ids: result.json.result.value.items.map((item) => item.sessionId), foreign_fixtures_hidden: foreign.length };
  });
  await test('settings-metadata-is-read-only-and-namespace-limited', async () => {
    const result = await rpc('settings/describe', { args: {} });
    assert.equal(result.status, 200); assert.equal(result.json?.result?.ok, true);
    const value = result.json.result.value;
    assert.equal(value.writable, false); assert.equal(value.hasDocument, false);
    const allowed = ['locale', 'ui-theme', 'ui-chat', 'ui-conversation', 'ui-onboarding'];
    assert(value.namespaces.every((item) => allowed.includes(item.ns)));
    return { namespaces: value.namespaces.map((item) => item.ns), writable: false };
  });
  await test('websocket-no-cookie-denied', async () => {
    const status = await deniedHandshake(false); assert.equal(status, 403); return { http_status: status };
  });
  await test('business-cookie-cannot-authenticate-native-websocket', async () => {
    const status = await deniedHandshake(true, true); assert.equal(status, 401); return { http_status: status };
  });

  const ws = await connectWs();
  try {
    await test('events-ready-is-minimal-and-no-real-home', async () => {
      ws.send({ type: 'open', streamId: 'smoke-events', endpoint: '$events', payload: { args: {} } });
      const frame = await ws.waitFor((item) => item.type === 'item' && item.streamId === 'smoke-events' && item.value.type === 'ready');
      assert.deepEqual(Object.keys(frame.value).sort(), ['clientId', 'host', 'type']);
      assert.deepEqual(frame.value.host, { home: '/synthetic' });
      return { bootstrap: 'ready', home_is_synthetic: true };
    });
    for (const sessionId of foreign) await test(`foreign-follow-denied-${sessionId}`, async () => {
      const streamId = `follow-${sessionId}`;
      ws.send({ type: 'open', streamId, endpoint: 'session/follow', payload: { args: { request: {
        address: { kind: 'session', sessionId }, assistantStream: true, maxMessages: 10,
      } } } });
      const frame = await ws.waitFor((item) => item.type === 'error' && item.streamId === streamId);
      assert.equal(frame.error.code, 'gateway/forbidden'); assert.deepEqual(frame.error.details, {});
      return { error_code: frame.error.code };
    });
    await test('same-websocket-stream-id-reuse-denied', async () => {
      const start = ws.frames.length;
      ws.send({ type: 'open', streamId: 'smoke-events', endpoint: 'session/control', payload: { args: {} } });
      const frame = await ws.waitFor((item) => item.type === 'error' && item.streamId === 'smoke-events', start);
      assert.equal(frame.error.code, 'gateway/forbidden');
      return { duplicate_open_denied: true };
    });
    await test('stream-id-reuse-after-cancel-denied', async () => {
      const start = ws.frames.length;
      ws.send({ type: 'cancel', streamId: 'smoke-events' });
      ws.send({ type: 'open', streamId: 'smoke-events', endpoint: 'workspace/follow', payload: { args: {} } });
      const frame = await ws.waitFor((item) => item.type === 'error' && item.streamId === 'smoke-events', start);
      assert.equal(frame.error.code, 'gateway/forbidden');
      return { reopen_after_cancel_denied: true };
    });
    await test('session-control-baseline-is-single-session', async () => {
      ws.send({ type: 'open', streamId: 'smoke-control', endpoint: 'session/control', payload: { args: {} } });
      const frame = await ws.waitFor((item) => item.type === 'item' && item.streamId === 'smoke-control' && item.value.type === 'baseline');
      const baseline = frame.value.value;
      const keys = {};
      for (const field of ['queues', 'jobs', 'projections']) {
        keys[field] = Object.keys(baseline[field]); onlyOwnIds(keys[field], refs.sessionId);
      }
      assert(foreign.every((id) => !JSON.stringify(frame.value).includes(id)));
      return { scoped_map_keys: keys, foreign_fixtures_hidden: foreign.length };
    });
    await test('workspace-baseline-hides-foreign-session-memberships', async () => {
      ws.send({ type: 'open', streamId: 'smoke-workspace', endpoint: 'workspace/follow', payload: { args: {} } });
      const frame = await ws.waitFor((item) => item.type === 'item' && item.streamId === 'smoke-workspace' && item.value.type === 'baseline');
      const value = frame.value.value;
      assert.equal(value.items.length, 1);
      onlyOwnIds(value.items.map((item) => item.workspaceId), refs.workspaceId);
      for (const item of value.items) { assert.equal(item.path, join(runtime, 'synthetic-workspace')); onlyOwnIds(item.sessionIds, refs.sessionId); }
      onlyOwnIds(value.archivedSessionIds, refs.sessionId);
      assert(foreign.every((id) => !JSON.stringify(value).includes(id)));
      return { workspace_ids: value.items.map((item) => item.workspaceId), session_ids: value.items.flatMap((item) => item.sessionIds) };
    });
    await test('own-session-follow-snapshot-remains-readable', async () => {
      ws.send({ type: 'open', streamId: 'smoke-own-follow', endpoint: 'session/follow', payload: { args: { request: {
        address: { kind: 'session', sessionId: refs.sessionId }, maxMessages: 10, assistantStream: true,
      } } } });
      const frame = await ws.waitFor((item) => item.type === 'item' && item.streamId === 'smoke-own-follow' && item.value.type === 'snapshot');
      assert.equal(frame.value.header.id, refs.sessionId);
      assert(foreign.every((id) => !JSON.stringify(frame.value).includes(id)));
      return { session_id: frame.value.header.id, record_count: frame.value.records.length, cursor: frame.value.cursor };
    });
    await test('unknown-websocket-stream-denied', async () => {
      ws.send({ type: 'open', streamId: 'smoke-unknown', endpoint: 'settings/follow', payload: { args: {} } });
      const frame = await ws.waitFor((item) => item.type === 'error' && item.streamId === 'smoke-unknown');
      assert.equal(frame.error.code, 'gateway/forbidden'); return { error_code: frame.error.code };
    });
  } finally { ws.close(); }
  for (const [name, bytes, binary, code] of [['binary-ws-input-denied', Buffer.from('synthetic'), true, 1008],
    ['oversized-ws-input-denied', 'x'.repeat(65537), false, 1009]]) {
    await test(name, async () => {
      const probe = await connectWs();
      try {
        const closed = new Promise((resolveCode, reject) => {
          const timer = setTimeout(() => reject(new Error('Bounded WS close deadline expired')), 5000);
          probe.socket.once('close', value => { clearTimeout(timer); resolveCode(value); });
        });
        probe.socket.send(bytes, { binary });
        assert.equal(await closed, code);
        return { close_code: code, application_frames: probe.frames.length };
      } finally { probe.close(); }
    });
  }
  report.status = report.tests.every((item) => item.status === 'PASS') ? 'PASS' : 'FAIL';
} catch (error) {
  report.status = 'FAIL'; report.fatal_failure = safeError(error);
} finally {
  for (const socket of sockets) socket.terminate();
  report.completed_at = new Date().toISOString();
  report.passed = report.tests.filter((item) => item.status === 'PASS').length;
  report.failed = report.tests.filter((item) => item.status === 'FAIL').length;
  await save();
  console.log(JSON.stringify({ status: report.status, passed: report.passed, failed: report.failed,
    failures: report.tests.filter((item) => item.status === 'FAIL').map((item) => ({ name: item.name, failure: item.failure })),
    ...(report.fatal_failure ? { fatal_failure: report.fatal_failure } : {}),
    valid_prompts_sent: 0, report: relative(root, reportPath) }));
  process.exitCode = report.status === 'PASS' ? 0 : 1;
}
