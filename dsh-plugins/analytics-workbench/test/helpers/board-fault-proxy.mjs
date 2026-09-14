/** Test-only one-shot transport faults in front of an owned synthetic HTTP service. */
import assert from 'node:assert/strict';
import { createServer, request } from 'node:http';
import { once } from 'node:events';

const prefix = '/api/v1/analytics/board-spec';
const targets = {
  'confirm-before': ['POST', /^\/previews\/[A-Za-z0-9_-]+\/confirm$/],
  'confirm-after': ['POST', /^\/previews\/[A-Za-z0-9_-]+\/confirm$/],
  get: ['GET', /^\/boards\/[A-Za-z0-9_-]+$/],
  list: ['GET', /^\/boards$/],
};

export async function mountBoardFaultProxy(targetOrigin) {
  const target = new URL(targetOrigin);
  assert.equal(target.protocol, 'http:');
  assert.equal(target.hostname, '127.0.0.1');
  assert.ok(target.port && !['6677', '4327', '8000', '5173'].includes(target.port));
  assert.equal(target.href, `${target.origin}/`);
  let armed = null;
  const events = [], confirmationKeys = new Map();
  const server = createServer((incoming, outgoing) => {
    const url = new URL(incoming.url, 'http://localhost');
    const path = url.pathname;
    if (!path.startsWith(`${prefix}/`)) { outgoing.writeHead(404).end(); return; }
    const operation = path.slice(prefix.length);
    const match = armed && incoming.method === targets[armed][0] && targets[armed][1].test(operation);
    const fault = match ? armed : null;
    if (match) armed = null;
    const event = { method: incoming.method, path: operation, fault, forwarded: false };
    if (incoming.method === 'POST' && targets['confirm-after'][1].test(operation)) {
      const key = incoming.headers['idempotency-key'];
      event.same_key_as_first = confirmationKeys.has(path) ? confirmationKeys.get(path) === key : null;
      if (!confirmationKeys.has(path)) confirmationKeys.set(path, key);
    }
    events.push(event);
    if (fault && fault !== 'confirm-after') {
      incoming.resume();
      event.status = 503;
      outgoing.writeHead(503, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      outgoing.end(JSON.stringify({ error: { code: 'INJECTED_UNAVAILABLE', message: '隔离验收：本次请求在到达保存服务前失败。' } }));
      return;
    }
    event.forwarded = true;
    const forwarded = request(new URL(`${path}${url.search}`, target), {
      method: incoming.method, headers: { ...incoming.headers, host: target.host, connection: 'close' },
    }, response => {
      event.status = response.statusCode;
      if (fault === 'confirm-after' && response.statusCode === 200) {
        // Consume the actual committed response before breaking transport. Never fabricate success.
        const chunks = []; let bytes = 0;
        response.on('data', chunk => {
          bytes += chunk.length;
          if (bytes > 2_200_000) response.destroy(new Error('isolated response limit'));
          else chunks.push(chunk);
        });
        response.once('end', () => {
          try { event.committed_version = JSON.parse(Buffer.concat(chunks).toString('utf8')).spec.version; }
          catch { event.invalid_commit_response = true; }
          event.reply_dropped = true;
          outgoing.destroy();
        });
        response.once('error', () => outgoing.destroy());
      } else {
        outgoing.writeHead(response.statusCode, response.headers);
        response.pipe(outgoing);
        response.once('error', () => outgoing.destroy());
      }
    });
    forwarded.setTimeout(10000, () => forwarded.destroy(new Error('isolated upstream timeout')));
    forwarded.once('error', () => { event.transport_error = true; outgoing.destroy(); });
    incoming.once('aborted', () => forwarded.destroy());
    incoming.pipe(forwarded);
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  return {
    origin: `http://127.0.0.1:${server.address().port}`,
    arm(mode) { assert.ok(Object.hasOwn(targets, mode)); assert.equal(armed, null, 'previous fault not consumed'); armed = mode; },
    audit: () => ({ armed, events: structuredClone(events) }),
    async close() { server.closeAllConnections(); await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve())); },
  };
}
