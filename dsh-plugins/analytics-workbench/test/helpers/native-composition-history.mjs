/** Test-only authenticated, fixed-session history; no model adapter or arbitrary tools/data. */
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { relative, resolve, join } from 'node:path';
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? fileURLToPath(new URL('../../../../.context/dsh-b0/upstream', import.meta.url)));
const { createUserMessage } = await import(pathToFileURL(join(upstream, 'packages/llm/llm/lib/index.js')).href);

export const name = 'composition-fixture-history';
export const inject = ['sessions', 'webServer', 'connection'];
const evidence = fileURLToPath(new URL('../../../../.context/checks/ai-cockpit-goal/', import.meta.url));

export function seedCompositionHistory(session) {
  if (String(session.id) !== 'session-composition-synthetic') return false;
  const cwd = relative(evidence, session.header.cwd ?? '');
  assert.match(cwd, /^native-composition-runtime-[A-Za-z0-9]+\/workspace$/, 'history fixture must stay in its disposable workspace');
  if (session.snapshotEvents().some(event => event.type === 'user/message')) return false;
  session.append('turn/start', { turn: 1 });
  session.append('user/message', createUserMessage({
    content: [{ type: 'text', text: '合成验收记录：用于检查驾驶舱与原生文件侧栏的共存。这是预置历史，不是模型回答，也不是真实问数结果。' }],
    source: { kind: 'user' },
  }), { surfaceOp: 'append' });
  session.append('turn/end', { turn: 1, reason: { kind: 'completed' } });
  return true;
}

export function apply(ctx) {
  // Seed only AFTER native session/create completes, and require the native
  // durability checkpoint before this fixture can be used as restart evidence.
  ctx.effect(() => ctx.webServer.register({ kind: 'exact', path: '/__composition_seed__',
    async handler(req, res) {
      const rejection = ctx.connection.requestRejection(req);
      if (rejection) { res.writeHead(rejection); res.end(); return; }
      if (req.method !== 'POST') { res.writeHead(405); res.end(); return; }
      const session = ctx.sessions.get('session-composition-synthetic');
      if (!session) { res.writeHead(404); res.end(); return; }
      try {
        const seeded = seedCompositionHistory(session);
        assert.equal(await ctx.sessions.flush(session), true, 'native persistence must acknowledge the fixture');
        res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
        res.end(JSON.stringify({ seeded, messages: session.deriveMessages().length }));
      } catch {
        res.writeHead(500); res.end('synthetic history seed failed');
      }
    } }), 'composition-fixture: authenticated fixed synthetic history');
}
