/** Internal B0 smoke driver. Credentials stay in memory; all requests are local. */
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, join, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const current = JSON.parse(await readFile(join(root, '.context/dsh-b0/current.json'), 'utf8'));
const { runtime } = current;
assert.ok(runtime.startsWith(join(root, '.context/dsh-b0/runtime-')));
const { launchUrl } = JSON.parse(await readFile(join(runtime, 'browser-private.json'), 'utf8'));
const url = new URL(launchUrl);
assert.equal(url.origin, 'http://127.0.0.1:4317');
const base = url.origin;
const auth = await fetch(launchUrl, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
const cookie = auth.headers.getSetCookie().map(value => value.split(';')[0]).join('; ');
assert.ok(cookie, 'Expected isolated DSH cookie exchange');
const file = (name, data) => writeFile(join(runtime, name), JSON.stringify(data, null, 2) + '\n', { mode: 0o600 });
async function call(method, request) {
  const response = await fetch(`${base}/api/${method}`, {
    method: 'POST', headers: { 'content-type': 'application/json', cookie },
    body: JSON.stringify({ type: 'client-request', rpcId: `b0-${Date.now()}`, method,
      payload: { args: method === 'session/list' ? { _request: {} } : request === undefined ? {} : { request } } }),
    signal: AbortSignal.timeout(10000),
  });
  const value = await response.json();
  if (response.status !== 200 || value.result?.ok !== true) throw new Error(`${method}: ${JSON.stringify(value)}`);
  return value.result.value;
}
const kernelPrivate = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
const queryMode = kernelPrivate.family === 'channel_followup';
const action = process.argv[2] ?? 'bootstrap';
if (action === 'bootstrap') {
  const unauth = await fetch(`${base}/api/session/catalog`, { method: 'POST', signal: AbortSignal.timeout(5000) });
  assert.equal(unauth.status, 401);
  const created = await call('workspace/create', { path: join(runtime, 'synthetic-workspace') });
  if (queryMode) {
    assert.ok(Array.isArray(kernelPrivate.session_ids) && kernelPrivate.session_ids.length === 2);
    const sessionIds = [];
    for (const sessionId of kernelPrivate.session_ids) {
      const session = await call('session/create', {
        workspaceId: created.workspace.workspaceId, sessionId, agentPreset: 'analytics-b0',
      });
      assert.equal(session.sessionId, sessionId);
      sessionIds.push(session.sessionId);
    }
    const refs = { workspaceId: created.workspace.workspaceId, sessionId: sessionIds[0], sessionIds,
      unauthenticated_status: unauth.status };
    await file('refs.json', refs);
    console.log(JSON.stringify(refs));
  } else {
    const session = await call('session/create', { workspaceId: created.workspace.workspaceId, sessionId: 'session-b0-synthetic-primary', agentPreset: 'analytics-b0' });
    const refs = { workspaceId: created.workspace.workspaceId, sessionId: session.sessionId, unauthenticated_status: unauth.status };
    await file('refs.json', refs);
    console.log(JSON.stringify(refs));
  }
} else if (action === 'prepare-ui') {
  // The testing notice was read and Continue was clicked in the native UI.
  // Seed only these cosmetic preferences using the internal setup identity;
  // the browser still cannot write arbitrary DSH settings.
  for (const [ns, patch] of [['ui-onboarding', { welcomeNoticeVersion: '2026-08-13.1' }], ['locale', { preference: 'zh-CN' }]]) {
    const method = 'settings/update';
    const response = await fetch(`${base}/api/${method}`, { method: 'POST', headers: { 'content-type': 'application/json', cookie },
      body: JSON.stringify({ type: 'client-request', rpcId: 'b0-ui-setup', method, payload: { args: { ns, patch } } }), signal: AbortSignal.timeout(5000) });
    const value = await response.json();
    assert.equal(value.result?.ok, true, `B0 cosmetic setting rejected: ${ns}`);
  }
  console.log('B0 internal setup: testing notice acknowledged; Chinese locale requested. No browser settings write granted.');
} else if (action === 'isolation-fixtures') {
  assert.equal(queryMode, false, 'query native-query does not create foreign sessions');
  const evidencePath = join(runtime, 'current-native-fixtures.json');
  // Explicit setup-only path. Two empty synthetic sessions, no prompts/models.
  const report = { status: 'RUNNING', sessionIds: [], workspaceIds: [], valid_prompts_sent: 0 };
  let existing;
  try { existing = JSON.parse(await readFile(evidencePath, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (existing) {
    const listed = await call('session/list');
    const expected = ['a', 'b'].map(label => `session-b0-native-foreign-${label}`);
    assert.ok(expected.every(id => listed.items.some(row => row.sessionId === id)), 'Existing fixture setup is incomplete; do not silently create duplicates');
    await writeFile(evidencePath, JSON.stringify({ ...existing, sessionIds: expected, status: 'PASS', verified_by_native_list: true }, null, 2) + '\n', { mode: 0o600 });
    console.log(JSON.stringify({ status: 'PASS', verified_existing_synthetic_sessions: expected.length, valid_prompts_sent: 0 }));
    process.exit(0);
  }
  await writeFile(evidencePath, JSON.stringify(report), { flag: 'wx', mode: 0o600 });
  for (const label of ['a', 'b']) {
    const path = join(runtime, 'synthetic-workspace', `foreign-${label}`);
    await mkdir(path, { mode: 0o700 });
    const created = await call('workspace/create', { path });
    const sessionId = `session-b0-native-foreign-${label}`;
    const session = await call('session/create', { workspaceId: created.workspace.workspaceId, sessionId, agentPreset: 'analytics-b0' });
    assert.equal(session.sessionId, sessionId);
    report.sessionIds.push(sessionId); report.workspaceIds.push(created.workspace.workspaceId);
    await writeFile(evidencePath, JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
  }
  const listed = await call('session/list');
  assert.ok(report.sessionIds.every(id => listed.items.some(row => row.sessionId === id)));
  report.status = 'PASS';
  await writeFile(evidencePath, JSON.stringify(report, null, 2) + '\n', { mode: 0o600 });
  console.log(JSON.stringify({ status: 'PASS', created_synthetic_sessions: report.sessionIds.length, valid_prompts_sent: 0 }));
} else if (action === 'browser') {
  // Let the established browse skill drive the existing browser daemon. Do not
  // echo the launch URL or pass credentials to another browser implementation.
  const business = JSON.parse(await readFile(join(runtime, 'gateway-private.json'), 'utf8'));
  assert.equal(new URL(business.launchUrl).origin, 'http://127.0.0.1:4318');
  const [flag, browse, ...extra] = process.argv.slice(3);
  assert.ok(flag === '--browse' && isAbsolute(browse ?? '') && !extra.length, 'Pass browser --browse /absolute/browse');
  const result = spawnSync(browse, ['newtab', business.launchUrl], { encoding: 'utf8', timeout: 45000 });
  const output = `${result.stdout ?? ''}${result.stderr ?? ''}`.replace(/([?&](?:token|b0)=)[A-Za-z0-9_-]+/g, '$1[REDACTED]');
  process.stdout.write(output);
  process.exitCode = result.status ?? 1;
} else {
  if (action === 'prompt' || action === 'duplicate' || action === 'slow' || action === 'failure') {
    throw new Error('Legacy direct prompt bypass is disabled. Use the native UI via the FastAPI-backed gateway.');
  } else if (action === 'cancel') {
    throw new Error('Legacy direct cancel bypass is disabled. Use native Stop via the FastAPI-backed gateway.');
  } else if (action === 'page') {
    throw new Error('Use native-smoke.mjs: session/page requires an observed address and throughSeq, not just sessionId.');
  } else throw new Error(`Unknown B0 action: ${action}`);
}
