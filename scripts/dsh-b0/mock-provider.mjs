/** Test-provider adapter, not a business/runtime adapter. The pinned official
 * mock repeats one tool-call ID for every request. Namespace wire IDs per HTTP
 * request so consecutive native turns obey the session-wide identity contract.
 * No result, argument, prompt, outcome, retry, or DSH source is rewritten.
 */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';

export function namespaceToolCallLine(line, requestNumber) {
  if (!line.startsWith('data:') || line.slice(5).trim() === '[DONE]') return line;
  const value = JSON.parse(line.slice(5));
  let changed = false;
  for (const choice of value.choices ?? []) {
    for (const tool of choice.delta?.tool_calls ?? []) {
      if (typeof tool.id === 'string' && tool.id.length) {
        tool.id = `b0-request-${requestNumber}:${tool.id}`;
        changed = true;
      }
    }
  }
  return changed ? `data: ${JSON.stringify(value)}` : line;
}

export async function startB0MockProvider(startOfficial, options) {
  const official = await startOfficial({ ...options, host: '127.0.0.1', port: 0 });
  assert.equal(new URL(official.baseURL).hostname, '127.0.0.1');
  let requestNumber = 0;
  const inflight = new Set();
  const server = createServer((req, res) => {
    const abort = new AbortController();
    inflight.add(abort);
    res.once('close', () => { if (!res.writableFinished) abort.abort(); });
    void (async () => {
      if (req.method !== 'POST' || !['/v1/chat/completions', '/chat/completions'].includes(req.url)) {
        res.writeHead(404).end(); return;
      }
      const requestId = ++requestNumber;
      const chunks = [];
      let size = 0;
      for await (const chunk of req) {
        size += chunk.length;
        assert.ok(size <= 2 * 1024 * 1024, 'B0 fixture request too large');
        chunks.push(chunk);
      }
      const response = await fetch(`${official.baseURL}${req.url}`, {
        method: 'POST', headers: { 'content-type': 'application/json', authorization: req.headers.authorization ?? '' },
        body: Buffer.concat(chunks), signal: abort.signal, redirect: 'error',
      });
      const type = response.headers.get('content-type') ?? 'application/octet-stream';
      res.writeHead(response.status, { 'content-type': type, 'cache-control': 'no-store' });
      if (!type.startsWith('text/event-stream')) { res.end(await response.text()); return; }
      const decoder = new TextDecoder();
      let pending = '';
      for await (const chunk of response.body) {
        pending += decoder.decode(chunk, { stream: true });
        assert.ok(pending.length <= 262144, 'B0 fixture SSE frame too large');
        let end;
        while ((end = pending.indexOf('\n')) >= 0) {
          const line = pending.slice(0, end);
          pending = pending.slice(end + 1);
          const writable = res.write(namespaceToolCallLine(line, requestId) + '\n');
          if (!writable) await once(res, 'drain', { signal: abort.signal });
        }
      }
      pending += decoder.decode();
      if (pending) res.write(namespaceToolCallLine(pending, requestId));
      res.end();
    })().catch(() => {
      if (!res.headersSent) res.writeHead(502, { 'content-type': 'application/json' }).end('{"error":"B0 fixture transport failed"}');
      else res.destroy();
    }).finally(() => inflight.delete(abort));
  });
  try {
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(options.port ?? 0, '127.0.0.1', () => { server.off('error', reject); resolve(); });
    });
  } catch (error) { await official.close(); throw error; }
  return {
    baseURL: `http://127.0.0.1:${server.address().port}`,
    get requests() { return official.requests; },
    async close() {
      for (const abort of inflight) abort.abort();
      server.closeAllConnections();
      await new Promise(resolve => server.close(resolve));
      await official.close();
    },
  };
}
