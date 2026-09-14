/** Strict Cordis inject for native session.prompt. Uses compiled client + real Context. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { ok } from './helpers/library-board-fixtures.mjs';

const plugin = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const pin = JSON.parse(await readFile(join(plugin, 'toolchain.json'), 'utf8'));
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: upstream, encoding: 'utf8' }).trim(), pin.upstream_sha);
const webRequire = createRequire(join(upstream, 'apps/web/package.json'));
const { Context, Service } = createRequire(join(plugin, 'package.json'))('@deepseek-ai/cordis');
const stores = await import(pathToFileURL(join(upstream, 'packages/client/store/lib/index.js')).href);
const source = await readFile(join(plugin, 'lib/client.js'), 'utf8');

/** R1 compiled inject: top-level remote only. Kept as the nested-inject failure. */
const R1_INJECT = ['slots', 'sessions', 'theme', 'layout', 'remote'];

class ClientRemoteLike extends Service {
  constructor(ctx) {
    super(ctx, 'remote');
  }
}

class RemoteSessionLike extends Service {
  constructor(ctx, promptImpl) {
    super(ctx, 'remote.session');
    this.prompt = promptImpl;
  }
}

function loadClient() {
  const seed = new Map([
    ['react', webRequire('react')],
    ['react-dom', webRequire('react-dom')],
    ['react/jsx-runtime', webRequire('react/jsx-runtime')],
    ['@deepseek-ai/dsh-client-store', stores],
  ]);
  let factoryRow;
  const previousWindow = globalThis.window;
  globalThis.window = {
    localStorage: { getItem: () => null },
    crypto,
    __ModuleLoader__: { load: row => { factoryRow = row; } },
  };
  try { new Function(source)(); }
  finally { globalThis.window = previousWindow; }
  return factoryRow.factory(spec => {
    assert.ok(seed.has(spec), `unexpected browser require: ${spec}`);
    return seed.get(spec);
  });
}

const SESSION_ID = 'native_session';

