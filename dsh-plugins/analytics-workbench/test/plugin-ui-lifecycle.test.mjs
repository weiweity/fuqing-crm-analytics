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
    const board = generate.options.inject().board;
    const nativeGenerate = renderToStaticMarkup(React.createElement(generate.component, {
      session: { sessionId: 'native-session-uuid' }, board,
    }));
    assert.equal(nativeGenerate, '');
    const registeredGenerate = renderToStaticMarkup(React.createElement(generate.component, {
      session: { sessionId: 'session-b0-synthetic-primary' }, board,
    }));
    assert.match(registeredGenerate, /生成驾驶舱/);
    assert.equal(board.getSnapshot().boardSpec.board_id, 'board_demo_channel_gsv_2026_08');
    board.actions.proposeGenerate();
    assert.equal(board.getSnapshot().pendingGenerate, null);
    assert.match(board.getSnapshot().boardError, /没有可绑定的核验结果/);
    assert.equal(board.getSnapshot().boardSpec.board_id, 'board_demo_channel_gsv_2026_08');
    const facts = { result_c0: { current_gsv: 410, comparison_gsv: 305, difference: 105 } };
    const spec = {
      board_id: 'board_retail_gsv_result_c0',
      version: 1,
      blocks: [
        { block_id: 'm1', kind: 'METRIC', title: '零售 GSV', metric_ref: 'retail_gsv', source_result_id: 'result_c0' },
      ],
    };
    board.actions.proposeGenerate({ spec, facts });
    assert.ok(board.getSnapshot().pendingGenerate);
    board.actions.confirmGenerate();
    assert.equal(board.getSnapshot().pendingGenerate, null);
    assert.equal(board.getSnapshot().boardSpec.board_id, 'board_retail_gsv_result_c0');
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
    'sidebar.brand.mark', 'sidebar.brand.name', 'conversation.hero.brand.mark', 'sidebar.footer.action', 'shell.overlay',
    'tool.call.toolview', 'tool.call.toolview', 'tool.call.toolview',
    'conversation.input.dock', 'conversation.input.dock',
    'sidebar.panellist', 'main',
    'sidebar.panellist', 'main',
  ]);
  const panels = entries.filter(row => row.options.name === 'sidebar.panellist');
  const mains = entries.filter(row => row.options.name === 'main');
  assert.deepEqual(panels.map(row => row.options.id), ['cockpit', 'staff']);
  assert.deepEqual(mains.map(row => row.options.key), ['cockpit', 'staff']);
  assert.equal(entries.some(row => row.options.name === 'conversation.view'), false);
  assert.equal(entries.find(row => row.options.name === 'sidebar.footer.action').options.inject().openCockpit(), false);
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
  assert.equal(entries.find(row => row.options.name === 'sidebar.footer.action').options.inject().openCockpit(), true);
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
  assert.equal(entries.length, 28);
  assert.equal(entries.filter(row => row.options.id === 'shine-mage.analytics-b0.footer').length, 2);
  assert.equal(entries.filter(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit').length, 2);
});
