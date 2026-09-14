/** Official authenticated Connection extension, removed with this business plugin. */
import type { Context } from '@deepseek-ai/cordis';
import { clientRequestSchema } from '@deepseek-ai/dsh-client-connection';
import { handleBoardBrowserCall } from './board-spec/browser-api.mjs';
import { BOARD_API_ENDPOINT } from './board-spec/connection-call.mjs';

export const name = 'analytics-workbench-board-browser-api';
export const inject = ['connection', 'webServer'];

export function apply(ctx: Context): void {
  // The pinned rpc.handle dedicated carrier cannot resolve webServer from the
  // Connection provider's shadow scope in a full Host. Its public exact Fetch
  // extension uses the already-mounted /api carrier and the same trust fence.
  ctx.connection.fetch.register({ path: `/api/${BOARD_API_ENDPOINT}`, methods: ['POST'], requestBody: 'buffered',
    async fetch(request) {
      let input: unknown;
      try { input = await request.json(); } catch { return new Response('invalid JSON', { status: 400 }); }
      const parsed = clientRequestSchema.safeParse(input);
      if (!parsed.success) return new Response('invalid envelope', { status: 400 });
      const message = parsed.data, body = message.payload as { operation?: unknown; payload?: unknown } | null;
      const valid = message.method === BOARD_API_ENDPOINT && body !== null && typeof body === 'object'
        && !Array.isArray(body) && typeof body.operation === 'string' && Object.hasOwn(body, 'payload')
        && Object.keys(body).length === 2;
      const result = valid ? await handleBoardBrowserCall(body.operation as string, body.payload, request.signal)
        : { ok: false, error: { code: 'gateway/bad-request', message: 'Invalid board request envelope', details: {} } };
      return Response.json({ type: 'server-response', rpcId: message.rpcId, result }, { headers: { 'cache-control': 'no-store' } });
    },
  });
}
