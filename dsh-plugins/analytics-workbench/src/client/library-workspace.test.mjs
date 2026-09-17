/** Compiled React interactions; not a real-browser or visual acceptance claim. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join, resolve } from 'node:path';
import { createLibraryBoardClient } from './library-board-client.mjs';
import { COMPONENT_CATALOG } from '../board-spec/component-catalog.mjs';
import { librarySnapshot, libraryPreview, ok, failed, listOf } from '../../test/helpers/library-board-fixtures.mjs';

const plugin = fileURLToPath(new URL('../..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const web = createRequire(join(upstream, 'apps/web/package.json'));
const React = web('react'), { createRoot } = web('react-dom/client');
const act = React.act ?? web('react-dom/test-utils').act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');
const outfile = join(plugin, 'lib/test-library-workspace.mjs');
await createRequire(web.resolve('vite/package.json'))('esbuild').build({
  absWorkingDir: plugin, entryPoints: ['src/client/library-workspace.tsx'], outfile, bundle: true,
  format: 'esm', platform: 'browser', target: 'es2022', jsx: 'automatic',
  external: ['react', 'react/jsx-runtime', 'react-dom'], logLevel: 'silent',
});
const { LibraryCockpitPanel, LibraryGenerateDock, LibraryPreviewToolCard } = await import(pathToFileURL(outfile).href);

async function domFixture(t) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318', pretendToBeVisual: true });
  const globals = ['window', 'document', 'HTMLElement', 'Element', 'SVGElement', 'ShadowRoot', 'getComputedStyle', 'IS_REACT_ACT_ENVIRONMENT'];
  const before = globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
  for (const key of globals) Object.defineProperty(globalThis, key, { configurable: true, writable: true,
    value: key === 'IS_REACT_ACT_ENVIRONMENT' ? true : key === 'getComputedStyle' ? dom.window.getComputedStyle.bind(dom.window) : dom.window[key] });
  const root = createRoot(dom.window.document.querySelector('#root'));
  const captures = new WeakMap();
  dom.window.HTMLElement.prototype.setPointerCapture = function (id) { captures.set(this, id); };
  dom.window.HTMLElement.prototype.hasPointerCapture = function (id) { return captures.get(this) === id; };
  dom.window.HTMLElement.prototype.releasePointerCapture = function () { captures.delete(this); };
  t.after(async () => { await act(async () => root.unmount()); dom.window.close();
    for (const [key, descriptor] of before) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key]; } });
  return { root, doc: dom.window.document, render: element => act(async () => root.render(element)),
    key: (selector, key, shiftKey = false) => act(async () => {
      const target = selector ? dom.window.document.querySelector(selector) : dom.window;
      target.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true }));
    }),
    pointer: (selector, type, x, y, extra = {}) => act(async () => {
      const target = selector ? dom.window.document.querySelector(selector) : dom.window;
      const event = new dom.window.MouseEvent(type, { clientX: x, clientY: y, button: 0, buttons: type === 'pointerup' ? 0 : 1, bubbles: true, cancelable: true });
      Object.defineProperties(event, { pointerId: { value: 1 }, pointerType: { value: 'mouse' }, ...Object.fromEntries(Object.entries(extra).map(([key, value]) => [key, { value }])) });
      target.dispatchEvent(event);
    }),
    click: selector => act(async () => { const button = dom.window.document.querySelector(selector); assert.ok(button, selector); button.click(); }) };
}

function allSix() {
  const snapshot = librarySnapshot();
  snapshot.spec.blocks = COMPONENT_CATALOG.components.slice(0, 6).map((component, index) => ({
    block_id: component.kind, kind: component.kind, title: component.name, library_version: COMPONENT_CATALOG.library_version,
    props: component.kind === 'TEXT' ? { content: '待确认的说明' } : {}, source_result_id: 'result_synthetic',
    layout: { x: 0, y: index * 10, ...component.default_size },
  }));
  snapshot.facts_by_result_id.result_synthetic = {
    schema_version: 'board-component-facts/v1', scalar: { value: 42, comparison: 40, unit: '个' },
    series: { ordered: true, unit: '个', points: [{ label: '一月', value: 40 }, { label: '二月', value: 42 }] },
    table: { columns: [{ key: 'count', label: '数量' }], rows: [{ count: 42 }] },
    evidence: { source_label: '合成来源', items: [{ label: '出处', value: '隔离验证' }] },
  };
  return snapshot;
}

test('six-component preview mounts from receipt, keyboard focus lands on heading, cancel and failed save preserve state', async t => {
  const ui = await domFixture(t), snapshot = allSix(), pending = libraryPreview(snapshot);
  let allowSave = false, cancelled = false;
  const client = createLibraryBoardClient(async (_channel, operation) => {
    if (operation === 'list') return ok(listOf(snapshot));
    if (operation === 'get') return ok(snapshot);
    if (operation === 'preview') return ok(pending);
    if (operation === 'confirm') return allowSave ? ok(snapshot) : failed();
    if (operation === 'cancel') { cancelled = true; return ok({ status: 'CANCELLED', preview_id: pending.preview_id }); }
    throw new Error(`unexpected ${operation}`);
  }); t.after(() => client.dispose());
  const theme = { subscribe: () => () => {}, getSnapshot: () => 'light' };
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client, themeSource: theme, goConversation() {} }));
  await act(async () => client.openPreview(pending.preview_id));
  assert.equal(ui.doc.querySelectorAll('[data-block-id]').length, 6);
  assert.equal(ui.doc.activeElement.tagName, 'H1');
  assert.equal(ui.doc.querySelectorAll('textarea').length, 0, 'native composer is not duplicated');
  assert.match(ui.doc.body.textContent, /尚未保存/);
  await ui.click('[data-testid="library-confirm"]');
  assert.equal(client.getSnapshot().saved, null); assert.ok(ui.doc.querySelector('[data-testid="library-preview-banner"]'));
  assert.match(ui.doc.querySelector('[role="status"]').textContent, /隔离故障/);
  assert.match(ui.doc.querySelector('[data-testid="library-preview-banner"]').textContent, /保存结果待核对/);
  assert.doesNotMatch(ui.doc.querySelector('[data-testid="library-preview-banner"]').textContent, /尚未保存|保留已保存版本/);
  assert.ok(ui.doc.querySelector('[data-testid="library-inspect-confirmation"]'));
  allowSave = true; await ui.click('[data-testid="library-confirm"]');
  assert.equal(ui.doc.querySelector('[data-testid="library-preview-banner"]'), null);
  assert.deepEqual(client.getSnapshot().saved, snapshot);
  await act(async () => client.openPreview(pending.preview_id));
  await ui.click('[data-testid="library-cancel"]');
  assert.equal(cancelled, true); assert.deepEqual(client.getSnapshot().saved, snapshot);
});

test('unknown save exposes a read-only recovery action and never labels a committed draft unsaved', async t => {
  const ui = await domFixture(t), saved = librarySnapshot(), pending = libraryPreview(librarySnapshot({ version: 2 }));
  let committed = false, writes = 0;
  const client = createLibraryBoardClient(async (_channel, operation) => {
    if (operation === 'list') return ok(listOf(committed ? pending.snapshot : saved));
    if (operation === 'get') return ok(committed ? pending.snapshot : saved);
    if (operation === 'preview') return ok({ ...pending, status: committed ? 'APPLIED' : 'PENDING' });
    if (operation === 'confirm') { writes++; committed = true; return failed(); }
    throw new Error(`unexpected ${operation}`);
  }); t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => { await client.openBoard(saved.spec.board_id); await client.openPreview(pending.preview_id); });
  await ui.click('[data-testid="library-confirm"]');
  assert.match(ui.doc.querySelector('[data-testid="library-preview-banner"]').textContent, /保存结果待核对/);
  await ui.click('[data-testid="library-inspect-confirmation"]');
  assert.equal(writes, 1); assert.equal(client.getSnapshot().saved.spec.version, 2);
  assert.equal(ui.doc.querySelector('[data-testid="library-preview-banner"]'), null);
  assert.match(ui.doc.body.textContent, /已核对.*保存/);
});

for (const [operation, action] of [['confirm', 'library-confirm'], ['preview', 'library-inspect-confirmation'], ['cancel', 'library-cancel']]) {
  test(`unknown save restores keyboard recovery focus after ${operation} settles`, async t => {
    const ui = await domFixture(t), pending = libraryPreview(librarySnapshot({ version: 2 }));
    let defer = false, settle;
    const client = createLibraryBoardClient(async (_channel, method) => {
      if (defer && method === operation) return new Promise(resolve => { settle = resolve; });
      if (method === 'list') return ok({ items: [] });
      if (method === 'preview') return ok(pending);
      if (method === 'confirm') return failed();
      throw new Error(`unexpected ${method}`);
    }); t.after(() => client.dispose());
    await client.openPreview(pending.preview_id);
    if (operation !== 'confirm') await client.confirm();
    await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
      themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
    const button = ui.doc.querySelector(`[data-testid="${action}"]`);
    button.focus(); defer = true; await ui.click(`[data-testid="${action}"]`);
    assert.equal(button.disabled, true);
    // Chromium blurs a focused button when it is disabled; JSDOM does not.
    ui.doc.body.tabIndex = -1; ui.doc.body.focus(); ui.doc.body.removeAttribute('tabindex');
    assert.equal(ui.doc.activeElement.tagName, 'BODY');
    await act(async () => settle(operation === 'preview' ? ok(pending) : failed()));
    assert.equal(ui.doc.activeElement.getAttribute('data-testid'), 'library-inspect-confirmation');
    assert.equal(client.getSnapshot().confirmationUncertain, true);
    assert.equal(ui.doc.activeElement.disabled, false);
  });
}

test('late unknown-save response does not steal focus from the native conversation', async t => {
  const ui = await domFixture(t), pending = libraryPreview(librarySnapshot({ version: 2 }));
  let settle;
  const client = createLibraryBoardClient(async (_channel, method) => {
    if (method === 'list') return ok({ items: [] });
    if (method === 'preview') return ok(pending);
    if (method === 'confirm') return new Promise(resolve => { settle = resolve; });
    throw new Error(`unexpected ${method}`);
  }); t.after(() => client.dispose());
  await client.openPreview(pending.preview_id);
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await ui.click('[data-testid="library-confirm"]');
  const conversation = ui.doc.createElement('textarea'); ui.doc.body.append(conversation); conversation.focus();
  await act(async () => settle(failed()));
  assert.equal(ui.doc.activeElement === conversation, true);
});

for (const succeeds of [false, true]) {
  test(`refresh restores its keyboard trigger after ${succeeds ? 'success' : 'failure'}`, async t => {
    const ui = await domFixture(t), snapshot = librarySnapshot();
    let defer = false, settle;
    const client = createLibraryBoardClient(async (_channel, method) => {
      if (method === 'list') return defer ? new Promise(resolve => { settle = resolve; }) : ok(listOf(snapshot));
      if (method === 'get') return ok(snapshot);
      throw new Error(`unexpected ${method}`);
    }); t.after(() => client.dispose());
    await client.openBoard(snapshot.spec.board_id);
    await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
      themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
    const button = [...ui.doc.querySelectorAll('button')].find(button => button.textContent === '刷新已保存看板');
    button.focus(); defer = true; await act(async () => button.click());
    assert.equal(button.disabled, true);
    ui.doc.body.tabIndex = -1; ui.doc.body.focus(); ui.doc.body.removeAttribute('tabindex');
    await act(async () => settle(succeeds ? ok(listOf(snapshot)) : failed()));
    assert.equal(ui.doc.activeElement === button, true);
    assert.deepEqual(client.getSnapshot().saved, snapshot);
  });
}

test('keyboard layout entry moves focus off the removed action to the board heading', async t => {
  const ui = await domFixture(t), snapshot = librarySnapshot();
  const client = createLibraryBoardClient(async (_channel, method) => method === 'list' ? ok(listOf(snapshot)) : ok(snapshot));
  t.after(() => client.dispose()); await client.openBoard(snapshot.spec.board_id);
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  ui.doc.querySelector('[data-testid="layout-start"]').focus(); await ui.click('[data-testid="layout-start"]');
  assert.equal(ui.doc.activeElement.tagName, 'H1');
});

test('native generation button binds the clicked session and ignores a late reply after switching sessions', async t => {
  const ui = await domFixture(t); let resolveFirst;
  const sessions = [];
  const generate = session => { sessions.push(session); return new Promise(resolve => { resolveFirst = resolve; }); };
  await ui.render(React.createElement(LibraryGenerateDock, { sessionId: 'first', generate }));
  await ui.click('button'); assert.equal(ui.doc.querySelector('button').disabled, true);
  await ui.render(React.createElement(LibraryGenerateDock, { sessionId: 'second', generate }));
  assert.equal(ui.doc.querySelector('button').disabled, false);
  await act(async () => resolveFirst());
  assert.equal(ui.doc.querySelector('[role="status"]').textContent, ''); assert.deepEqual(sessions, ['first']);
});

test('daily LINE renders all points without hundreds of legend chips and exposes paged keyboard-accessible values', async t => {
  const ui = await domFixture(t), saved = allSix();
  const source = saved.facts_by_result_id.result_synthetic;
  source.time_series = { ordered: true, unit: null, points: Array.from({ length: 366 }, (_, i) => ({ label: `day-${i + 1}`, value: i === 20 ? null : i })) };
  source.series.ordered = false;
  const client = createLibraryBoardClient(async (_channel, operation) => operation === 'list' ? ok(listOf(saved)) : ok(saved));
  t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(saved.spec.board_id));
  const line = ui.doc.querySelector('[data-block-id=LINE]');
  assert.equal(line.querySelectorAll('circle').length, 365);
  assert.equal(line.querySelectorAll('.sm-library-legend span').length, 2);
  assert.match(line.querySelector('summary').textContent, /366 条/);
  assert.equal(line.querySelectorAll('tbody tr').length, 10);
  assert.equal((line.querySelector('path').getAttribute('d').match(/M/g) ?? []).length, 2, 'missing daily value breaks the line');
  await act(async () => { line.querySelector('summary').click(); });
  assert.equal(line.querySelector('details').open, true);
  await act(async () => { [...line.querySelectorAll('button')].find(button => button.textContent === '下一页').click(); });
  assert.match(line.querySelector('tbody').textContent, /day-11/);
});

test('native tool card offers inspection only and never calls confirm', async t => {
  const ui = await domFixture(t); const calls = [];
  await ui.render(React.createElement(LibraryPreviewToolCard, {
    block: { kind: 'tool-result', meta: { schema_version: 'board-tool-result/v1', status: 'PREVIEW_READY', published: false,
      preview_id: 'preview_test', title: '新看板', component_count: 6 } },
    library: { openPreview: async id => calls.push(id), confirm: () => { throw new Error('model must not confirm'); } },
    openCockpit: () => { calls.push('open-cockpit'); return true; },
  }));
  await ui.click('button'); assert.deepEqual(calls, ['preview_test', 'open-cockpit']);
});

function withPlanning(saved = allSix()) {
  for (const kind of ['PROCESS', 'TIMELINE']) {
    const component = COMPONENT_CATALOG.components.find(component => component.kind === kind);
    saved.spec.blocks.push({ block_id: kind, kind, title: component.name, library_version: COMPONENT_CATALOG.library_version,
      props: kind === 'PROCESS' ? { nodes: [{ id: 'a', label: '核对' }, { id: 'b', label: '确认' }], edges: [{ from: 'a', to: 'b' }] }
        : { events: [{ id: 'a', date: '2026-09-13', label: '讨论' }] },
      layout: { x: 0, y: saved.spec.blocks.length * 10, ...component.default_size } });
  }
  return saved;
}

function withWaterfall(saved = allSix()) {
  const component = COMPONENT_CATALOG.components.find(component => component.kind === 'WATERFALL');
  saved.spec.blocks.push({ block_id: 'WATERFALL', kind: 'WATERFALL', title: component.name,
    library_version: COMPONENT_CATALOG.library_version, source_result_id: 'result_synthetic', props: {},
    layout: { x: 0, y: saved.spec.blocks.length * 10, ...component.default_size } });
  saved.facts_by_result_id.result_synthetic.waterfall = { unit: '个', start: { label: '起点', value: -10 },
    end: { label: '终点', value: 20 }, contributions: [{ label: '增加', value: 40 }, { label: '减少', value: -10 }, { label: '不变', value: 0 }] };
  return saved;
}

test('waterfall draws negative anchors, signed contributions, zero marks and conserved connectors as native elements', async t => {
  const ui = await domFixture(t), saved = withWaterfall();
  const client = createLibraryBoardClient(async (_channel, operation) => operation === 'list' ? ok(listOf(saved))
    : operation === 'get' ? ok(saved) : failed());
  t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(saved.spec.board_id));
  const component = ui.doc.querySelector('[data-block-id=WATERFALL]');
  const bars = [...component.querySelectorAll('g[data-role]')];
  assert.equal(bars.length, 5);
  assert.deepEqual(bars.map(bar => Number(bar.dataset.value)), [-10, 40, -10, 0, 20]);
  assert.deepEqual(bars.map(bar => Number(bar.dataset.from)), [0, -10, 30, 20, 0]);
  assert.deepEqual([...component.querySelectorAll('[data-carry]')].map(line => Number(line.dataset.carry)), [-10, 30, 20, 20]);
  const zero = component.querySelector('[data-zero]');
  assert.equal(zero.tagName, 'line');
  assert.equal(bars[2].querySelector('rect').getAttribute('fill'), 'var(--sm-bg)', 'decrease not hue-only');
  assert.equal(component.querySelectorAll('[data-value-label]').length, 5);
  assert.equal(component.querySelectorAll('tbody tr').length, 5);
  assert.match(component.querySelector('tbody').textContent, /增加.*\+40/);
  assert.equal(component.querySelector('.sm-library-waterfall-scroll').tabIndex, 0);
  assert.equal(component.querySelectorAll('img,iframe,script').length, 0);
});

function withFunnel(saved = allSix(), counts = [10, 5, 0], props = {}) {
  const component = COMPONENT_CATALOG.components.find(component => component.kind === 'FUNNEL');
  saved.spec.blocks.push({ block_id: 'FUNNEL', kind: 'FUNNEL', title: component.name,
    library_version: COMPONENT_CATALOG.library_version, source_result_id: 'result_synthetic', props,
    layout: { x: 0, y: saved.spec.blocks.length * 10, ...component.default_size } });
  saved.facts_by_result_id.result_synthetic.funnel = { unit: '人', cohort_label: '本期购买客户', counting_rule: '合成同一人群的购买频次，不是访客转化',
    stages: counts.map((count, index) => ({ label: `至少 ${index + 1} 笔有效订单`, count })) };
  return saved;
}

for (const [name, counts, props, expectedRates] of [
  ['previous', [10, 5, 0], {}, ['首阶段无上一阶段', '50%', '0%']],
  ['first', [10, 5, 0], { rate_basis: 'first' }, ['100%', '50%', '0%']],
  ['empty', [0, 0, 0], {}, ['首阶段无上一阶段', '无可用分母', '无可用分母']],
  ['hidden', [10, 5, 0], { show_values: false, show_rates: false }, []],
]) test(`funnel ${name} renders proportional native bars, explicit rate basis and complete accessible data`, async t => {
  const ui = await domFixture(t), saved = withFunnel(allSix(), counts, props);
  const client = createLibraryBoardClient(async (_channel, operation) => operation === 'list' ? ok(listOf(saved))
    : operation === 'get' ? ok(saved) : failed());
  t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(saved.spec.board_id));
  const component = ui.doc.querySelector('[data-block-id=FUNNEL]');
  assert.deepEqual([...component.querySelectorAll('[data-funnel-width]')].map(bar => Number(bar.dataset.funnelWidth)),
    counts[0] ? [100, 50, 0] : [0, 0, 0]);
  const rates = [...component.querySelectorAll('[data-funnel-rate]')];
  assert.equal(rates.length, expectedRates.length);
  expectedRates.forEach((rate, index) => assert.ok(rates[index].textContent.includes(rate)));
  assert.equal(component.querySelectorAll('[data-funnel-count]').length, props.show_values === false ? 0 : 3);
  assert.equal(component.querySelectorAll('tbody tr').length, 3, 'hiding labels cannot remove source data access');
  assert.equal(component.querySelectorAll('img,iframe,script').length, 0);
  if (name === 'empty') assert.ok(!rates.some(rate => rate.textContent.includes('0%')));
});

test('all registered components offer scoped native editing with before/after and cancel, without a second composer', async t => {
  const ui = await domFixture(t), saved = allSix(), native = [];
  withPlanning(saved);
  withWaterfall(saved);
  withFunnel(saved);
  let edit = null, pending = null;
  const changes = { METRIC: { value_format: 'compact' }, LINE: { line_style: 'dashed' },
    BAR: { orientation: 'vertical' }, TABLE: { page_size: 5 }, TEXT: { content: '改后的说明' }, EVIDENCE: { expanded: true },
    PROCESS: { nodes: [{ id: 'a', label: '核对口径' }, { id: 'b', label: '确认' }] },
    TIMELINE: { events: [{ id: 'a', date: '2026-09-14', label: '调整讨论日期' }] },
    WATERFALL: { show_values: false, show_table: false }, FUNNEL: { show_values: false, rate_basis: 'first' } };
  const client = createLibraryBoardClient(async (_channel, operation, payload) => {
    if (operation === 'list') return ok(listOf(saved));
    if (operation === 'get') return ok(saved);
    if (operation === 'current_edit') return ok(edit);
    if (operation === 'select_edit') {
      edit = { schema_version: 'board-edit-context/v1', edit_context_id: 'edit_' + 'a'.repeat(32), board_id: saved.spec.board_id,
        base_version: 1, block_id: payload.block_id, session_id: saved.spec.session_id, status: 'OPEN', preview_id: null,
        expires_at_ms: Date.now() + 10000, block: saved.spec.blocks.find(block => block.block_id === payload.block_id),
        facts_by_result_id: saved.facts_by_result_id };
      return ok(edit);
    }
    if (operation === 'preview') return ok(pending);
    if (operation === 'cancel_edit') { edit = null; return ok({ status: 'CANCELLED', edit_context_id: payload.edit_context_id }); }
    throw new Error(operation);
  }, { editNative: async context => native.push(context) }); t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(saved.spec.board_id));
  for (const [kind, props] of Object.entries(changes)) {
    await ui.click(`[data-block-id=${kind}] button`);
    assert.equal(native.at(-1).block_id, kind);
    assert.match(ui.doc.querySelector('[data-testid=library-edit-banner]').textContent, /原生对话/);
    const next = structuredClone(saved); next.spec.version = 2;
    next.spec.blocks.find(block => block.block_id === kind).props = { ...edit.block.props, ...props };
    pending = libraryPreview(next); edit = { ...edit, status: 'PROPOSED', preview_id: pending.preview_id };
    await act(async () => client.openPreview(pending.preview_id, edit.edit_context_id));
    assert.match(ui.doc.querySelector('[data-testid=library-edit-diff]').textContent, /修改前.*修改后/);
    for (const key of Object.keys(props)) assert.match(ui.doc.querySelector('[data-testid=library-edit-diff]').textContent, new RegExp(key));
    assert.equal(ui.doc.querySelectorAll('textarea,input,[contenteditable=true]').length, 0);
    await ui.click('[data-testid=library-cancel]');
    assert.deepEqual(client.getSnapshot().saved, saved); assert.equal(client.getSnapshot().editContext, null);
  }
  assert.equal(native.length, COMPONENT_CATALOG.components.length);
});

test('planning diagrams render structured content, date proportions and isolated keyboard targets, never HTML', async t => {
  const ui = await domFixture(t), saved = withPlanning(librarySnapshot());
  const process = saved.spec.blocks.find(block => block.kind === 'PROCESS');
  process.props.nodes[1].label = '<img src=x onerror=run()>确认';
  const duplicate = structuredClone(process); duplicate.block_id = 'PROCESS_COPY'; duplicate.layout.y = 80;
  saved.spec.blocks.push(duplicate);
  const timeline = saved.spec.blocks.find(block => block.kind === 'TIMELINE');
  timeline.props.events = [
    { id: 'end', date: '2026-01-11', label: '结束' },
    { id: 'start', date: '2026-01-01', label: '开始' },
    { id: 'second', date: '2026-01-02', label: '第二天', detail: '<script>run()</script>' },
    { id: 'same', date: '2026-01-02', label: '同日审阅' },
  ];
  const client = createLibraryBoardClient(async (_channel, operation) => operation === 'list' ? ok(listOf(saved)) : ok(saved));
  t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(saved.spec.board_id));
  const flow = ui.doc.querySelector('[data-block-id=PROCESS]');
  const other = ui.doc.querySelector('[data-block-id=PROCESS_COPY]');
  assert.equal(flow.querySelectorAll('[data-process-node]').length, 2);
  assert.equal(flow.querySelectorAll('[data-process-edge]').length, 1);
  assert.equal(flow.querySelectorAll('.sm-process-map [role=button]').length, 2);
  assert.match(flow.textContent, /非已核验 SOP/);
  assert.match(flow.textContent, /<img src=x onerror=run\(\)>确认/);
  assert.equal(ui.doc.querySelector('img,script,iframe'), null);
  const link = flow.querySelector('.sm-process-edges button');
  const target = ui.doc.getElementById(link.getAttribute('aria-controls'));
  const scrolls = [];
  target.scrollIntoView = options => scrolls.push(options);
  await act(async () => link.click());
  assert.equal(ui.doc.activeElement, target);
  assert.equal(flow.contains(target), true); assert.equal(other.contains(target), false);
  assert.equal(scrolls.length, 1);
  const graphicNode = flow.querySelectorAll('.sm-process-map [role=button]')[1];
  await act(async () => graphicNode.dispatchEvent(new ui.doc.defaultView.KeyboardEvent('keydown', { key: 'Enter', bubbles: true })));
  assert.equal(ui.doc.activeElement, target); assert.equal(scrolls.length, 2);
  const time = ui.doc.querySelector('[data-block-id=TIMELINE]');
  const markers = [...time.querySelectorAll('[data-timeline-date]')];
  assert.deepEqual(markers.map(node => Number(node.dataset.position)), [0, .1, 1]);
  const xs = markers.map(node => Number(node.querySelector('circle').getAttribute('cx')));
  assert.ok(Math.abs((xs[1] - xs[0]) / (xs[2] - xs[0]) - .1) < 1e-10);
  assert.equal(time.querySelectorAll('[data-timeline-event]').length, 4);
  assert.deepEqual([...time.querySelectorAll('time')].map(node => node.dateTime), ['2026-01-01', '2026-01-02', '2026-01-11']);
  assert.match(time.textContent, /<script>run\(\)<\/script>/);
});

test('pointer handles move and resize a local draft; collision/Escape/pointercancel refuse drops; keyboard and preview use same layout', async t => {
  const ui = await domFixture(t), saved = librarySnapshot(), operations = [];
  saved.spec.blocks.push({ ...structuredClone(saved.spec.blocks[0]), block_id: 'other', title: '另一块', layout: { x: 6, y: 0, w: 6, h: 5 } });
  const client = createLibraryBoardClient(async (_channel, operation, payload) => {
    operations.push(operation);
    if (operation === 'list') return ok(listOf(saved));
    if (operation === 'get') return ok(saved);
    if (operation === 'layout_preview') {
      const result = structuredClone(saved); result.spec.version++;
      for (const update of payload.layouts) result.spec.blocks.find(block => block.block_id === update.block_id).layout = update.layout;
      return ok(libraryPreview(result, { operation: 'LAYOUT' }));
    }
    throw new Error(`unexpected ${operation}`);
  }); t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(saved.spec.board_id));
  assert.equal(ui.doc.querySelector('[data-layout-mode]'), null);
  await ui.click('[data-testid=layout-start]');
  const grid = ui.doc.querySelector('[data-testid=library-board-grid]'), region = ui.doc.querySelector('.sm-layout-scroll');
  assert.equal(ui.doc.defaultView.getComputedStyle(grid).overflow, 'clip', 'the shipped CSS clips a raw ghost instead of extending the finite grid; physical bounds are browser-tested');
  grid.getBoundingClientRect = () => ({ width: 1000 });
  region.getBoundingClientRect = () => ({ left: 0, top: 0, right: 1000, bottom: 900 });
  const move = '[data-block-id=note] [data-layout-mode=move]', resize = '[data-block-id=note] [data-layout-mode=resize]';
  const box = () => client.getSnapshot().layoutDraft.spec.blocks[0].layout;
  await ui.pointer(move, 'pointerdown', 100, 100);
  await ui.pointer(null, 'pointermove', 270, 100);
  assert.equal(ui.doc.querySelector('[data-testid=layout-target]').dataset.valid, 'false');
  await ui.pointer(null, 'pointerup', 270, 100);
  assert.deepEqual(box(), saved.spec.blocks[0].layout);
  assert.match(ui.doc.querySelector('[data-testid=layout-status]').textContent, /重叠/);
  await ui.pointer(move, 'pointerdown', 100, 100); await ui.pointer(null, 'pointermove', 270, 440);
  assert.ok(ui.doc.querySelector('[data-testid=layout-ghost]').style.transform.includes('170px'));
  assert.deepEqual(box(), saved.spec.blocks[0].layout, 'pointermove is only a visual candidate');
  await ui.key(null, 'Escape'); await ui.pointer(null, 'pointerup', 270, 440);
  assert.deepEqual(box(), saved.spec.blocks[0].layout);
  await ui.pointer(move, 'pointerdown', 100, 100); await ui.pointer(null, 'pointermove', 270, 440);
  await ui.pointer(null, 'pointercancel', 270, 440); assert.deepEqual(box(), saved.spec.blocks[0].layout);
  await ui.pointer(move, 'pointerdown', 100, 100); await ui.pointer(null, 'pointermove', 270, 440);
  await ui.pointer(null, 'pointerup', 270, 440); assert.deepEqual(box(), { x: 2, y: 6, w: 6, h: 5 });
  await ui.pointer(resize, 'pointerdown', 300, 400); await ui.pointer(null, 'pointerup', 470, 512);
  assert.deepEqual(box(), { x: 2, y: 6, w: 8, h: 7 });
  await ui.key(move, 'ArrowDown', true); assert.equal(box().y, 11);
  await ui.key(resize, 'ArrowLeft'); assert.equal(box().w, 7);
  assert.deepEqual(client.getSnapshot().saved, saved);
  assert.deepEqual(client.getSnapshot().layoutDraft.spec.blocks[1], saved.spec.blocks[1]);
  assert.deepEqual(operations, ['list', 'get']);
  await ui.click('[data-testid=layout-preview]');
  assert.deepEqual(operations, ['list', 'get', 'layout_preview']);
  assert.equal(ui.doc.querySelector('[data-layout-mode]'), null);
  assert.match(ui.doc.querySelector('[data-testid=library-preview-banner]').textContent, /布局预览/);
  assert.deepEqual(client.getSnapshot().saved, saved);
});

for (const mode of ['move', 'resize']) for (const axis of ['x', 'y']) {
  test(`parent and inner scrolling update a stationary ${mode} ${axis} gesture without writing saved state`, async t => {
    const ui = await domFixture(t), saved = librarySnapshot(), operations = [];
    const client = createLibraryBoardClient(async (_channel, operation) => {
      operations.push(operation);
      return operation === 'list' ? ok(listOf(saved)) : ok(saved);
    }); t.after(() => client.dispose());
    await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
      themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
    await act(async () => client.openBoard(saved.spec.board_id));
    await ui.click('[data-testid=layout-start]');
    const region = ui.doc.querySelector('.sm-layout-scroll'), grid = ui.doc.querySelector('.sm-layout-grid');
    grid.getBoundingClientRect = () => ({ width: 1000 });
    let left = 20, top = 200;
    region.getBoundingClientRect = () => ({ left, top, right: left + 1000, bottom: top + 500, width: 1000, height: 500 });
    const handle = `[data-block-id=note] [data-layout-mode=${mode}]`;
    const changeScroll = async (parentDelta, innerDelta) => {
      left = 20 - (axis === 'x' ? parentDelta : 0);
      top = 200 - (axis === 'y' ? parentDelta : 0);
      region[axis === 'x' ? 'scrollLeft' : 'scrollTop'] = innerDelta;
      // Scroll does not bubble. The canvas must observe ancestor scroll in capture phase.
      await act(async () => region.parentElement.dispatchEvent(new ui.doc.defaultView.Event('scroll')));
    };
    const assertCandidate = delta => {
      const target = ui.doc.querySelector('[data-testid=layout-target]');
      const property = mode === 'move' ? (axis === 'x' ? 'left' : 'top') : (axis === 'x' ? 'width' : 'height');
      const base = mode === 'move' ? 0 : axis === 'x' ? 492 : 264;
      assert.equal(Number.parseFloat(target.style[property]), base + delta);
      assert.deepEqual(client.getSnapshot().layoutDraft.spec, saved.spec, 'scroll is a visual candidate only');
    };
    const pitch = axis === 'x' ? (1000 + 16) / 12 : 56;
    await ui.pointer(handle, 'pointerdown', 300, 350);
    await changeScroll(pitch * 2, 0); assertCandidate(pitch * 2);
    await changeScroll(pitch, pitch); assertCandidate(pitch * 2); // Same total, no double counting.
    await changeScroll(0, 0); assertCandidate(0); // Reversing the ancestor scroll returns the candidate.
    await changeScroll(pitch * 2, 0);
    await ui.key(null, 'Escape'); await ui.pointer(null, 'pointerup', 300, 350);
    assert.deepEqual(client.getSnapshot().layoutDraft.spec, saved.spec);
    await changeScroll(0, 0);
    await ui.pointer(handle, 'pointerdown', 300, 350);
    await changeScroll(pitch, pitch);
    await ui.pointer(null, 'pointerup', 300, 350);
    const expected = { ...saved.spec.blocks[0].layout };
    expected[mode === 'move' ? axis : axis === 'x' ? 'w' : 'h'] += 2;
    assert.deepEqual(client.getSnapshot().layoutDraft.spec.blocks[0].layout, expected);
    assert.deepEqual(client.getSnapshot().saved, saved);
    assert.deepEqual(operations, ['list', 'get'], 'parent scrolling and pointer release never call save');
  });
}

for (const scenario of [
  { name: 'screen bottom', rect: [20, 300, 1020, 900], point: [300, 695], axis: 'scrollTop', direction: 1 },
  { name: 'screen top', rect: [20, -200, 1020, 500], point: [300, 5], axis: 'scrollTop', direction: -1 },
  { name: 'screen right', rect: [20, 100, 1020, 650], point: [795, 400], axis: 'scrollLeft', direction: 1 },
  { name: 'clipping parent bottom', rect: [20, 100, 1020, 650], parent: [20, 100, 800, 500], point: [300, 495], axis: 'scrollTop', direction: 1 },
  { name: 'clipping parent right', rect: [20, 100, 1020, 650], parent: [20, 100, 600, 650], point: [595, 400], axis: 'scrollLeft', direction: 1 },
  { name: 'visual viewport bottom', rect: [20, 100, 1020, 650], viewport: { offsetLeft: 0, offsetTop: 50, width: 800, height: 400 }, point: [300, 445], axis: 'scrollTop', direction: 1 },
  { name: 'fully off-screen region', rect: [20, 800, 1020, 1400], point: [300, 1395], axis: 'scrollTop', direction: 0 },
]) test(`visible-edge scrolling lifecycle: ${scenario.name}`, async t => {
  const ui = await domFixture(t), saved = librarySnapshot(), operations = [];
  const client = createLibraryBoardClient(async (_channel, operation) => {
    operations.push(operation);
    return operation === 'list' ? ok(listOf(saved)) : ok(saved);
  }); t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(saved.spec.board_id));
  await ui.click('[data-testid=layout-start]');
  const win = ui.doc.defaultView, frames = new Map(); let frameId = 0, time = 100;
  win.requestAnimationFrame = callback => { frames.set(++frameId, callback); return frameId; };
  win.cancelAnimationFrame = id => frames.delete(id);
  Object.defineProperties(win, { innerWidth: { value: 800, configurable: true }, innerHeight: { value: 700, configurable: true } });
  if (scenario.viewport) Object.defineProperty(win, 'visualViewport', { value: scenario.viewport, configurable: true });
  const rect = ([left, top, right, bottom]) => ({ left, top, right, bottom, width: right - left, height: bottom - top });
  const region = ui.doc.querySelector('.sm-layout-scroll'), grid = ui.doc.querySelector('.sm-layout-grid');
  grid.getBoundingClientRect = () => ({ width: 1000 });
  region.getBoundingClientRect = () => rect(scenario.rect);
  Object.defineProperties(region, { clientWidth: { value: scenario.rect[2] - scenario.rect[0] }, clientHeight: { value: scenario.rect[3] - scenario.rect[1] } });
  region.scrollTop = 1000; region.scrollLeft = 100;
  if (scenario.parent) {
    const parent = region.parentElement; parent.style.overflowX = 'hidden'; parent.style.overflowY = 'hidden';
    parent.getBoundingClientRect = () => rect(scenario.parent);
    Object.defineProperties(parent, { clientWidth: { value: scenario.parent[2] - scenario.parent[0] }, clientHeight: { value: scenario.parent[3] - scenario.parent[1] } });
  }
  const tick = () => act(async () => { time += 16; const next = [...frames.values()]; frames.clear(); for (const callback of next) callback(time); });
  const before = region[scenario.axis];
  await ui.pointer('[data-block-id=note] [data-layout-mode=move]', 'pointerdown', 300, 350);
  await ui.pointer(null, 'pointermove', ...scenario.point);
  await tick(); const first = region[scenario.axis];
  if (scenario.direction === 0) {
    assert.equal(first, before, 'an entirely hidden canvas must not scroll');
    await ui.pointer(null, 'pointercancel', ...scenario.point); await tick();
    assert.equal(frames.size, 0); assert.deepEqual(client.getSnapshot().layoutDraft.spec, saved.spec);
    return;
  }
  assert.ok((first - before) * scenario.direction > 0, `expected visible-edge scrolling: ${before} -> ${first}`);
  await tick(); assert.ok((region[scenario.axis] - first) * scenario.direction > 0, 'stationary held pointer keeps scrolling');
  const index = scenario.axis === 'scrollTop' ? 1 : 0;
  const viewStart = scenario.viewport ? (index ? scenario.viewport.offsetTop : scenario.viewport.offsetLeft) : 0;
  const viewEnd = viewStart + (scenario.viewport ? (index ? scenario.viewport.height : scenario.viewport.width) : index ? 700 : 800);
  const low = Math.max(scenario.rect[index], scenario.parent?.[index] ?? -Infinity, viewStart);
  const high = Math.min(scenario.rect[index + 2], scenario.parent?.[index + 2] ?? Infinity, viewEnd);
  const reverse = [...scenario.point]; reverse[index] = scenario.direction > 0 ? low + 5 : high - 5;
  const turning = region[scenario.axis];
  await ui.pointer(null, 'pointermove', ...reverse); await tick();
  assert.ok((region[scenario.axis] - turning) * scenario.direction < 0, 'crossing to the other visible edge reverses scrolling');
  assert.deepEqual(client.getSnapshot().layoutDraft.spec, saved.spec, 'auto-scroll is only a candidate, not a draft commit');
  await ui.key(null, 'Escape'); const stopped = region[scenario.axis];
  await tick(); assert.equal(region[scenario.axis], stopped); assert.equal(frames.size, 0);
  await ui.pointer(null, 'pointerup', ...scenario.point);
  assert.deepEqual(client.getSnapshot().layoutDraft.spec, saved.spec);
  assert.deepEqual(operations, ['list', 'get'], 'no server mutation during a gesture or cancellation');
  await ui.click('[data-testid=layout-cancel]');
  await ui.click('[data-testid=layout-start]');
  assert.equal(ui.doc.querySelector('[data-testid=layout-status]').textContent, '', 'new editing session clears the cancelled gesture status');
});

function visible(el) {
  assert.ok(el);
  assert.equal(el.closest('[hidden]'), null);
}

test('native library cockpit opens 人群行动 without the old overlay', async t => {
  globalThis.__SHINE_CROWD_ACTION__ = true;
  t.after(() => { delete globalThis.__SHINE_CROWD_ACTION__; });
  const ui = await domFixture(t), snapshot = librarySnapshot(), pending = libraryPreview(snapshot);
  const client = createLibraryBoardClient(async (_channel, operation) => {
    if (operation === 'list') return ok(listOf(snapshot));
    if (operation === 'preview') return ok(pending);
    return ok(snapshot);
  });
  t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  await act(async () => client.openBoard(snapshot.spec.board_id));
  const entry = ui.doc.querySelector('[data-testid="analytics-competition-actions"]');
  assert.equal(entry?.textContent, '人群行动');
  assert.equal(ui.doc.querySelector('[data-testid="sm-competition-actions"]'), null);
  assert.equal(ui.doc.querySelector('[data-testid="library-board-view"]').hidden, false);
  entry.focus();
  await ui.click('[data-testid="analytics-competition-actions"]');
  assert.equal(entry.getAttribute('aria-pressed'), 'true');
  assert.equal(ui.doc.activeElement, entry, 'switching tabs does not steal focus to the heading');
  const actions = ui.doc.querySelector('[data-testid="sm-competition-actions"]');
  assert.ok(actions);
  assert.equal(actions.getAttribute('data-auto-send'), '0');
  assert.match(ui.doc.querySelector('[data-testid="sm-no-auto-send"]').textContent, /不自动发送/);
  assert.equal(ui.doc.querySelector('[data-testid="library-board-view"]').hidden, true);
  assert.equal(ui.doc.querySelector('[data-testid="analytics-b0-dialog"]'), null);
  await ui.click('[data-testid="library-panel-board"]');
  assert.equal(ui.doc.querySelector('[data-testid="library-board-view"]').hidden, false);
  assert.equal(ui.doc.querySelector('[data-testid="analytics-competition-actions-view"]').hidden, true);
  await ui.click('[data-testid=layout-start]');
  visible(ui.doc.querySelector('[data-testid=library-layout-banner]'));
  await ui.click('[data-testid="analytics-competition-actions"]');
  visible(ui.doc.querySelector('[data-testid=library-layout-banner]'));
  assert.equal(ui.doc.querySelector('[data-testid=library-layout-banner]').closest('[data-testid=library-board-view]'), null);
  await ui.click('[data-testid="library-panel-board"]');
  await ui.click('[data-testid=layout-cancel]');
  await act(async () => client.openPreview(pending.preview_id));
  visible(ui.doc.querySelector('[data-testid=library-preview-banner]'));
  await ui.click('[data-testid="analytics-competition-actions"]');
  visible(ui.doc.querySelector('[data-testid=library-preview-banner]'));
  assert.ok(ui.doc.querySelector('[data-testid=library-confirm]'));
  assert.equal(ui.doc.querySelector('[data-testid=library-preview-banner]').closest('[data-testid=library-board-view]'), null);
});

test('crowd-action pack off hides the native 人群行动 entry', async t => {
  globalThis.__SHINE_CROWD_ACTION__ = false;
  t.after(() => { delete globalThis.__SHINE_CROWD_ACTION__; });
  const ui = await domFixture(t), snapshot = librarySnapshot();
  const client = createLibraryBoardClient(async (_channel, operation) => operation === 'list' ? ok(listOf(snapshot)) : ok(snapshot));
  t.after(() => client.dispose());
  await ui.render(React.createElement(LibraryCockpitPanel, { library: client,
    themeSource: { subscribe: () => () => {}, getSnapshot: () => 'light' }, goConversation() {} }));
  assert.equal(ui.doc.querySelector('[data-testid="analytics-competition-actions"]'), null);
  assert.equal(ui.doc.querySelector('[data-testid="analytics-competition-actions-view"]'), null);
  assert.equal(ui.doc.querySelector('[data-testid="library-panel-board"]')?.textContent, '我的驾驶舱');
});
