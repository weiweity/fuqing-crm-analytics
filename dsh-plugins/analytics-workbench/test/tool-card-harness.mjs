/** Actual compiled plugin + pinned React renderer, synthetic owner props only.
 * This is a component harness, not a native session or a business execution.
 */
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';
import { FIXTURE, TOOL_NAME } from '../src/model.mjs';

const root = fileURLToPath(new URL('..', import.meta.url));
const upstream = resolve(process.env.B0_BUILD_UPSTREAM ?? join(root, '../../.context/dsh-b0/upstream'));
const call = { callId: 'b0-dom-call', name: TOOL_NAME, argsRaw: '{"query":"channel_repeat_rate"}',
  turn: 1, step: 1, time: 0, subCalls: [] };
const result = { kind: 'tool-result', seq: 2, time: 1, callId: call.callId,
  call: { name: call.name, argsRaw: call.argsRaw }, callTime: 0, content: [], isError: false, subCalls: [], meta: FIXTURE };
export const CARD_CASES = Object.freeze([
  { id: 'running', label: '加载中', block: call, expected: 'B0 合成工具运行中…', success: false },
  { id: 'success', label: '成功', block: result, expected: '复购率 25%', success: true },
  { id: 'tool-error', label: '工具失败', block: { ...result, isError: true, meta: undefined,
    content: [{ type: 'text', text: 'SENSITIVE_FAKE_DETAIL <script>bad()</script>' }] }, expected: 'B0 工具失败', success: false },
  { id: 'unknown-version', label: '未知版本', block: { ...result, meta: { ...FIXTURE, schema_version: 'future/v999' } }, expected: '版本不支持', success: false },
  { id: 'missing-meta', label: '缺失元数据', block: { ...result, meta: undefined }, expected: '结果格式无法识别', success: false },
  { id: 'extra-meta', label: '额外字段拒绝', block: { ...result, meta: { ...FIXTURE, html: '<img src=x onerror=bad()>' } }, expected: '结果格式无法识别', success: false },
  { id: 'changed-facts', label: '错误数值拒绝', block: { ...result, meta: { ...FIXTURE, repeat_rate: 0.99 } }, expected: '结果格式无法识别', success: false },
  { id: 'error-with-meta', label: '失败不能借旧数据变成功', block: { ...result, isError: true }, expected: 'B0 工具失败', success: false },
]);

export async function loadCardHarness() {
  const req = createRequire(join(upstream, 'apps/web/package.json'));
  const React = req('react');
  const { renderToStaticMarkup } = req('react-dom/server');
  const stores = await import(pathToFileURL(join(upstream, 'packages/client/store/lib/index.js')).href);
  const seed = new Map([['react', React], ['react/jsx-runtime', req('react/jsx-runtime')], ['@deepseek-ai/dsh-client-store', stores]]);
  let factory;
  const code = await readFile(join(root, 'lib/client.js'), 'utf8');
  vm.runInNewContext(code, { window: { __ModuleLoader__: { load: row => { factory = row; } } } }, { timeout: 1000 });
  assert.equal(factory.id, '@shine-mage/dsh-analytics-workbench-b0');
  const client = factory.factory(name => { assert.ok(seed.has(name), `Unexpected dependency ${name}`); return seed.get(name); });
  const registrations = [];
  client.apply({ effect: () => {}, sessions: {}, slots: {
    inject: (_name, callback) => callback(),
    register: (options, component) => { registrations.push({ options, component }); return () => {}; },
  } });
  const cards = registrations.filter(r => r.options.name === 'tool.call.toolview');
  assert.equal(cards.length, 1); assert.equal(cards[0].options.key, TOOL_NAME);
  const brand = registrations.find(r => r.options.name === 'sidebar.brand.mark');
  const brandHtml = renderToStaticMarkup(React.createElement(brand.component, { size: 24 }));
  const css = brandHtml.match(/<style>([\s\S]*?)<\/style>/)?.[1];
  assert.ok(css?.includes('.analytics-b0-card'));
  return { css, client_sha256: createHash('sha256').update(code).digest('hex'), registrations,
    render(block) {
      const wire = JSON.stringify(block);
      const frozenOwner = JSON.parse(wire);
      const html = renderToStaticMarkup(React.createElement(cards[0].component, { block: frozenOwner,
        callId: frozenOwner.callId, toolName: TOOL_NAME,
        openFile: () => assert.fail('Component tried to open a file'),
        loadImage: () => assert.fail('Component tried to load a private image') }));
      assert.equal(JSON.stringify(frozenOwner), wire, 'Renderer mutated owner evidence');
      return html;
    } };
}
