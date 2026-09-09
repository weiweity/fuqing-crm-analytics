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
import { QUERY_TOOL_NAME } from '../src/query-model.mjs';
import { FIRST_PURCHASE_TOOL_NAME } from '../src/first-purchase-query-model.mjs';

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
const queryCounts = {
  channel_mature_cohort_count: 2, channel_immature_count: 0, channel_repeat_count: 1,
  channel_cross_channel_count: 0, channel_repeat_ratio: 0.5, channel_cross_channel_ratio: 0,
  channel_window_net_paid_minor: 100, channel_empty_reason: null,
};
const queryFilters = {
  schema_version: 'analytics-channel-followup/v1', query_id: 'channel_first_observed_followup',
  query_version: 'channel-followup-query/v1', metric_id: 'channel_first_observed_n_day_repeat',
  metric_version: 'channel-followup-metric/v1', data_version: 'synthetic-channel-followup-data/v1',
  hash_version: 'channel-followup-filter-hash/v1', cohort_window_kind: 'FIXED',
  resolved_cohort_start: '2026-05-31T16:00:00.000000+00:00', resolved_cohort_end: '2026-08-31T16:00:00.000000+00:00',
  observation_days: 30, data_snapshot_ref: 'synthetic-channel-followup-v1',
  as_of: '2026-08-31T16:00:00.000000+00:00', timezone: 'Asia/Shanghai', channel_ids: ['A'],
  cohort_ref: null, product_ids: [], exclude_low_price: false, comparison: null,
  permission_scope: 'scope_1', data_digest: 'a'.repeat(64), filter_hash: 'b'.repeat(64),
};
const queryReceipt = {
  schema_version: 'analytics-run-channel-followup-native-receipt/v1',
  run_id: 'run_1', attempt_id: 'attempt_1', step_id: 'step_1', disposition: 'EXECUTE',
  result: {
    schema_version: 'analytics-channel-followup/v1', answer_mode: 'DETERMINISTIC_TOOL',
    query_id: 'channel_first_observed_followup', query_version: 'channel-followup-query/v1',
    metric_id: 'channel_first_observed_n_day_repeat', metric_version: 'channel-followup-metric/v1',
    data_version: 'synthetic-channel-followup-data/v1', hash_version: 'channel-followup-filter-hash/v1',
    contains_real_data: false, data_source: 'SYNTHETIC_SNAPSHOT',
    data_snapshot_ref: 'synthetic-channel-followup-v1', as_of: queryFilters.as_of,
    resolved_filters: queryFilters, filter_hash: queryFilters.filter_hash,
    facts: {
      display_name: '首次观察到的渠道 / N日二单率', currency: 'CNY', amount_unit: 'minor',
      amount_precision: 'integer_fen', observation_days: 30,
      channels: [{ channel_id: 'A', ...queryCounts }], totals: queryCounts,
    },
    limitations: ['synthetic only'],
  },
};
const queryCall = { callId: 'query-dom-call', name: QUERY_TOOL_NAME, argsRaw: '{}', turn: 1, step: 1, time: 0, subCalls: [] };
const queryResult = { kind: 'tool-result', seq: 2, time: 1, callId: queryCall.callId,
  call: { name: queryCall.name, argsRaw: queryCall.argsRaw }, callTime: 0, content: [], isError: false, subCalls: [], meta: queryReceipt };
const emptyCounts = {
  channel_mature_cohort_count: 0, channel_immature_count: 1, channel_repeat_count: 0,
  channel_cross_channel_count: 0, channel_repeat_ratio: null, channel_cross_channel_ratio: null,
  channel_window_net_paid_minor: null, channel_empty_reason: 'EMPTY_MATURE_COHORT',
};
export const QUERY_CARD_CASES = Object.freeze([
  { id: 'query-running', label: '查询加载中', block: queryCall, expected: '合成查询运行中', success: false },
  { id: 'query-success', label: '查询成功', block: queryResult, expected: 'N=30', success: true },
  { id: 'query-null', label: '空成熟队列', block: { ...queryResult, meta: {
    ...queryReceipt, result: { ...queryReceipt.result, resolved_filters: queryFilters,
      facts: { ...queryReceipt.result.facts, channels: [{ channel_id: 'A', ...emptyCounts }], totals: emptyCounts } } } },
    expected: '空成熟队列', success: true },
  { id: 'query-failed', label: '查询失败', block: { ...queryResult, isError: true, meta: undefined,
    content: [{ type: 'text', text: 'SENSITIVE_FAKE_DETAIL <script>bad()</script>' }] }, expected: '查询工具失败', success: false },
  { id: 'query-unknown', label: '查询未知版本', block: { ...queryResult, meta: { ...queryReceipt, schema_version: 'future/v999' } },
    expected: '版本不支持', success: false },
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
  const b0Card = cards.find(row => row.options.key === TOOL_NAME);
  const queryCard = cards.find(row => row.options.key === QUERY_TOOL_NAME);
  const firstPurchaseCard = cards.find(row => row.options.key === FIRST_PURCHASE_TOOL_NAME);
  assert.ok(b0Card); assert.ok(queryCard);
  assert.ok(firstPurchaseCard, 'compiled client is missing the first-purchase renderer');
  const brand = registrations.find(r => r.options.name === 'sidebar.brand.mark');
  const brandHtml = renderToStaticMarkup(React.createElement(brand.component, { size: 24 }));
  const css = brandHtml.match(/<style>([\s\S]*?)<\/style>/)?.[1];
  assert.ok(css?.includes('.analytics-b0-card'));
  function renderCard(component, toolName, block) {
    const wire = JSON.stringify(block);
    const frozenOwner = JSON.parse(wire);
    const html = renderToStaticMarkup(React.createElement(component, { block: frozenOwner,
      callId: frozenOwner.callId, toolName,
      openFile: () => assert.fail('Component tried to open a file'),
      loadImage: () => assert.fail('Component tried to load a private image') }));
    assert.equal(JSON.stringify(frozenOwner), wire, 'Renderer mutated owner evidence');
    return html;
  }
  return { css, client_sha256: createHash('sha256').update(code).digest('hex'), registrations,
    render(block) { return renderCard(b0Card.component, TOOL_NAME, block); },
    renderQuery(block) { return renderCard(queryCard.component, QUERY_TOOL_NAME, block); },
    renderFirstPurchase(block) { return renderCard(firstPurchaseCard.component, FIRST_PURCHASE_TOOL_NAME, block); } };
}
