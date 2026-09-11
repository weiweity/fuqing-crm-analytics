/** Client slot lifecycle against a fake Cordis surface. Not a native Settings enable/disable run. */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(root, '../../.context/dsh-b0/upstream'));
const webRequire = createRequire(join(upstream, 'apps/web/package.json'));
const stores = await import(pathToFileURL(join(upstream, 'packages/client/store/lib/index.js')).href);
const source = await readFile(join(root, 'lib/client.js'), 'utf8');

test('ordinary native chat has no synthetic run status; registered B0 still has its status', () => {
  const { entries, effects } = mount(loadClient());
  const component = entries.find(row => row.options.name === 'conversation.input.dock').component;
  const React = webRequire('react');
  const { renderToStaticMarkup } = webRequire('react-dom/server');
  try {
    const native = renderToStaticMarkup(React.createElement(component, { session: { sessionId: 'native-session-uuid' } }));
    assert.equal(native, '');
    const registered = renderToStaticMarkup(React.createElement(component, { session: { sessionId: 'session-b0-synthetic-primary' } }));
    assert.match(registered, /B0 任务内核状态/);
    const generate = entries.find(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit');
    const store = generate.options.store.create();
    const nativeGenerate = renderToStaticMarkup(React.createElement(generate.component, {
      session: { sessionId: 'native-session-uuid' }, useStore: selector => selector(store.getSnapshot()), actions: store.actions,
    }));
    assert.equal(nativeGenerate, '');
    const registeredGenerate = renderToStaticMarkup(React.createElement(generate.component, {
      session: { sessionId: 'session-b0-synthetic-primary' }, useStore: selector => selector(store.getSnapshot()), actions: store.actions,
    }));
    assert.match(registeredGenerate, /生成驾驶舱/);
    store.actions.openGenerate();
    assert.equal(store.getSnapshot().open, true);
    assert.equal(store.getSnapshot().intent, 'generate');
  } finally {
    for (const dispose of effects) if (typeof dispose === 'function') dispose();
  }
});

function loadClient() {
  const seed = new Map([
    ['react', webRequire('react')],
    ['react-dom', webRequire('react-dom')],
    ['react/jsx-runtime', webRequire('react/jsx-runtime')],
    ['@deepseek-ai/dsh-client-store', stores],
  ]);
  let factoryRow;
  vm.runInNewContext(source, { window: { localStorage: { getItem: () => null }, __ModuleLoader__: { load: row => { factoryRow = row; } } } }, { timeout: 1000 });
  return factoryRow.factory(spec => {
    assert.ok(seed.has(spec), `unexpected browser require: ${spec}`);
    return seed.get(spec);
  });
}

function mount(client, extra = {}) {
  const entries = [];
  const effects = [];
  client.apply({
    effect: factory => { effects.push(factory()); },
    theme: { overrideTokens: () => () => {} },
    sessions: {
      list: { getSnapshot: () => ({ phase: 'ready', ids: [], byId: {} }), subscribe: () => () => {} },
      open() { assert.fail('lifecycle test opened a session'); },
      clear() {},
      create() { assert.fail('lifecycle test created a session'); },
    },
    slots: {
      inject: (_name, callback) => effects.push(callback()),
      register: (options, component) => {
        entries.push({ options, component });
        return () => {
          const index = entries.findIndex(row => row.options === options);
          if (index >= 0) entries.splice(index, 1);
        };
      },
    },
    ...extra,
  });
  return { entries, effects };
}

test('apply registers business slots; dispose removes them without touching native keys', () => {
  const client = loadClient();
  const { entries, effects } = mount(client);
  assert.deepEqual(entries.map(row => row.options.name), [
    'sidebar.brand.mark', 'sidebar.brand.name', 'sidebar.footer.action', 'shell.overlay',
    'tool.call.toolview', 'tool.call.toolview', 'tool.call.toolview',
    'conversation.input.dock', 'conversation.input.dock',
    'sidebar.panellist', 'main',
  ]);
  const panel = entries.find(row => row.options.name === 'sidebar.panellist');
  const main = entries.find(row => row.options.name === 'main');
  assert.equal(panel.options.id, 'cockpit');
  assert.equal(main.options.key, 'cockpit');
  assert.equal(entries.some(row => row.options.name === 'conversation.view'), false);
  assert.equal(entries[2].options.inject().openCockpit(), false);
  assert.deepEqual(entries.filter(row => row.options.name === 'tool.call.toolview').map(row => row.options.key), [
    'analytics_b0_query', 'analytics_channel_followup_query', 'analytics_first_purchase_query',
  ]);
  for (const dispose of effects) if (typeof dispose === 'function') dispose();
  assert.equal(entries.length, 0);
});

test('footer openCockpit selects sidebar.panellist id cockpit on the main slot', () => {
  const selected = [];
  const { entries, effects } = mount(loadClient(), {
    layout: { selectPanel: id => { selected.push(id); } },
  });
  assert.equal(entries[2].options.inject().openCockpit(), true);
  assert.deepEqual(selected, ['cockpit']);
  assert.equal(entries.find(row => row.options.name === 'sidebar.panellist').options.id,
    entries.find(row => row.options.name === 'main').options.key);
  for (const dispose of effects) if (typeof dispose === 'function') dispose();
});

test('a second apply on the same fake ctx duplicates registrations; Host must not double-insert the plugin', () => {
  const client = loadClient();
  const entries = [];
  const ctx = {
    effect: factory => factory(),
    theme: { overrideTokens: () => () => {} },
    sessions: {
      list: { getSnapshot: () => ({ phase: 'ready', ids: [], byId: {} }), subscribe: () => () => {} },
      open() {}, clear() {}, create() { assert.fail('lifecycle test created a session'); },
    },
    slots: {
      inject: (_name, callback) => callback(),
      register: (options, component) => { entries.push({ options, component }); return () => {}; },
    },
  };
  client.apply(ctx);
  client.apply(ctx);
  assert.equal(entries.length, 22);
  assert.equal(entries.filter(row => row.options.id === 'shine-mage.analytics-b0.footer').length, 2);
  assert.equal(entries.filter(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit').length, 2);
});
