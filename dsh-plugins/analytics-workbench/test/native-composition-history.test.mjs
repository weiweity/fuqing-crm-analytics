import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { seedCompositionHistory, apply } from './helpers/native-composition-history.mjs';
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? fileURLToPath(new URL('../../../.context/dsh-b0/upstream', import.meta.url)));
const { Session, SessionId, SESSION_FORMAT_VERSION } = await import(pathToFileURL(join(upstream, 'packages/core/session/lib/index.js')).href);

const cwd = fileURLToPath(new URL('../../../.context/checks/ai-cockpit-goal/native-composition-runtime-test/workspace', import.meta.url));
function session(id = 'session-composition-synthetic', workspace = cwd) {
  return Session.create(SessionId(id), [], { version: SESSION_FORMAT_VERSION, id: SessionId(id), createdAt: 1, isSeeded: false, cwd: workspace });
}

test('composition history uses the pinned native surface, remains explicit synthetic and is idempotent', () => {
  const value = session();
  assert.equal(seedCompositionHistory(value), true);
  const events = value.snapshotEvents();
  assert.equal(value.deriveMessages().length, 1);
  assert.match(value.deriveMessages()[0].content[0].text, /预置历史，不是模型回答/);
  assert.equal(events.filter(event => /llm|request\/header|assistant\/|tool\//.test(event.type)).length, 0);
  assert.equal(seedCompositionHistory(value), false);
  assert.deepEqual(value.snapshotEvents(), events);
});

test('history seed refuses the selected ID outside a disposable composition workspace', () => {
  const value = session('session-composition-synthetic', '/tmp/not-the-composition-fixture');
  const before = value.snapshotEvents();
  assert.throws(() => seedCompositionHistory(value), /disposable workspace/);
  assert.deepEqual(value.snapshotEvents(), before);
});

test('history seed leaves every other native session untouched', () => {
  const value = session('another-session');
  const before = value.snapshotEvents();
  assert.equal(seedCompositionHistory(value), false);
  assert.deepEqual(value.snapshotEvents(), before);
});

test('fixture endpoint rejects unauthenticated and non-POST requests, and awaits native durability', async () => {
  const value = session(); let handler, flushes = 0;
  apply({ effect: fn => fn(), webServer: { register(route) { handler = route.handler; return () => {}; } },
    connection: { requestRejection: req => req.authorized ? undefined : 401 },
    sessions: { get: id => id === 'session-composition-synthetic' ? value : undefined,
      async flush(actual) { assert.equal(actual, value); flushes++; return true; } } });
  const request = async (method, authorized) => {
    const response = { status: null, body: '', writeHead(status) { this.status = status; }, end(body = '') { this.body = body; } };
    await handler({ method, authorized }, response); return response;
  };
  assert.equal((await request('POST', false)).status, 401);
  assert.equal((await request('GET', true)).status, 405);
  assert.equal(value.deriveMessages().length, 0); assert.equal(flushes, 0);
  const result = await request('POST', true);
  assert.equal(result.status, 200); assert.equal(flushes, 1);
  assert.deepEqual(JSON.parse(result.body), { seeded: true, messages: 1 });
  assert.deepEqual(JSON.parse((await request('POST', true)).body), { seeded: false, messages: 1 });
});
