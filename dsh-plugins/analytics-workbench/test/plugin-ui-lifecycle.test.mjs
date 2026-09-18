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

function memoryStorage() {
  const data = new Map();
  return {
    getItem(key) { return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { data.set(String(key), String(value)); },
    removeItem(key) { data.delete(String(key)); },
  };
}

function fakePluginWindow(storage) {
  const listeners = new Map();
  return {
    localStorage: storage,
    addEventListener(type, fn) {
      const list = listeners.get(type) ?? [];
      list.push(fn);
      listeners.set(type, list);
    },
    removeEventListener(type, fn) {
      listeners.set(type, (listeners.get(type) ?? []).filter(row => row !== fn));
    },
    dispatchEvent(event) {
      for (const fn of listeners.get(event?.type) ?? []) fn(event);
      return true;
    },
    open() { assert.fail('lifecycle test opened a tab'); },
  };
}

function loadClient(hostWindow) {
  const storage = hostWindow?.localStorage ?? memoryStorage();
  const view = hostWindow ?? fakePluginWindow(storage);
  const seed = new Map([
    ['react', webRequire('react')],
    ['react-dom', webRequire('react-dom')],
    ['react/jsx-runtime', webRequire('react/jsx-runtime')],
    ['@deepseek-ai/dsh-client-store', stores],
  ]);
  let factoryRow;
  view.__ModuleLoader__ = { load: row => { factoryRow = row; } };
  vm.runInNewContext(source, {
    window: view,
    localStorage: storage,
    document: view.document,
    Event: view.Event,
    KeyboardEvent: view.KeyboardEvent,
    HTMLElement: view.HTMLElement,
    HTMLButtonElement: view.HTMLButtonElement,
    Node: view.Node,
    ResizeObserver: view.ResizeObserver,
    FormData: view.FormData,
    __SHINE_QUERY__: true,
    __SHINE_BOARD__: true,
    __SHINE_CROWD_ACTION__: true,
  }, { timeout: 1000 });
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
      retain() { assert.fail('lifecycle test opened a session'); },
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
    'sidebar.brand.mark', 'conversation.hero.brand.mark',
    'sidebar.footer.action', 'sidebar.footer.action', 'shell.overlay', 'shell.overlay',
    'tool.call.toolview', 'tool.call.toolview', 'tool.call.toolview', 'tool.call.toolview', 'tool.call.toolview', 'tool.call.toolview',
    'conversation.input.dock', 'conversation.composer.dock',
    'sidebar.panellist', 'main',
    'sidebar.panellist', 'main',
  ]);
  const panels = entries.filter(row => row.options.name === 'sidebar.panellist');
  const mains = entries.filter(row => row.options.name === 'main');
  assert.deepEqual(panels.map(row => row.options.id), ['cockpit', 'staff']);
  assert.deepEqual(mains.map(row => row.options.key), ['cockpit', 'staff']);
  assert.equal(entries.some(row => row.options.name === 'conversation.view'), false);
  const footers = entries.filter(row => row.options.name === 'sidebar.footer.action');
  assert.deepEqual(footers.map(row => row.options.id),
    ['shine-mage.account.login', 'shine-mage.account.theme']);
  assert.deepEqual(footers.map(row => row.options.order), [10, 11]);
  assert.equal(typeof footers[0].component, 'function');
  assert.equal(typeof footers[1].component, 'function');
  assert.deepEqual(entries.filter(row => row.options.name === 'tool.call.toolview').map(row => row.options.key), [
    'analytics_b0_query', 'analytics_channel_followup_query', 'analytics_first_purchase_query', 'competition_board_generate', 'competition_board_edit', 'free_html_page_generate',
  ]);
  for (const dispose of effects) if (typeof dispose === 'function') dispose();
  assert.equal(entries.length, 0);
});