async function boot(t, {
  inject: injectOverride,
  provideRemote = true,
  hideRemoteBehindIsolate = false,
  hostLikeRemote = true,
  accept = true,
  saved = {
    spec: {
      schema_version: 'board-spec/v1',
      board_id: 'board_test',
      version: 1,
      title: '合成经营看板',
      session_id: SESSION_ID,
      blocks: [{
        block_id: 'note',
        title: '说明',
        kind: 'TEXT',
        library_version: 'board-components/v1',
        props: {
          content: '初始说明', align: 'start', text_style: 'body',
          subtitle: '', tone: 'neutral', density: 'comfortable',
        },
        layout: { x: 0, y: 0, w: 6, h: 5 },
        source_result_id: null,
      }],
    },
    facts_by_result_id: {},
  },
} = {}) {
  const client = loadClient();
  const root = new Context();
  const ctx = hostLikeRemote
    ? root.isolate('remote').isolate('remote.session')
    : root.isolate('remote');
  const entries = [];
  const prompts = [];
  const slotDisposers = [];
  const snapshot = {
    phase: 'ready',
    ids: [SESSION_ID],
    current: SESSION_ID,
    byId: { [SESSION_ID]: { id: SESSION_ID } },
  };
  const promptImpl = async (payload) => {
    prompts.push(payload);
    return { ok: true, value: { accepted: accept } };
  };
  const remotePlain = { session: { prompt: promptImpl } };
  ctx.provide('slots', {
    inject(_name, callback) {
      const dispose = callback();
      if (typeof dispose === 'function') slotDisposers.push(dispose);
    },
    register(options, component) {
      entries.push({ options, component });
      return () => {
        const index = entries.findIndex(row => row.options === options);
        if (index >= 0) entries.splice(index, 1);
      };
    },
  });
  ctx.provide('sessions', {
    list: { getSnapshot: () => snapshot, subscribe: () => () => {} },
    open(id) { snapshot.current = id; },
    clear() {},
    create() { throw new Error('native prompt inject test must not create a session'); },
  });
  ctx.provide('theme', {
    overrideTokens: () => () => {},
    getTheme: () => ({ active: { colorScheme: 'dark' } }),
  });
  ctx.provide('layout', { selectPanel() {} });
  if (hostLikeRemote) {
    if (hideRemoteBehindIsolate) {
      await root.plugin({
        name: 'client-remote-like',
        apply: (c) => { new ClientRemoteLike(c); },
      }).await();
      await root.plugin({
        name: 'remote.session',
        apply: (c) => { new RemoteSessionLike(c, promptImpl); },
      }).await();
    } else if (provideRemote) {
      await ctx.plugin({
        name: 'client-remote-like',
        apply: (c) => { new ClientRemoteLike(c); },
      }).await();
      await ctx.plugin({
        name: 'remote.session',
        apply: (c) => { new RemoteSessionLike(c, promptImpl); },
      }).await();
    }
  } else if (hideRemoteBehindIsolate) {
    root.provide('remote', remotePlain);
  } else if (provideRemote) {
    ctx.provide('remote', remotePlain);
  }
  let currentEdit = null;
  ctx.provide('connection', {
    rpc: {
      async call(path, endpoint, body) {
        const operation = body?.operation;
        const payload = body?.payload ?? {};
        if (path !== '/api' || endpoint !== 'shine-mage-board') {
          throw new Error(`unexpected rpc ${JSON.stringify({ path, endpoint, body })}`);
        }
        if (operation === 'list') return ok({ items: [{
          board_id: saved.spec.board_id, session_id: saved.spec.session_id,
          title: saved.spec.title, version: saved.spec.version,
        }] });
        if (operation === 'get') return { ok: true, value: JSON.parse(JSON.stringify(saved)) };
        if (operation === 'current_edit') return ok(currentEdit);
        if (operation === 'select_edit') {
          currentEdit = {
            schema_version: 'board-edit-context/v1',
            edit_context_id: 'edit_' + 'a'.repeat(32),
            board_id: saved.spec.board_id, base_version: saved.spec.version,
            block_id: payload.block_id, session_id: saved.spec.session_id,
            status: 'OPEN', preview_id: null, expires_at_ms: Date.now() + 10000,
            block: saved.spec.blocks.find(block => block.block_id === payload.block_id),
            facts_by_result_id: saved.facts_by_result_id,
          };
          return ok(currentEdit);
        }
        throw new Error(operation);
      },
    },
  });
  const fiber = ctx.plugin({
    name: client.name,
    inject: injectOverride ?? [...client.inject],
    apply: client.apply,
  });
  await fiber.await();
  const disposeSlots = () => {
    while (slotDisposers.length) slotDisposers.pop()();
  };
  t.after(async () => {
    await fiber.dispose();
    disposeSlots();
  });
  return { client, ctx, entries, prompts, fiber, saved, disposeSlots, currentEdit: () => currentEdit };
}

