import { currentPorts } from './ports.mjs';
/** B0 transport experiment. Explicit manifest, not a production access service. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { authorizeHttp, authorizeStream, filterHttpResult, filterStreamItem, sessionAllowed } from './gateway-policy.mjs';
import { assetHeaderViolation, mapAssetRoute } from './asset-routes.mjs';
import { pluginManifest, refreshedPluginManifest, safeRpcResult } from './transport-safety.mjs';
import { currentPermission, permissionFence } from './permission-fence.mjs';
import { brandAssets } from './brand-assets.mjs';
import { resolveBoardSample, boardSampleHtml } from './board-sample.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const b0 = join(root, '.context/dsh-b0');
const current = JSON.parse(await readFile(join(b0, 'current.json'), 'utf8'));
const ports = currentPorts(current);
const { runtime } = current;
assert.ok(runtime.startsWith(join(b0, 'runtime-')));
const refs = JSON.parse(await readFile(join(runtime, 'refs.json'), 'utf8'));
const { launchUrl } = JSON.parse(await readFile(join(runtime, 'browser-private.json'), 'utf8'));
assert.equal(new URL(launchUrl).origin, `http://127.0.0.1:${ports.web}`);
const upstreamOrigin = `http://127.0.0.1:${ports.web}`;
const origin = `http://127.0.0.1:${ports.gateway}`;
const brands = await brandAssets(root);
const exchange = await fetch(launchUrl, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
let internalCookie = exchange.headers.getSetCookie().map(s => s.split(';')[0]).join('; ');
assert.ok(internalCookie);
const bootResponse = await fetch(`${upstreamOrigin}/`, { headers: { cookie: internalCookie }, signal: AbortSignal.timeout(5000) });
assert.equal(bootResponse.status, 200);
let bootHtml = await bootResponse.text();
let pluginUrls = pluginManifest(bootHtml, upstreamOrigin);
const pass = randomBytes(32).toString('base64url');
const session = randomBytes(32).toString('base64url');
const scope = { ...refs, workspacePath: join(runtime, 'synthetic-workspace'), inFlight: false };
const kernelPrivate = JSON.parse(await readFile(join(runtime, 'kernel-private.json'), 'utf8'));
const { gateway_token: gatewayToken } = kernelPrivate;
assert.ok(typeof gatewayToken === 'string' && gatewayToken.length >= 32);
const queryFamily = kernelPrivate.family === 'channel_followup';
const firstPurchaseFamily = kernelPrivate.family === 'first_purchase';
const assetsEnabled = Array.isArray(kernelPrivate.asset_capabilities) && kernelPrivate.asset_capabilities.length > 0;
if (queryFamily) {
  assert.ok(Array.isArray(refs.sessionIds) && refs.sessionIds.length === 2 && refs.sessionIds.includes(refs.sessionId));
}
const policyLog = [];
const upstreamRequire = createRequire(join(process.env.B0_BUILD_UPSTREAM ?? join(b0, 'upstream'), 'packages/api/gateway/package.json'));
const { WebSocket, WebSocketServer } = upstreamRequire('ws');
const wss = new WebSocketServer({ noServer: true, maxPayload: 65536 });
const links = new Set();
let refreshing;
async function writeGatewayState(generation) {
  await writeFile(join(runtime, 'gateway-private.json'), JSON.stringify({ launchUrl: `${origin}/?b0=${pass}`,
    pid: process.pid, upstream_generation: generation }), { mode: 0o600 });
}
async function refreshOwnedUpstream() {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    const latest = JSON.parse(await readFile(join(b0, 'current.json'), 'utf8'));
    assert.equal(latest.runtime, runtime, 'Cannot switch the gateway to another runtime');
    assert.equal(latest.pinned, current.pinned);
    assert.equal(latest.hostReadyGeneration, latest.hostGeneration);
    const fresh = JSON.parse(await readFile(join(runtime, 'browser-private.json'), 'utf8'));
    assert.equal(new URL(fresh.launchUrl).origin, upstreamOrigin);
    const exchange = await fetch(fresh.launchUrl, { redirect: 'manual', signal: AbortSignal.timeout(5000) });
    const cookie = exchange.headers.getSetCookie().map(value => value.split(';')[0]).join('; ');
    assert.ok(cookie);
    const boot = await fetch(`${upstreamOrigin}/`, { headers: { cookie }, signal: AbortSignal.timeout(5000) });
    assert.equal(boot.status, 200);
    const nextHtml = await boot.text();
    const exactNextUrls = refreshedPluginManifest(bootHtml, nextHtml, upstreamOrigin);
    internalCookie = cookie;
    bootHtml = nextHtml;
    pluginUrls = exactNextUrls;
    // Reconnect transport only. No automatic prompt/cancel or business replay.
    for (const link of links) link.terminate();
    for (const client of wss.clients) client.close(1012, 'B0 owned upstream restarted');
    await writeGatewayState(latest.hostGeneration);
    console.log(`B0_GATEWAY_REFRESHED native_generation=${latest.hostGeneration}`);
  })();
  try { await refreshing; } finally { refreshing = undefined; }
}
async function kernel(path, { method = 'GET', body, headers = {} } = {}) {
  return fetch(`http://127.0.0.1:${ports.kernel}${path}`, { method, headers: {
    'content-type': 'application/json', authorization: `Bearer ${gatewayToken}`, ...headers,
  }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(5000), redirect: 'error' });
}

async function currentAccess(sessionId = scope.sessionId) {
  return currentPermission(async () => {
    if (!sessionAllowed(scope, sessionId)) return false;
    const response = await kernel('/internal/native/context', {
      headers: queryFamily ? { 'x-runtime-session-id': sessionId } : {},
    });
    if (!response.ok) { await response.body?.cancel(); return false; }
    return (await response.json()).session_id === sessionId;
  });
}

function requestSession(method, request) {
  if (method === 'session/page') return request?.address?.sessionId;
  if (method === 'session/prompt' || method === 'session/cancel') return request?.sessionId;
  return undefined;
}

async function nativeMutation(method, request, rpcId, res) {
  let response;
  let accepted;
  const sessionId = request?.sessionId;
  const sessionHeaders = queryFamily ? { 'x-runtime-session-id': sessionId } : {};
  if (method === 'session/prompt') {
    if (!await currentAccess(sessionId)) return deny(res, rpcId);
    response = await kernel('/internal/native/prompt', { method: 'POST', body: request });
    accepted = await response.json();
  } else {
    if (!await currentAccess(sessionId)) return deny(res, rpcId);
    const contextResponse = await kernel('/internal/native/context', { headers: sessionHeaders });
    if (!contextResponse.ok) return deny(res, rpcId, contextResponse.status);
    const context = await contextResponse.json();
    if (context.session_id !== sessionId) return deny(res, rpcId);
    const runPath = firstPurchaseFamily ? '/api/v1/analytics-first-purchase/runs/'
      : queryFamily ? '/api/v1/analytics-query/runs/' : '/api/v1/analytics/runs/';
    const snapshots = await Promise.all(context.conversation.run_ids.map(async id => {
      const row = await kernel(`${runPath}${encodeURIComponent(id)}`, { headers: sessionHeaders });
      if (!row.ok) throw new Error('kernel run read failed');
      return row.json();
    }));
    const target = snapshots.find(row => row.diagnostics.execution_active)
      ?? snapshots.find(row => row.status === 'QUEUED');
    if (!target) {
      res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(JSON.stringify({ type: 'server-response', rpcId, result: { ok: true, value: { accepted: true } } }));
      return;
    }
    response = await kernel(`${runPath}${target.run_id}/cancel`, { method: 'POST', body: { reason: 'USER_REQUEST' },
      headers: { 'idempotency-key': `native-cancel-${rpcId}`, 'if-match': String(target.version), ...sessionHeaders } });
    accepted = await response.json();
  }
  if (!response.ok || typeof accepted.run_id !== 'string') return deny(res, rpcId, response.status);
  // Native UI sees its native acknowledgement; the header binds it to the
  // authoritative original FastAPI 202. Neither is a completion signal.
  res.writeHead(method === 'session/prompt' ? 202 : 200, { 'content-type': 'application/json', 'cache-control': 'no-store',
    'x-b0-run-id': accepted.run_id });
  res.end(JSON.stringify({ type: 'server-response', rpcId, result: { ok: true, value: { accepted: true } } }));
}
function equal(a, b) {
  return typeof a === 'string' && Buffer.byteLength(a) === Buffer.byteLength(b) && timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
function browserAuthenticated(req) {
  return (req.headers.cookie ?? '').split(';').some(s => equal(s.trim(), `shine-b0=${session}`));
}
function sameOrigin(req) {
  return req.headers.host === `127.0.0.1:${ports.gateway}` && (!req.headers.origin || req.headers.origin === origin)
    && (!req.headers['sec-fetch-site'] || ['same-origin', 'none'].includes(req.headers['sec-fetch-site']));
}
function audit(transport, method, allowed, reason) {
  if (policyLog.length < 10000) policyLog.push({ at: new Date().toISOString(), transport, method, allowed, reason });
}
function deny(res, rpcId = 'b0-denied', status = 403) {
  res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
  res.end(JSON.stringify({ type: 'server-response', rpcId, result: { ok: false,
    error: { code: 'gateway/forbidden', message: 'B0验证未开放此操作', details: {} } } }));
}
async function bodyOf(req) {
  const chunks = []; let size = 0;
  for await (const chunk of req) { size += chunk.length; if (size > 65536) throw new Error('body-too-large'); chunks.push(chunk); }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
async function httpHandler(req, res) {
  if (!sameOrigin(req)) return deny(res);
  const url = new URL(req.url, origin);
  if (req.method === 'GET' && url.pathname === '/' && equal(url.searchParams.get('b0'), pass)) {
    res.writeHead(303, { location: '/', 'set-cookie': `shine-b0=${session}; HttpOnly; SameSite=Strict; Path=/`, 'cache-control': 'no-store' }); res.end(); return;
  }
  if (!browserAuthenticated(req)) return deny(res, undefined, 401);
  if (assetsEnabled) {
    const mapped = mapAssetRoute(req.method, url.pathname, url.searchParams,
      firstPurchaseFamily ? 'first_purchase' : 'channel_followup');
    if (mapped) {
      if (mapped.kind === 'reject' || assetHeaderViolation(req.rawHeaders)) {
        audit('asset', url.pathname, false, mapped.kind === 'reject' ? 'asset-allowlist' : 'asset-header');
        return deny(res);
      }
      if (mapped.kind === 'status') {
        let live = false;
        try {
          const probe = await kernel(firstPurchaseFamily
            ? '/api/v1/analytics-first-purchase/dashboards' : '/api/v1/analytics/dashboards');
          live = probe.status === 200;
          await probe.body?.cancel?.();
        } catch {
          live = false;
        }
        if (!live) {
          res.writeHead(503, { 'content-type': 'application/json', 'cache-control': 'no-store' });
          res.end(JSON.stringify({
            http_api: 'UNAVAILABLE', analyses: false, cockpit: false, snapshot: true, synthetic: true,
          }));
          return;
        }
        res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
        res.end(JSON.stringify({
          http_api: 'CONNECTED', analyses: true, cockpit: true, snapshot: true, synthetic: true,
        }));
        return;
      }
      const headers = {};
      if (mapped.key && req.headers['idempotency-key']) headers['idempotency-key'] = req.headers['idempotency-key'];
      if (mapped.match && req.headers['if-match']) headers['if-match'] = req.headers['if-match'];
      let body;
      if (req.method !== 'GET') {
        try { body = await bodyOf(req); }
        catch { audit('asset', url.pathname, false, 'invalid-json'); return deny(res, undefined, 400); }
      }
      const response = await kernel(mapped.kernel, { method: req.method, headers, body });
      const out = { 'content-type': 'application/json', 'cache-control': 'no-store' };
      const etag = response.headers.get('etag');
      const location = response.headers.get('location');
      if (etag) out.etag = etag;
      if (location) out.location = location;
      res.writeHead(response.status, out);
      res.end(await response.text());
      return;
    }
  }
  if (!await currentAccess()) return deny(res);
  if (req.method === 'GET' && !url.search && brands.has(url.pathname)) {
    const asset = brands.get(url.pathname);
    res.writeHead(200, { 'content-type': asset.type, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
    res.end(asset.bytes); return;
  }
  if (req.method === 'GET' && resolveBoardSample(req.url)) {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store',
      'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
      'x-content-type-options': 'nosniff' });
    res.end(boardSampleHtml()); return;
  }
  // Read-only run projection for the native plugin. Browser capabilities and
  // DSH credentials never cross this boundary. No generic HTTP proxy.
  if (req.method === 'GET' && !url.search && (url.pathname === '/b0/context' || /^\/b0\/runs\/run_[a-f0-9]{32}$/.test(url.pathname))) {
    const headerSession = req.headers['x-runtime-session-id'];
    if (queryFamily) {
      if (!sessionAllowed(scope, headerSession) || !await currentAccess(headerSession)) return deny(res);
      const path = url.pathname === '/b0/context' ? '/internal/native/context'
        : url.pathname.replace('/b0/runs/', '/api/v1/analytics-query/runs/');
      const response = await kernel(path, { headers: { 'x-runtime-session-id': headerSession } });
      res.writeHead(response.status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(await response.text()); return;
    }
    if (firstPurchaseFamily) {
      const path = url.pathname === '/b0/context' ? '/internal/native/context'
        : url.pathname.replace('/b0/runs/', '/api/v1/analytics-first-purchase/runs/');
      const response = await kernel(path);
      res.writeHead(response.status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(await response.text()); return;
    }
    const path = url.pathname === '/b0/context' ? '/internal/native/context' : url.pathname.replace('/b0/runs/', '/api/v1/analytics/runs/');
    const response = await kernel(path);
    res.writeHead(response.status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(await response.text()); return;
  }
  if (url.pathname.startsWith('/api/')) {
    const method = url.pathname.slice(5);
    // Reject Fetch/binary endpoints before attempting JSON parsing. This B0
    // surface admits JSON RPC only; query-bearing API URLs are not its contract.
    if (req.method !== 'POST' || url.search || req.headers['content-type']?.split(';')[0].trim().toLowerCase() !== 'application/json') {
      audit('http', method, false, 'not-json-rpc'); return deny(res);
    }
    let envelope;
    try { envelope = await bodyOf(req); } catch { audit('http', method, false, 'invalid-json'); return deny(res, undefined, 400); }
    if (!envelope || Array.isArray(envelope) || envelope.type !== 'client-request' || envelope.method !== method || typeof envelope.rpcId !== 'string'
      || envelope.rpcId.length === 0 || envelope.rpcId.length > 256
      || Object.keys(envelope).some(k => !['type', 'method', 'rpcId', 'payload'].includes(k))) return deny(res);
    const request = envelope.payload?.args?.request;
    // inFlight is intentionally not tracked here: admission, idempotency and
    // quota are one transaction in the FastAPI run kernel.
    const permit = authorizeHttp(method, envelope.payload, scope);
    audit('http', method, permit.allowed, permit.reason);
    if (!permit.allowed) return deny(res, envelope.rpcId);
    const targetSession = requestSession(method, request);
    if (targetSession !== undefined && !await currentAccess(targetSession)) return deny(res, envelope.rpcId);
    if (['session/prompt', 'session/cancel'].includes(method)) return nativeMutation(method, request, envelope.rpcId, res);
    const response = await fetch(`${upstreamOrigin}/api/${method}`, { method: 'POST',
      headers: { 'content-type': 'application/json', cookie: internalCookie }, body: JSON.stringify(envelope), signal: AbortSignal.timeout(10000) });
    const filterScope = targetSession ? { ...scope, sessionId: targetSession } : scope;
    const result = safeRpcResult(await response.json(), envelope.rpcId, method, filterScope, filterHttpResult);
    if (result === null) return deny(res, envelope.rpcId, 502);
    res.writeHead(response.status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify(result)); return;
  }
  const staticPath = !url.search && (url.pathname === '/' || url.pathname.startsWith('/assets/') || /^\/favicon\.(svg|ico|png)$/.test(url.pathname));
  const pluginPath = pluginUrls.has(new URL(req.url, upstreamOrigin).href);
  if (req.method !== 'GET' || (!staticPath && !pluginPath)) { audit('fetch', url.pathname, false, 'static-allowlist'); return deny(res); }
  const response = await fetch(`${upstreamOrigin}${url.pathname}${url.search}`, { headers: { cookie: internalCookie, 'accept-encoding': 'identity' }, redirect: 'manual', signal: AbortSignal.timeout(10000) });
  // Node fetch decompresses automatically; never forward compressed-length or
  // content-encoding, upstream auth cookies, redirects, or private headers.
  res.writeHead(response.status, { 'content-type': response.headers.get('content-type') ?? 'application/octet-stream', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' });
  res.end(Buffer.from(await response.arrayBuffer()));
}
const server = createServer((req, res) => { void httpHandler(req, res).catch(error => {
  audit('handler', 'error', false, 'upstream-unavailable'); if (!res.headersSent) deny(res, undefined, 502); else res.end();
}); });
server.on('upgrade', (req, socket, head) => { void (async () => {
  if (!sameOrigin(req) || !browserAuthenticated(req) || req.url !== '/api/remote.mux') {
    socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); return;
  }
  if (!await currentAccess() || wss.clients.size >= 8) {
    socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); return;
  }
  if (socket.destroyed) return;
  wss.handleUpgrade(req, socket, head, client => {
    const upstream = new WebSocket(`ws://127.0.0.1:${ports.web}/api/remote.mux`, { headers: { cookie: internalCookie }, maxPayload: 1024 * 1024 });
    const seen = new Set(); const active = new Map(); const pending = [];
    const denied = () => { client.close(1008, 'B0 current permission unavailable'); upstream.terminate(); };
    const incoming = permissionFence(currentAccess, denied, { queueLimit: 16 });
    const outgoing = permissionFence(currentAccess, denied, { queueLimit: 16, pollMs: 1000 });
    links.add(upstream);
    const send = value => { if (client.readyState === WebSocket.OPEN) client.send(JSON.stringify(value)); };
    const forward = message => { if (upstream.readyState === WebSocket.OPEN) upstream.send(JSON.stringify(message)); else if (pending.length < 32) pending.push(message); else client.close(1008, 'B0 stream limit'); };
    upstream.on('open', () => { for (const message of pending.splice(0)) forward(message); });
    client.on('message', (data, binary) => { void incoming.enqueue(async () => {
      try {
        if (binary) throw new Error('binary denied');
        const message = JSON.parse(String(data));
        if (message.type === 'open' && (seen.size >= 64 || active.size >= 8)) { client.close(1008, 'B0 stream limit'); return; }
        const permit = authorizeStream(message, { ...scope, seenStreamIds: seen, activeStreamIds: new Set(active.keys()) });
        audit('ws', message.endpoint ?? message.type, permit.allowed, permit.reason);
        if (!permit.allowed) { send({ type: 'error', streamId: message.streamId ?? 'invalid', error: { code: 'gateway/forbidden', message: 'B0 stream denied', details: {} } }); return; }
        if (message.type === 'open') {
          const boundSession = message.endpoint === 'session/follow' ? message.payload?.args?.request?.address?.sessionId : undefined;
          if (message.endpoint === 'session/follow' && !await currentAccess(boundSession)) {
            send({ type: 'error', streamId: message.streamId, error: { code: 'gateway/forbidden', message: 'B0 stream denied', details: {} } });
            return;
          }
          seen.add(message.streamId);
          active.set(message.streamId, { endpoint: message.endpoint, sessionId: boundSession });
        }
        forward(message);
        if (message.type === 'cancel') active.delete(message.streamId);
      } catch { client.close(1008, 'B0 invalid frame'); }
    }); });
    upstream.on('message', (data, binary) => { void outgoing.enqueue(() => {
      try {
        if (binary) throw new Error('binary upstream');
        const message = JSON.parse(String(data));
        const binding = active.get(message.streamId);
        if (!binding) return;
        const endpoint = binding.endpoint;
        if (message.type === 'item') {
          const filterScope = endpoint === 'session/follow' ? { ...scope, sessionId: binding.sessionId } : scope;
          const value = filterStreamItem(endpoint, message.value, filterScope);
          if (value !== null) send({ type: 'item', streamId: message.streamId, value });
        } else if (message.type === 'end') { send(message); active.delete(message.streamId); }
        else if (message.type === 'error') send({ type: 'error', streamId: message.streamId, error: { code: 'gateway/internal', message: 'B0 upstream stream error', details: {} } });
      } catch { client.close(1011, 'B0 invalid upstream'); }
    }); });
    client.on('close', () => { incoming.close(); outgoing.close(); upstream.terminate(); links.delete(upstream); });
    client.on('error', () => client.terminate());
    upstream.on('close', () => { client.close(); links.delete(upstream); });
    upstream.on('error', () => client.close(1011, 'B0 upstream unavailable'));
  });
})().catch(() => { socket.destroy(); }); });
await new Promise((ok, fail) => { server.once('error', fail); server.listen(ports.gateway, '127.0.0.1', ok); });
await writeGatewayState(current.hostGeneration);
console.log(`B0_GATEWAY_READY ${origin}/ (native credential withheld; synthetic owner only)`);
process.on('SIGUSR1', () => { void refreshOwnedUpstream().catch(() => {
  console.error('B0_GATEWAY_REFRESH_FAILED; no requests replayed or policy widened');
}); });
let stopping = false;
async function stop() {
  if (stopping) return; stopping = true;
  for (const link of links) link.terminate();
  for (const client of wss.clients) client.terminate();
  await new Promise(ok => wss.close(ok));
  await new Promise(ok => server.close(ok));
  await writeFile(join(runtime, 'gateway-evidence.json'), JSON.stringify({ policyLog, authority: 'FastAPI RunStore; no Node ledger' }, null, 2), { mode: 0o600 });
  console.log('B0_GATEWAY_STOPPED');
}
process.once('SIGTERM', () => { void stop(); });
process.once('SIGINT', () => { void stop(); });