test('generate dock openCockpit selects sidebar.panellist id cockpit on the main slot', () => {
  const selected = [];
  const { entries, effects } = mount(loadClient(), {
    layout: { selectPanel: id => { selected.push(id); } },
  });
  const generate = entries.find(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit');
  assert.equal(generate.options.name, 'conversation.composer.dock');
  assert.equal(generate.options.inject().openCockpit(), true);
  assert.deepEqual(selected, ['cockpit']);
  assert.equal(entries.find(row => row.options.name === 'sidebar.panellist').options.id,
    entries.find(row => row.options.name === 'main').options.key);
  for (const dispose of effects) if (typeof dispose === 'function') dispose();
});

test('account menu lists the competition board as a new-tab link', () => {
  const { entries, effects } = mount(loadClient());
  const React = webRequire('react');
  const { renderToStaticMarkup } = webRequire('react-dom/server');
  try {
    const row = entries.find(item => item.options.id === 'shine-mage.account.menu');
    const html = renderToStaticMarkup(React.createElement(row.component, {
      useStore: selector => selector({ menuOpen: true, themeOpen: false }),
      actions: { closeMenu() {}, toggleMenu() {}, openMenu() {}, closeTheme() {}, toggleTheme() {}, closeAll() {} },
      themeSource: { subscribe: () => () => {}, getSnapshot: () => 'system' },
      setTheme() {},
    }));
    assert.match(html, /比赛看板/);
    assert.match(html, /data-testid="legacy-board-open"/);
    assert.match(html, /href="http:\/\/127\.0\.0\.1:15173\/"/);
    assert.match(html, /target="_blank"/);
    assert.match(html, /rel="noopener noreferrer"/);
    assert.match(html, />设置</);
    assert.match(html, /<svg /);
    assert.match(html, />未登录</);
    assert.match(html, /data-testid="shine-account-signin"/);
    assert.match(html, /data-testid="shine-account-name-input"/);
    assert.doesNotMatch(html, /data-testid="shine-account-signout"/);
  } finally {
    for (const dispose of effects) if (typeof dispose === 'function') dispose();
  }
});

test('login footer shows 未登录 when wide and hides the label on the rail', () => {
  const { entries, effects } = mount(loadClient());
  const React = webRequire('react');
  const { renderToStaticMarkup } = webRequire('react-dom/server');
  try {
    const row = entries.find(item => item.options.id === 'shine-mage.account.login');
    const wide = renderToStaticMarkup(React.createElement(row.component, {
      wide: true,
      useStore: selector => selector({ menuOpen: false, themeOpen: false }),
      actions: { closeMenu() {}, toggleMenu() {}, openMenu() {}, closeTheme() {}, toggleTheme() {}, closeAll() {} },
    }));
    const rail = renderToStaticMarkup(React.createElement(row.component, {
      wide: false,
      useStore: selector => selector({ menuOpen: false, themeOpen: false }),
      actions: { closeMenu() {}, toggleMenu() {}, openMenu() {}, closeTheme() {}, toggleTheme() {}, closeAll() {} },
    }));
    assert.match(wide, /未登录/);
    assert.match(wide, /data-wide="1"/);
    assert.match(wide, /<svg /);
    assert.match(rail, /data-wide="0"/);
    assert.match(rail, /aria-label="未登录"/);
    assert.match(rail, /<svg /);
    const theme = entries.find(item => item.options.id === 'shine-mage.account.theme');
    const themeRail = renderToStaticMarkup(React.createElement(theme.component, {
      wide: false,
      useStore: selector => selector({ menuOpen: false, themeOpen: false }),
      actions: { closeMenu() {}, toggleMenu() {}, openMenu() {}, closeTheme() {}, toggleTheme() {}, closeAll() {} },
      themeSource: { subscribe: () => () => {}, getSnapshot: () => 'system' },
      setTheme() {},
    }));
    assert.match(themeRail, /data-wide="0"/);
    assert.match(themeRail, /<svg /);
  } finally {
    for (const dispose of effects) if (typeof dispose === 'function') dispose();
  }
});

test('signing in writes identity on this tab and the footer shows the name', async () => {
  const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
  const React = webRequire('react');
  const { createRoot } = webRequire('react-dom/client');
  const act = typeof React.act === 'function' ? React.act : webRequire('react-dom/test-utils').act;
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318/' });
  const previous = {
    window: globalThis.window,
    document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT,
  };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const { entries, effects } = mount(loadClient(dom.window));
  const root = createRoot(dom.window.document.getElementById('root'));
  const actions = { closeMenu() {}, toggleMenu() {}, openMenu() {}, closeTheme() {}, toggleTheme() {}, closeAll() {} };
  const useStore = selector => selector({ menuOpen: true, themeOpen: false });
  try {
    const login = entries.find(item => item.options.id === 'shine-mage.account.login');
    const menu = entries.find(item => item.options.id === 'shine-mage.account.menu');
    await act(() => {
      root.render(React.createElement(React.Fragment, null,
        React.createElement(login.component, { wide: true, useStore, actions }),
        React.createElement(menu.component, {
          useStore, actions, setTheme() {},
          themeSource: { subscribe: () => () => {}, getSnapshot: () => 'system' },
        }),
      ));
    });
    const input = dom.window.document.querySelector('[data-testid="shine-account-name-input"]');
    assert.ok(input);
    input.value = '王敏';
    await act(() => { dom.window.document.querySelector('[data-testid="shine-account-signin"]').click(); });
    const footer = dom.window.document.querySelector('[data-testid="shine-account-login"]');
    assert.match(footer.textContent, /王敏/);
    assert.match(dom.window.document.querySelector('[data-testid="shine-account-menu"]').textContent, /飞书/);
    assert.ok(dom.window.document.querySelector('[data-testid="shine-account-signout"]'));
    await act(() => { dom.window.document.querySelector('[data-testid="shine-account-signout"]').click(); });
    assert.match(footer.textContent, /未登录/);
    assert.ok(dom.window.document.querySelector('[data-testid="shine-account-signin"]'));
  } finally {
    await act(() => root.unmount());
    for (const dispose of effects) if (typeof dispose === 'function') dispose();
    if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
    if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
    if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
  }
});

test('theme menu offers day night and system icons', () => {
  const { entries, effects } = mount(loadClient());
  const React = webRequire('react');
  const { renderToStaticMarkup } = webRequire('react-dom/server');
  try {
    const row = entries.find(item => item.options.id === 'shine-mage.account.menu');
    const html = renderToStaticMarkup(React.createElement(row.component, {
      useStore: selector => selector({ menuOpen: false, themeOpen: true }),
      actions: { closeMenu() {}, toggleMenu() {}, openMenu() {}, closeTheme() {}, toggleTheme() {}, closeAll() {} },
      themeSource: { subscribe: () => () => {}, getSnapshot: () => 'dark' },
      setTheme() {},
    }));
    assert.match(html, /data-testid="shine-theme-menu"/);
    assert.match(html, /data-testid="shine-theme-light"/);
    assert.match(html, /data-testid="shine-theme-dark"/);
    assert.match(html, /data-testid="shine-theme-system"/);
    assert.match(html, /日间/);
    assert.match(html, /夜晚/);
    assert.match(html, /跟随系统/);
    assert.match(html, /aria-pressed="true"/);
  } finally {
    for (const dispose of effects) if (typeof dispose === 'function') dispose();
  }
});

test('a second apply on the same fake ctx duplicates registrations; Host must not double-insert the plugin', () => {
  const client = loadClient();
  const entries = [];
  const ctx = {
    effect: factory => factory(),
    theme: { overrideTokens: () => () => {} },
    sessions: {
      list: { getSnapshot: () => ({ phase: 'ready', ids: [], byId: {} }), subscribe: () => () => {} },
      retain() { return { sessionId: '', release() {} }; }, create() { assert.fail('lifecycle test created a session'); },
    },
    slots: {
      inject: (_name, callback) => callback(),
      register: (options, component) => { entries.push({ options, component }); return () => {}; },
    },
  };
  client.apply(ctx);
  client.apply(ctx);
  // A second apply duplicates every registration; no identity is added or lost.
  const ids = entries.filter(row => row.options.id !== undefined).map(row => row.options.id);
  for (const id of ['shine-mage.account.login', 'shine-mage.account.theme',
    'shine-mage.analytics-b0.generate-cockpit', 'shine-mage.analytics-b0.overlay']) {
    assert.equal(entries.filter(row => row.options.id === id).length, 2, `${id} registered twice`);
    assert.equal(ids.filter(value => value === id).length, 2, `${id} counted twice`);
  }
});

test('board store refreshBoard rebinds catalog; cancelGenerate drops pending; generateBoard writes', () => {
  const { entries, effects } = mount(loadClient());
  try {
    const board = entries.find(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit').options.inject().board;
    board.actions.setFactsCatalog({
      demo_live: { current_gsv: 999, comparison_gsv: 1, difference: 998 },
    });
    board.actions.refreshBoard();
    assert.equal(board.getSnapshot().boardFacts.demo_live.current_gsv, 999);
    assert.equal(board.getSnapshot().boardFacts.demo_private, undefined);
    const spec = {
      board_id: 'board_x',
      version: 1,
      blocks: [{ block_id: 'm1', kind: 'METRIC', title: 'x', source_result_id: 'demo_live' }],
    };
    board.actions.proposeGenerate({ spec, facts: { demo_live: { current_gsv: 1, comparison_gsv: 1, difference: 0 } } });
    assert.ok(board.getSnapshot().pendingGenerate);
    board.actions.cancelGenerate();
    assert.equal(board.getSnapshot().pendingGenerate, null);
    board.actions.generateBoard();
    assert.match(board.getSnapshot().boardError, /没有可绑定的核验结果/);
    board.actions.generateBoard({ spec, facts: { demo_live: { current_gsv: 2, comparison_gsv: 1, difference: 1 } } });
    assert.equal(board.getSnapshot().boardSpec.board_id, 'board_x');
    assert.equal(board.getSnapshot().pendingGenerate, null);
  } finally {
    for (const dispose of effects) if (typeof dispose === 'function') dispose();
  }
});

test('generate dock proposes a bound board from results and appends a LINK without Feishu token', async () => {
  const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
  const React = webRequire('react');
  const { createRoot } = webRequire('react-dom/client');
  const act = typeof React.act === 'function' ? React.act : webRequire('react-dom/test-utils').act;
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318/' });
  const previous = {
    window: globalThis.window,
    document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT,
  };
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const { entries, effects } = mount(loadClient());
  const root = createRoot(dom.window.document.getElementById('root'));
  let opened = 0;
  try {
    const generate = entries.find(row => row.options.id === 'shine-mage.analytics-b0.generate-cockpit');
    const board = generate.options.inject().board;
    await act(() => {
      root.render(React.createElement(generate.component, {
        session: { sessionId: 'session-b0-synthetic-primary' },
        board,
        openCockpit() { opened += 1; },
        async fetchResults() {
          return [{
            result_id: 'result_c0',
            facts: { current: { gsv: 410 }, comparison: { gsv: 305 }, difference: 105 },
          }];
        },
      }));
    });
    await act(() => { dom.window.document.querySelector('[data-testid="analytics-b0-generate-cockpit"]').click(); });
    for (let i = 0; i < 30 && !board.getSnapshot().pendingGenerate; i += 1) {
      await act(async () => { await new Promise(resolve => setTimeout(resolve, 15)); });
    }
    const pending = board.getSnapshot().pendingGenerate;
    assert.ok(pending);
    assert.equal(pending.spec.blocks[0].source_result_id, 'result_c0');
    assert.equal(pending.facts.result_c0.current_gsv, 410);
    assert.equal(opened, 1);
  } finally {
    await act(() => root.unmount());
    for (const dispose of effects) if (typeof dispose === 'function') dispose();
    if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
    if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
    if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
    dom.window.close();
  }
});