function generateNative(entries) {
  const dock = entries.find(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit');
  assert.ok(dock, 'generate dock was not registered');
  return dock.options.inject().generateNative;
}

function libraryOf(entries) {
  const footer = entries.find(row => row.options.id === 'shine-mage.analytics-b0.footer');
  assert.ok(footer, 'footer was not registered');
  return footer.options.inject().library;
}

function clientInjectWithout(inject, names) {
  const drop = new Set(Array.isArray(names) ? names : [names]);
  const next = inject.filter(item => !drop.has(item));
  assert.ok(next.length < inject.length);
  return next;
}

test('undeclared remote is rejected by the real Cordis loader even when provided', async t => {
  const { entries } = await boot(t, {
    inject: clientInjectWithout(loadClient().inject, ['remote', 'remote.session']),
    provideRemote: false,
    hideRemoteBehindIsolate: true,
    hostLikeRemote: false,
  });
  await assert.rejects(
    generateNative(entries)(SESSION_ID),
    /cannot get property "remote" without inject/,
  );
});

test('plain remote object does not enforce nested session inject (R1 miss)', async t => {
  const { entries, prompts } = await boot(t, {
    inject: R1_INJECT,
    hostLikeRemote: false,
    provideRemote: true,
  });
  await generateNative(entries)(SESSION_ID);
  assert.equal(prompts.length, 1);
  assert.equal(prompts[0].mode, 'queue');
});

test('R1 inject fails remote.session under host-like Service registration', async t => {
  const { entries, prompts, saved } = await boot(t, { inject: R1_INJECT, hostLikeRemote: true });
  assert.equal(loadClient().inject.includes('remote'), true);
  await assert.rejects(
    generateNative(entries)(SESSION_ID),
    /cannot get property "remote.session" without inject/,
  );
  assert.equal(prompts.length, 0);
  const library = libraryOf(entries);
  await library.openBoard(saved.spec.board_id);
  const before = structuredClone(library.getSnapshot().saved);
  await library.beginEdit('note');
  assert.match(library.getSnapshot().message, /cannot get property "remote.session" without inject/);
  assert.deepEqual(library.getSnapshot().saved, before);
  assert.equal(library.getSnapshot().editContext.status, 'OPEN');
  assert.equal(prompts.length, 0);
});

test('declared remote and remote.session let generateNative and editNative submit one queued prompt on the same session', async t => {
  const { client, ctx, entries, prompts, saved } = await boot(t);
  assert.ok(client.inject.includes('remote'));
  assert.ok(client.inject.includes('remote.session'));
  assert.equal(client.inject.includes('slots'), true);
  assert.ok(ctx.reflect.props.remote);
  assert.ok(ctx.reflect.props['remote.session']);
  const generate = generateNative(entries);
  await generate(SESSION_ID);
  assert.equal(prompts.length, 1);
  assert.equal(prompts[0].sessionId, SESSION_ID);
  assert.equal(prompts[0].mode, 'queue');
  assert.equal(prompts[0].content[0].type, 'text');
  assert.match(prompts[0].content[0].text, /competition_board_generate/);
  assert.match(prompts[0].content[0].text, /不重复查数/);
  assert.match(prompts[0].content[0].text, /saved_boards/);
  assert.match(prompts[0].content[0].text, /不是草稿/);
  assert.match(prompts[0].content[0].text, /另一份待确认新板/);
  assert.equal(/自动保存|自行保存/.test(prompts[0].content[0].text), false);

  const library = libraryOf(entries);
  assert.ok(library);
  await library.openBoard(saved.spec.board_id);
  assert.equal(library.getSnapshot().message, '');
  assert.ok(library.getSnapshot().saved);
  const before = structuredClone(library.getSnapshot().saved);
  await library.beginEdit('note');
  assert.equal(prompts.length, 2);
  assert.equal(prompts[1].sessionId, SESSION_ID);
  assert.equal(prompts[1].mode, 'queue');
  assert.match(prompts[1].content[0].text, /edit_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/);
  assert.match(prompts[1].content[0].text, /不授权你自行改变内容|不自动保存/);
  assert.deepEqual(library.getSnapshot().saved, before);
  assert.equal(library.getSnapshot().editContext.status, 'OPEN');
});

test('rejected native prompt is visible and does not mutate the saved board or drop the edit context', async t => {
  const { entries, prompts, saved } = await boot(t, { accept: false });
  await assert.rejects(generateNative(entries)(SESSION_ID), /未接受|not accepted/);
  assert.equal(prompts.length, 1);
  const library = libraryOf(entries);
  await library.openBoard(saved.spec.board_id);
  assert.ok(library.getSnapshot().saved, library.getSnapshot().message);
  const before = structuredClone(library.getSnapshot().saved);
  await library.beginEdit('note');
  assert.match(library.getSnapshot().message, /未接受|选中目标保留/);
  assert.deepEqual(library.getSnapshot().saved, before);
  assert.equal(library.getSnapshot().editContext.status, 'OPEN');
  assert.equal(prompts.length, 2);
});

test('dispose and reload do not leave a second generate dock or cross-session prompt', async t => {
  const first = await boot(t);
  assert.equal(first.entries.filter(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit').length, 1);
  await first.fiber.dispose();
  first.disposeSlots();
  assert.equal(first.entries.filter(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit').length, 0);
  const second = await boot(t);
  assert.equal(second.entries.filter(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit').length, 1);
  await generateNative(second.entries)(SESSION_ID);
  assert.deepEqual(second.prompts.map(row => row.sessionId), [SESSION_ID]);
  second.saved.spec.session_id = 'other-session';
  const library = libraryOf(second.entries);
  await library.openBoard(second.saved.spec.board_id);
  assert.ok(library.getSnapshot().saved, library.getSnapshot().message);
  await library.beginEdit('note');
  assert.match(library.getSnapshot().message, /原生会话当前不可用/);
  assert.equal(second.prompts.length, 1);
  assert.deepEqual(library.getSnapshot().saved.spec.session_id, 'other-session');
});
