import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve, join } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? resolve(root, '../../.context/dsh-b0/upstream'));

test('built Host root requires isolated capabilities; tool fails closed without native context', async () => {
  const ui = await import(pathToFileURL(join(root, 'lib/index.js')).href);
  assert.throws(() => ui.apply({}), /explicit isolated capabilities/);
  assert.deepEqual(ui.inject, ['agents', 'sessions', 'sessionController']);
  const host = await import(pathToFileURL(join(root, 'lib/tool.js')).href);
  const registered = [];
  host.apply({ tools: { register: tool => { registered.push(tool); } } });
  assert.equal(registered.length, 1);
  const [tool] = registered;
  assert.equal(tool.name, 'analytics_b0_query');
  const args = { query: 'channel_repeat_rate' };
  await assert.rejects(tool.execute(args, { signal: new AbortController().signal }), /no bound execution context/);
  await assert.rejects(tool.execute({ query: 'sql' }, { signal: new AbortController().signal }));
});

test('built browser factory requires only platform modules and registers shared-root entries', async () => {
  const webRequire = createRequire(join(upstream, 'apps/web/package.json'));
  const stores = await import(pathToFileURL(join(upstream, 'packages/client/store/lib/index.js')).href);
  const seed = new Map([
    ['react', webRequire('react')],
    ['react/jsx-runtime', webRequire('react/jsx-runtime')],
    ['@deepseek-ai/dsh-client-store', stores],
  ]);
  let factoryRow;
  const browser = {
    localStorage: { getItem: () => null },
    __ModuleLoader__: { load: row => { factoryRow = row; } },
  };
  const code = await readFile(join(root, 'lib/client.js'), 'utf8');
  vm.runInNewContext(code, { window: browser }, { filename: 'analytics-b0-client.js', timeout: 1000 });
  assert.equal(factoryRow.id, '@shine-mage/dsh-analytics-workbench-b0');
  const client = factoryRow.factory(spec => {
    assert.ok(seed.has(spec), `unexpected browser require: ${spec}`);
    return seed.get(spec);
  });
  const entries = [];
  const effects = [], opened = [];
  const primary = 'session-b0-synthetic-primary';
  let snapshot = { phase: 'pending', ids: [primary], byId: { [primary]: { id: primary } } };
  let notify;
  client.apply({
    effect: factory => { effects.push(factory()); },
    sessions: {
      list: { getSnapshot: () => snapshot, subscribe: listener => { notify = listener; return () => { notify = undefined; }; } },
      open: id => { opened.push(id); snapshot = { ...snapshot, current: id }; },
      clear: () => { snapshot = { ...snapshot, current: undefined }; },
      create: () => assert.fail('compiled client attempted session/create'),
    },
    slots: {
    inject: (_name, callback) => callback(),
    register: (options, component) => { entries.push({ options, component }); return () => {}; },
  } });
  assert.deepEqual(opened, []);
  snapshot = { ...snapshot, phase: 'ready' };
  notify();
  notify();
  assert.deepEqual(opened, [primary]);
  assert.equal(entries.length, 7);
  assert.deepEqual(entries.map(row => row.options.name), ['sidebar.brand.mark', 'sidebar.brand.name',
    'sidebar.footer.action', 'shell.overlay', 'tool.call.toolview', 'tool.call.toolview', 'conversation.input.dock']);
  assert.equal(entries[4].options.key, 'analytics_b0_query');
  assert.equal(entries[5].options.key, 'analytics_channel_followup_query');
  assert.equal(entries[0].options.priority, -10);
  assert.equal(entries[1].options.priority, -10);
  const selection = entries[3].options.inject();
  selection.detachSelection();
  assert.equal(snapshot.current, undefined);
  selection.restoreSelection();
  assert.equal(snapshot.current, primary);
  assert.equal(entries[2].options.store, entries[3].options.store);
  const state = entries[2].options.store.create();
  assert.equal(state.getSnapshot().open, false);
  state.actions.open();
  assert.equal(state.getSnapshot().open, true);
  state.actions.edit('编译产物标题');
  state.actions.preview();
  state.actions.requestClose();
  assert.equal(state.getSnapshot().confirmClose, true);
  assert.equal(state.getSnapshot().open, true);
  state.actions.keepEditing();
  assert.equal(state.getSnapshot().confirmClose, false);
  state.actions.commit('仅 UI 测试');
  assert.equal(state.getSnapshot().editor.title, '编译产物标题');
  state.actions.close();
  assert.equal(state.getSnapshot().open, false);
  state.actions.open();
  state.actions.edit('不应保存');
  state.actions.discardAndClose();
  assert.equal(state.getSnapshot().editor.draft, '编译产物标题');
  assert.equal(state.getSnapshot().open, false);
  for (const dispose of effects) dispose();
  assert.equal(notify, undefined);
});
