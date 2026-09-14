/** Source + live DOM for the BoardSpec canvas. Fixture only; no HTTP. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from '../board-spec/fixture.mjs';
import { COMPONENT_CATALOG } from '../board-spec/component-catalog.mjs';
import { COMPONENT_FACTS_VERSION } from '../board-spec/component-view.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const plugin = resolve(here, '../..');
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const webReq = createRequire(join(upstream, 'apps/web/package.json'));
const vite = createRequire(webReq.resolve('vite/package.json'));
const esbuild = vite('esbuild');
const React = webReq('react');
const { createRoot } = webReq('react-dom/client');
const testUtils = webReq('react-dom/test-utils');
const act = typeof React.act === 'function' ? React.act : testUtils.act;
const { JSDOM } = createRequire(join(upstream, 'node_modules/jsdom/package.json'))('jsdom');

const canvasSource = await readFile(join(here, 'board-spec-canvas.tsx'), 'utf8');

function libraryFixture() {
  const spec = { board_id: 'library-dom-fixture', version: 1, blocks: COMPONENT_CATALOG.components.map((c, i) => ({
    block_id: c.kind, kind: c.kind, title: c.name, library_version: COMPONENT_CATALOG.library_version,
    layout: { x: 0, y: i * 10, ...c.default_size }, ...(c.allows_result === false ? {} : { source_result_id: 'synthetic_verified' }),
    props: c.kind === 'TEXT' ? { content: '初始备注' } : c.kind === 'TABLE' ? { page_size: 5 }
      : c.kind === 'PROCESS' ? { nodes: [{ id: 'a', label: '核对' }] }
      : c.kind === 'TIMELINE' ? { events: [{ id: 'a', date: '2026-09-13', label: '讨论' }] } : {},
  })) };
  const facts = { synthetic_verified: { schema_version: COMPONENT_FACTS_VERSION,
    scalar: { value: 12.5, comparison: 10, unit: '万元' },
    waterfall: { unit: '万元', start: { label: '起点', value: 10 }, end: { label: '终点', value: 12.5 },
      contributions: [{ label: '核验贡献', value: 2.5 }] },
    series: { ordered: true, unit: '万元', points: [{ label: '七月', value: -5 }, { label: '八月', value: null }, { label: '九月', value: 12.5 }] },
    table: { columns: [{ key: 'period', label: '日期' }, { key: 'amount', label: '金额', unit: '万元' }],
      rows: Array.from({ length: 12 }, (_, i) => ({ period: `日期${i + 1}`, amount: i })) },
    evidence: { source_label: '合成验证结果', items: [{ label: '截数日期', value: '2026-09-13' }] },
  } };
  return { spec, facts };
}

const MIXED_SPEC = {
  board_id: 'board_d_mix',
  version: 1,
  blocks: [
    { block_id: 'u1', kind: 'METRIC', title: '未绑定' },
    { block_id: 'm1', kind: 'METRIC', title: '零售 GSV', metric_ref: 'retail_gsv', source_result_id: 'r1' },
    {
      block_id: 'h1',
      kind: 'html_sandbox',
      title: '脏 HTML',
      html: '<script>window.parent.steal()</script><img src=x onerror=bad()>',
    },
    { block_id: 'l1', kind: 'LINK', title: '飞书文档', url: 'https://example.invalid/feishu/doc/channel' },
  ],
};

async function loadCanvas() {
  await mkdir(join(plugin, 'lib'), { recursive: true });
  const outfile = join(plugin, 'lib/test-board-spec-canvas.mjs');
  await esbuild.build({
    absWorkingDir: plugin,
    entryPoints: ['src/client/board-spec-canvas.tsx'],
    outfile,
    bundle: true,
    format: 'esm',
    platform: 'browser',
    target: 'es2022',
    jsx: 'automatic',
    external: ['react', 'react/jsx-runtime', 'react-dom'],
    logLevel: 'silent',
  });
  return import(pathToFileURL(outfile).href);
}

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://127.0.0.1:4318/' });
  const previous = {
    window: globalThis.window,
    document: globalThis.document,
    act: globalThis.IS_REACT_ACT_ENVIRONMENT,
  };
  previous.browserGlobals = new Map(
    ['getComputedStyle', 'HTMLElement', 'Element', 'SVGElement', 'ShadowRoot', 'HTMLTextAreaElement', 'HTMLButtonElement', 'HTMLInputElement']
      .map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]),
  );
  for (const key of previous.browserGlobals.keys()) {
    const value = typeof dom.window[key] === 'function' && key === 'getComputedStyle'
      ? dom.window[key].bind(dom.window)
      : dom.window[key];
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  }
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return { dom, previous };
}

function restoreDom(previous) {
  for (const [key, descriptor] of previous.browserGlobals) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
  if (previous.window === undefined) delete globalThis.window; else globalThis.window = previous.window;
  if (previous.document === undefined) delete globalThis.document; else globalThis.document = previous.document;
  if (previous.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  else globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
}

function typeAsk(text) {
  const input = globalThis.document.querySelector('[data-testid="sm-board-spec-ask-input"]');
  testUtils.Simulate.change(input, { target: { value: text } });
}

test('registered component DOM: line gaps, table pagination, units and escaped text are real renderers', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  const fixture = libraryFixture();
  fixture.spec.blocks.find(b => b.kind === 'TEXT').props.content = '<img src=x onerror=bad()>\n<script>bad()</script>';
  try {
    await act(() => root.render(React.createElement(BoardSpecCanvas, fixture)));
    const document = dom.window.document;
    for (const kind of COMPONENT_CATALOG.components.map(c => c.kind)) assert.ok(document.querySelector(`[data-testid="sm-library-${kind.toLowerCase()}"]`));
    assert.equal(document.querySelector('[data-testid="sm-library-metric-value"]').textContent, '12.5');
    assert.match(document.querySelector('[data-testid="sm-library-metric"]').textContent, /单位：万元/);
    const path = document.querySelector('[data-testid="sm-library-line-path"]');
    assert.equal((path.getAttribute('d').match(/M/g) ?? []).length, 2, 'null gap must break the actual SVG path');
    assert.equal(path.getAttribute('d').includes('L'), false);
    assert.equal(document.querySelectorAll('[data-testid="sm-library-line"] circle').length, 2);
    assert.equal(document.querySelectorAll('[data-testid="sm-library-bar"] .sm-library-fill').length, 2);
    const table = document.querySelector('[data-testid="sm-library-table"]');
    assert.equal(table.querySelectorAll('tbody tr').length, 5);
    await act(() => [...table.querySelectorAll('button')].find(b => b.textContent === '下一页').click());
    assert.match(table.querySelector('tbody').textContent, /日期6/);
    assert.equal(document.querySelector('[data-testid="sm-board-spec-block-TABLE"]').getAttribute('data-on'), '0', 'pagination must not select or edit a block');
    const text = document.querySelector('[data-testid="sm-library-text"]');
    assert.match(text.textContent, /<script>bad/);
    assert.equal(text.querySelector('script,img'), null);
    assert.equal(document.querySelectorAll('[data-testid="sm-library-evidence"] dt').length, 1);
  } finally {
    await act(() => root.unmount()); dom.window.close(); restoreDom(previous);
  }
});

test('six representative property edits: mock proposal transport → cancel unchanged → apply changed → rollback restored', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  const fixture = libraryFixture(), initial = structuredClone(fixture);
  const edits = {
    METRIC: { show_comparison: false }, LINE: { line_style: 'dashed', show_points: false },
    BAR: { orientation: 'vertical' }, TABLE: { columns: ['amount'], sort_field: 'amount', sort_direction: 'desc' },
    TEXT: { content: '新说明', align: 'center' }, EVIDENCE: { expanded: false, summary: '新证据说明' },
  };
  try {
    await act(() => root.render(React.createElement(BoardSpecCanvas, { ...fixture,
      askTransport: { async fetchImpl(_url, options) {
        const request = JSON.parse(options.body);
        return Response.json({ patch: { block_id: request.block_id, base_version: request.version, op: 'set_props', props: edits[request.block_id] } });
      } },
    })));
    const document = dom.window.document;
    const click = id => act(() => document.querySelector(`[data-testid="${id}"]`).click());
    for (const kind of Object.keys(edits)) {
      await click(`sm-board-spec-block-${kind}`);
      await act(() => typeAsk('调整展示'));
      const selector = `[data-testid="sm-library-${kind.toLowerCase()}"]`;
      const original = document.querySelector(selector).innerHTML;
      const untouched = Object.keys(edits).filter(k => k !== kind).map(k => [k, document.querySelector(`[data-testid="sm-library-${k.toLowerCase()}"]`).innerHTML]);
      await click('sm-board-spec-propose');
      assert.ok(document.querySelector('[data-testid="sm-board-spec-patch-modal"]'));
      assert.equal(document.querySelector(selector).innerHTML, original);
      await click('sm-board-spec-cancel');
      assert.equal(document.querySelector(selector).innerHTML, original);
      await click('sm-board-spec-propose');
      await click('sm-board-spec-confirm');
      assert.notEqual(document.querySelector(selector).innerHTML, original, kind);
      for (const [other, html] of untouched) assert.equal(document.querySelector(`[data-testid="sm-library-${other.toLowerCase()}"]`).innerHTML, html, `must not change ${other}`);
      await click('sm-board-spec-rollback');
      assert.equal(document.querySelector(selector).innerHTML, original, `restore ${kind}`);
    }
    assert.deepEqual(fixture, initial, 'neither BoardSpec inputs nor facts may mutate');
  } finally {
    await act(() => root.unmount()); dom.window.close(); restoreDom(previous);
  }
});

test('canvas source paints closed kinds and does not execute HTML', () => {
  assert.match(canvasSource, /data-testid="sm-board-spec-metric-headline"/);
  assert.match(canvasSource, /未绑定结果，不显示 0%/);
  assert.match(canvasSource, /confirmPatch/);
  assert.match(canvasSource, /proposeAsk/);
  assert.match(canvasSource, /sm-board-spec-patch-modal/);
  assert.match(canvasSource, /rollbackPrevious/);
  assert.doesNotMatch(canvasSource, /rollbackTo\(state, 1\)/);
  assert.match(canvasSource, /BOARD_SPEC_KINDS/);
  assert.doesNotMatch(canvasSource, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(canvasSource, /innerHTML\s*=/);
  assert.match(canvasSource, /htmlSandboxFrame/);
  assert.match(canvasSource, /sm-board-spec-iframe/);
  assert.doesNotMatch(canvasSource, /BoardWorkbench/);
  assert.match(canvasSource, /返回对话/);
  assert.doesNotMatch(canvasSource, /from 'tailwind'|tailwindcss/);
});

test('canvas paints bound METRIC 400, unbound empty, and html_sandbox without markup', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  try {
    await act(() => {
      root.render(React.createElement(BoardSpecCanvas, { spec: MIXED_SPEC, facts: BOARD_SPEC_FACTS }));
    });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-metric-headline"]').textContent, '400');
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-unbound"]').textContent, /未绑定结果，不显示 0%/);
    const html = dom.window.document.querySelector('[data-testid="sm-board-spec-html"]');
    assert.match(html.textContent, /沙箱 HTML/);
    assert.doesNotMatch(html.textContent, /steal|onerror|<script|<img/i);
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-block-l1"]'));
    const open = dom.window.document.querySelector('[data-testid="sm-board-spec-open-link"]');
    assert.equal(open.getAttribute('href'), 'https://example.invalid/feishu/doc/channel');
    assert.equal(open.getAttribute('rel'), 'noopener noreferrer');
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-tab-links"]').click(); });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-block-l1"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-metric-headline"]'), null);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-tab-browser"]').click(); });
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-browser"]').textContent, /不改 DSH 壳/);
    const iframe = dom.window.document.querySelector('[data-testid="sm-board-spec-iframe"]');
    assert.ok(iframe);
    assert.equal(iframe.getAttribute('sandbox'), '');
    assert.doesNotMatch(iframe.getAttribute('sandbox') ?? '', /allow-scripts/);
    assert.doesNotMatch(iframe.getAttribute('sandbox') ?? '', /allow-same-origin/);
    assert.match(iframe.getAttribute('srcdoc') ?? '', /steal/);
    assert.equal(dom.window.document.querySelector('script'), null);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('canvas confirm writes title then rollback restores fixture v1', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  try {
    await act(() => {
      root.render(React.createElement(BoardSpecCanvas, {
        spec: BOARD_SPEC_FIXTURE,
        facts: BOARD_SPEC_FACTS,
      }));
    });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-metric-headline"]').textContent, '400');
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-version"]').textContent, /版本 v1/);
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-rollback"]').disabled, true);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-block-b3"]').click(); });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-block-b3"]').getAttribute('data-on'), '1');
    await act(() => { typeAsk('本月渠道占比'); });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-ask-input"]').value, '本月渠道占比');
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-propose"]').click(); });
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-version"]').textContent, /版本 v1/);
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-patch-modal"]'));
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-confirm"]').click(); });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-status"]'), null);
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-patch-modal"]'), null);
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-version"]').textContent, /版本 v2/);
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-block-b3"]').textContent, /本月渠道占比/);
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-rollback"]').disabled, false);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-rollback"]').click(); });
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-version"]').textContent, /版本 v1/);
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-block-b3"]').textContent, /两期连线/);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('invalid spec is rejected and not painted as 0%', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  try {
    await act(() => {
      root.render(React.createElement(BoardSpecCanvas, {
        spec: { board_id: 'x', version: 1, blocks: [{ block_id: 'z', kind: 'PIE' }] },
        facts: {},
      }));
    });
    const reject = dom.window.document.querySelector('[data-testid="sm-board-spec-reject"]');
    assert.ok(reject);
    assert.doesNotMatch(reject.textContent, /0%/);
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-canvas"]'), null);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('open-canvas refresh rebinds METRIC and drops to unbound without 0%', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  try {
    await act(() => {
      root.render(React.createElement(BoardSpecCanvas, {
        spec: BOARD_SPEC_FIXTURE,
        facts: { r1: { current_gsv: 450, comparison_gsv: 300 } },
      }));
    });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-metric-headline"]').textContent, '450');
    await act(() => {
      root.render(React.createElement(BoardSpecCanvas, {
        spec: BOARD_SPEC_FIXTURE,
        facts: {},
      }));
    });
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-unbound"]'));
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-metric-headline"]'), null);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('canvas cancel drops pending; askTransport HTTP stages without writing version', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  let back = 0;
  try {
    await act(() => {
      root.render(React.createElement(BoardSpecCanvas, {
        spec: BOARD_SPEC_FIXTURE,
        facts: BOARD_SPEC_FACTS,
        goConversation() { back += 1; },
        askTransport: {
          async fetchImpl() {
            return Response.json({
              patch: { block_id: 'b3', base_version: 1, op: 'set_title', title: 'HTTP标题' },
            });
          },
        },
      }));
    });
    await act(() => { dom.window.document.querySelector('[data-testid="sm-cockpit-back"]').click(); });
    assert.equal(back, 1);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-block-b3"]').click(); });
    await act(() => { typeAsk('HTTP标题'); });
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-propose"]').click(); });
    for (let i = 0; i < 20 && !dom.window.document.querySelector('[data-testid="sm-board-spec-patch-modal"]'); i += 1) {
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 15)); });
    }
    assert.ok(dom.window.document.querySelector('[data-testid="sm-board-spec-patch-modal"]'));
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-version"]').textContent, /版本 v1/);
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-cancel"]').click(); });
    assert.equal(dom.window.document.querySelector('[data-testid="sm-board-spec-patch-modal"]'), null);
    assert.match(dom.window.document.querySelector('[data-testid="sm-board-spec-version"]').textContent, /版本 v1/);
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});

test('browser tab https URL uses sandbox iframe; refresh_url replaces srcdoc without parent markup', async () => {
  const { BoardSpecCanvas } = await loadCanvas();
  const { previous, dom } = installDom();
  const root = createRoot(dom.window.document.getElementById('root'));
  const priorFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.equal(url, 'https://example.invalid/sandbox');
    return new Response('<p>live-refresh</p>', { status: 200, headers: { 'content-type': 'text/html' } });
  };
  try {
    await act(() => {
      root.render(React.createElement(BoardSpecCanvas, {
        spec: {
          board_id: 'board_refresh',
          version: 1,
          blocks: [{
            block_id: 'h1',
            kind: 'html_sandbox',
            title: '渠道结构',
            html: '<p>seed</p>',
            refresh_url: 'https://example.invalid/sandbox',
          }],
        },
        facts: {},
      }));
    });
    await act(() => { dom.window.document.querySelector('[data-testid="sm-board-spec-tab-browser"]').click(); });
    const urlInput = dom.window.document.querySelector('[data-testid="sm-board-spec-url"]');
    await act(() => { testUtils.Simulate.change(urlInput, { target: { value: 'https://example.invalid/doc' } }); });
    const httpsFrame = dom.window.document.querySelector('[data-testid="sm-board-spec-iframe"]');
    assert.equal(httpsFrame.getAttribute('src'), 'https://example.invalid/doc');
    assert.equal(httpsFrame.getAttribute('sandbox'), '');
    await act(() => { testUtils.Simulate.change(urlInput, { target: { value: '' } }); });
    const refresh = dom.window.document.querySelector('[data-testid="sm-board-spec-html-refresh"]');
    assert.ok(refresh);
    await act(() => { refresh.click(); });
    for (let i = 0; i < 20; i += 1) {
      const srcdoc = dom.window.document.querySelector('[data-testid="sm-board-spec-iframe"]')?.getAttribute('srcdoc') || '';
      if (srcdoc.includes('live-refresh')) break;
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 15)); });
    }
    const htmlFrame = dom.window.document.querySelector('[data-testid="sm-board-spec-iframe"]');
    assert.match(htmlFrame.getAttribute('srcdoc') ?? '', /live-refresh/);
    assert.doesNotMatch(dom.window.document.body.textContent, /live-refresh/);
  } finally {
    globalThis.fetch = priorFetch;
    await act(() => root.unmount());
    dom.window.close();
    restoreDom(previous);
  }
});
