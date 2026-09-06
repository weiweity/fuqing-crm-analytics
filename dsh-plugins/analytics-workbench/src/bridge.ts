/** Private Host protocol: native prompt/cancel plus journal + driver exit proof.
 * No business ledger, scheduler, retries, model loop, SQL, or browser endpoint.
 */
import type { Context } from '@deepseek-ai/cordis';
import type {} from '@deepseek-ai/dsh-api-session-controller';
import { createServer } from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { summarizeRequest, evidenceFor, requestIdOf } from './native-evidence.mjs';
import { registeredSessionIds } from './runtime-family.mjs';

export const name = 'analytics-workbench-b0-bridge';
export const inject = ['agents', 'sessions', 'sessionController'];
const id = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);

export function apply(ctx: Context): void {
  const token = process.env.B0_RUNTIME_TOKEN;
  const sessions = registeredSessionIds();
  if (!token || token.length < 32) throw new Error('B0 bridge requires explicit isolated capabilities');
  const expected = Buffer.from(`Bearer ${token}`);
  let admitting = false;
  const server = createServer((req, res) => {
    const respond = (status: number, value: unknown) => {
      res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(JSON.stringify(value));
    };
    void (async () => {
      const auth = Buffer.from(req.headers.authorization ?? '');
      if (req.method !== 'POST' || auth.length !== expected.length || !timingSafeEqual(auth, expected)) return respond(401, { error: 'unauthorized' });
      let raw = '';
      for await (const chunk of req) { raw += chunk; if (Buffer.byteLength(raw) > 65536) return respond(413, { error: 'too-large' }); }
      const intent = JSON.parse(raw);
      if (req.url === '/health') return respond(200, { ready: sessions.every(sessionId => ctx.agents.get(sessionId as never) !== undefined) });
      if (!intent || ['run_id', 'attempt_id', 'session_id', 'request_id'].some(key => !id(intent[key])) || !sessions.includes(intent.session_id)) return respond(409, { error: 'binding' });
      let agent = ctx.agents.get(intent.session_id as never);
      if (!agent && req.url === '/observe') {
        // The pinned official resume path first takes the cross-process
        // session write lease, appends interrupted-tail closers and attaches
        // an idle agent. It does not send/replay a prompt or wake the inbox.
        // A still-live holder rejects the lease: never adopt by saved PID.
        const restored = await ctx.sessionController.resolveAgent(intent.session_id as never);
        if ('error' in restored) return respond(503, { error: 'native-unavailable' });
        agent = restored.agent;
      }
      if (!agent) return respond(200, evidenceFor(intent, { received: false, successful_call_ids: [] }, false));
      let summary = summarizeRequest(agent.session.snapshotEvents(), intent.request_id);
      if (req.url === '/dispatch') {
        if (summary.received) return respond(200, { accepted: true });
        if (admitting || agent.status !== 'idle' || agent.inbox.hasPending) return respond(409, { error: 'agent-busy' });
        const request = intent.payload?.native_request ?? { sessionId: intent.session_id, requestId: intent.request_id, mode: 'queue',
          content: [{ type: 'text', text: intent.payload?.question }], clientTimeZone: 'Asia/Shanghai' };
        if (request.sessionId !== intent.session_id || request.requestId !== intent.request_id || request.mode !== 'queue'
          || request.content?.length !== 1 || request.content[0].type !== 'text' || typeof request.content[0].text !== 'string'
          || !request.content[0].text.trim() || request.content[0].text.length > 8000) return respond(409, { error: 'payload' });
        admitting = true;
        try {
          const receipt = await ctx.sessionController.prompt(request, new AbortController().signal);
          await ctx.sessions.flush(agent.session);
          return respond(200, receipt);
        } finally { admitting = false; }
      }
      if (req.url === '/cancel') {
        const pending = [...agent.inbox.nextStep, ...agent.inbox.nextTurn].filter(message => requestIdOf(message) === intent.request_id);
        if (summary.currentRequestId !== intent.request_id && pending.length === 0) return respond(409, { error: 'not-current-request' });
        for (const message of pending) agent.inbox.remove(message.id);
        // Do not drop a different request's inbox. The FastAPI slot prevents a
        // newer dispatch until observe independently proves this driver's exit.
        if (summary.currentRequestId === intent.request_id) agent.cancel({ kind: 'user' }, { keepInbox: true });
        await ctx.sessions.flush(agent.session);
        return respond(200, { accepted: true });
      }
      if (req.url !== '/observe') return respond(404, { error: 'not-found' });
      const idle = await Promise.race([agent.whenIdle().then(() => true), delay(80, false)]);
      const durable = idle && await ctx.sessions.flush(agent.session);
      summary = summarizeRequest(agent.session.snapshotEvents(), intent.request_id);
      const exited = idle && durable && ctx.agents.get(intent.session_id as never) === agent && agent.status === 'idle' && !agent.inbox.hasPending;
      return respond(200, evidenceFor(intent, summary, exited));
    })().catch(() => { if (!res.headersSent) respond(503, { error: 'native-unavailable' }); else res.end(); });
  });
  ctx.effect(async () => {
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(4316, '127.0.0.1', () => { server.off('error', reject); resolve(); });
    });
    return async () => { server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve())); };
  }, 'analytics-b0: private native bridge');
}
