/** Lane G: native page-package delivery tool to workbench generate. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';

const plugin = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(plugin, '../../.context/dsh-b0/upstream'));
const pin = JSON.parse(await readFile(join(plugin, 'toolchain.json'), 'utf8'));
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: upstream, encoding: 'utf8' }).trim(), pin.upstream_sha);
const { PAGE_GENERATE_TOOL_NAME, PAGE_REQUEST_ID_PATTERN, PAGE_TOOL_RESULT_SCHEMA } = await import(pathToFileURL(join(plugin, 'src/competition-agent/page-family.mjs')));
const { executePageTool, PAGE_TOOL_PARAMETERS } = await import(pathToFileURL(join(plugin, 'src/competition-agent/page-tools.mjs')));
const { createNativePageGenerate, createPagePackageWaiter, extractPagePackage } = await import(pathToFileURL(join(plugin, 'src/client/free-html-library/native-generate.mjs')));
const { createFreeHtmlLibraryStore } = await import(pathToFileURL(join(plugin, 'src/client/free-html-library/store.mjs')));
const { createLivePageAdapters } = await import(pathToFileURL(join(plugin, 'src/client/free-html-library/live-adapters.mjs')));
const { AGENT_PACKAGE, createIsolatedFetch } = await import(pathToFileURL(join(plugin, 'src/client/free-html-library/p12-http-fakes.mjs')));

const REQUEST_ID = 'page-gen-test0001-delivery';
const execution = { agent: { session: { id: 'session_page_fixture' } }, signal: new AbortController().signal };

test('host page generate targets the visible session and reuses the waiter requestId', async () => {
  const source = await readFile(join(plugin, 'src/client/index.tsx'), 'utf8');
  assert.match(source, /resolvePageGenerateSession/);
  assert.doesNotMatch(source, /B0_PRIMARY_SESSION_ID\) \?\? ids\[0\]/);
  assert.match(source, /requestId: requestId as never/);
  assert.match(source, /const remoteWorkspaceFiles = \(\) =>/);
  assert.match(source, /catch \{\s*return undefined;/);
});

test('page tool delivers a valid free-page package', async () => {
  const receipt = await executePageTool(PAGE_GENERATE_TOOL_NAME, {
    request_id: REQUEST_ID,
    package: { html: '<html><h1>原生Agent标题</h1></html>', css: 'h1{}', js: 'window.__g=true' },
  }, execution);
  assert.equal(receipt.status, 'PACKAGE_RECEIVED');
  assert.equal(receipt.schema_version, PAGE_TOOL_RESULT_SCHEMA);
  assert.equal(receipt.request_id, REQUEST_ID);
  assert.equal(receipt.published, false);
  assert.equal(receipt.package.html.includes('原生Agent标题'), true);
  assert.equal(Object.hasOwn(PAGE_TOOL_PARAMETERS, PAGE_GENERATE_TOOL_NAME), true);
});

test('page tool refuses bad packages and never saves or calls HTTP', async () => {
  const refusedEmpty = await executePageTool(PAGE_GENERATE_TOOL_NAME, {
    request_id: REQUEST_ID,
    package: { html: '   ' },
  }, execution);
  assert.equal(refusedEmpty.status, 'REFUSED');
  assert.match(String(refusedEmpty.error.message), /html/);
  const refusedNoRequest = await executePageTool(PAGE_GENERATE_TOOL_NAME, {
    package: { html: '<html>x</html>' },
  }, execution);
  assert.equal(refusedNoRequest.status, 'REFUSED');
  const refusedSession = await executePageTool(PAGE_GENERATE_TOOL_NAME, {
    request_id: REQUEST_ID, package: { html: '<html>x</html>' },
  }, { agent: {}, signal: new AbortController().signal });
  assert.equal(refusedSession.error.code, 'SESSION_REQUIRED');
  const source = await readFile(join(plugin, 'src/competition-agent/page-tools.mjs'), 'utf8');
  assert.doesNotMatch(source, /fetch\(|:6677|child_process|COMPETITION_HTTP/);
});

test('generate waits for delivery tool and persists the native package', async () => {
  const waiter = createPagePackageWaiter();
  const prompts = [];
  const generate = createNativePageGenerate({
    waiter,
    submitPrompt: async (prompt, extras) => {
      prompts.push({ prompt, requestId: extras?.requestId });
      return { ok: true, value: { accepted: true } };
    },
  });
  const isolated = createIsolatedFetch({ token: 'library-page-isolated-test-token-32chars' });
  const adapters = createLivePageAdapters({
    nativeGenerate: generate,
    documentsHttp: { base: 'http://127.0.0.1:18091', token: 'library-page-isolated-test-token-32chars', fetchImpl: isolated.fetchImpl },
    resultHttp: { base: 'http://127.0.0.1:18091', token: 'library-page-isolated-test-token-32chars', fetchImpl: isolated.fetchImpl },
  });
  const store = createFreeHtmlLibraryStore({ adapters, viewportWidth: 1440 });
  const pending = store.generate();
  // The prompt receipt is synchronous, but the waiter registers one microtask
  // after submitPrompt settles; flush until the intake holds the request.
  for (let i = 0; i < 50 && waiter.pendingCount === 0; i += 1) await Promise.resolve();
  assert.equal(prompts.length, 1);
  assert.match(prompts[0].requestId, PAGE_REQUEST_ID_PATTERN);
  assert.equal(waiter.pendingCount, 1);
  assert.equal(waiter.deliver(prompts[0].requestId, AGENT_PACKAGE), true);
  await pending;
  const html = store.getSnapshot().current.package.html;
  assert.match(html, /原生Agent标题/);
  assert.doesNotMatch(html, /示例标题/);
  assert.equal(store.getSnapshot().current.binding_state, 'UNBOUND_SAMPLE');
});

test('refused delivery fails generate and keeps the prompt', async () => {
  const waiter = createPagePackageWaiter();
  const generate = createNativePageGenerate({
    waiter,
    submitPrompt: async () => ({ ok: true, value: { accepted: true } }),
  });
  const store = createFreeHtmlLibraryStore({
    adapters: createLivePageAdapters({ nativeGenerate: generate }),
    viewportWidth: 1440,
  });
  store.setPrompt('保留我');
  const pending = store.generate();
  await new Promise(resolveDelay => setTimeout(resolveDelay, 0));
  waiter.cancelAll();
  await pending;
  assert.equal(store.getSnapshot().prompt, '保留我');
  assert.equal(store.getSnapshot().current, null);
  assert.match(store.getSnapshot().message, /未返回页面源码包|拒收/);
});

test('waiter times out a lost delivery and rejects the generate', async () => {
  const waiter = createPagePackageWaiter();
  const generate = createNativePageGenerate({
    waiter,
    submitPrompt: async () => ({ ok: true, value: { accepted: true } }),
  });
  const error = await generate('超时页', { timeoutMs: 20 }).then(() => null, caught => caught);
  assert.equal(error?.code, 'NATIVE_GENERATE_UNAVAILABLE');
  assert.match(error.message, /时限/);
  assert.equal(waiter.pendingCount, 0);
});

test('tool card registration wires the delivery intake (compiled client)', {
  skip: existsSync(join(plugin, 'lib/client.js')) ? false : 'plugin lib/client.js is built later in pipeline --check',
}, async () => {
  const webRequire = (await import('node:module')).createRequire(join(upstream, 'apps/web/package.json'));
  const stores = await import(pathToFileURL(join(upstream, 'packages/client/store/lib/index.js')).href);
  const source = await readFile(join(plugin, 'lib/client.js'), 'utf8');
  assert.match(source, /free_html_page_generate/);
  assert.match(source, /free-page-tool-result\/v1/);
  let factoryRow;
  const browser = {
    localStorage: { getItem: () => null },
    __ModuleLoader__: { load: row => { factoryRow = row; } },
  };
  const vm = await import('node:vm');
  vm.runInNewContext(source, { window: browser, __SHINE_QUERY__: true, __SHINE_BOARD__: true }, { filename: 'analytics-b0-client.js', timeout: 1000 });
  const client = factoryRow.factory(spec => {
    assert.ok(['react', 'react-dom', 'react/jsx-runtime', '@deepseek-ai/dsh-client-store'].includes(spec), `unexpected browser require: ${spec}`);
    return spec === '@deepseek-ai/dsh-client-store' ? stores : webRequire(spec);
  });
  const entries = [];
  const effects = [];
  let notify;
  let snapshot = { phase: 'ready', ids: ['session_page'], byId: { session_page: { id: 'session_page', retainedBy: {} } } };
  client.apply({
    effect: factory => { effects.push(factory()); },
    theme: { overrideTokens: () => () => {} },
    layout: { selectPanel: () => {} },
    sessions: {
      list: { getSnapshot: () => snapshot, subscribe: listener => { notify = listener; return () => {}; } },
      retain: () => ({ release() {} }),
      create: () => assert.fail('no session create'),
    },
    slots: {
      inject: (_name, callback) => callback(),
      register: (options, component) => { entries.push({ options, component }); return () => {}; },
    },
  });
  const pageCard = entries.find(row => row.options.key === PAGE_GENERATE_TOOL_NAME);
  assert.ok(pageCard, 'page tool card is registered');
  assert.equal(typeof pageCard.options.inject().pagePackageWaiter, 'object');
  const waiter = pageCard.options.inject().pagePackageWaiter;
  const React = webRequire('react');
  const { renderToStaticMarkup } = webRequire('react-dom/server');
  // Running state: no waiter delivery before the tool result arrives.
  const running = renderToStaticMarkup(React.createElement(pageCard.component, {
    block: { kind: 'tool-call', callId: 'c1' }, pagePackageWaiter: waiter,
  }));
  assert.match(running, /正在等待原生 Agent 交付页面源码包/);
  // Success receipt hands the package to the waiter.
  const requestId = 'page-gen-abcdef12-card';
  renderToStaticMarkup(React.createElement(pageCard.component, {
    block: {
      kind: 'tool-result', callId: 'c2', isError: false,
      call: { name: PAGE_GENERATE_TOOL_NAME },
      meta: {
        schema_version: PAGE_TOOL_RESULT_SCHEMA, status: 'PACKAGE_RECEIVED',
        request_id: requestId, session_id: 's', published: false,
        package: { html: '<html><h1>原生Agent标题</h1></html>', css: '', js: '', resources: [], node_map: [] },
      },
    },
    pagePackageWaiter: waiter,
  }));
  assert.equal(waiter.pendingCount, 0);
  for (const dispose of effects) if (typeof dispose === 'function') dispose();
});
