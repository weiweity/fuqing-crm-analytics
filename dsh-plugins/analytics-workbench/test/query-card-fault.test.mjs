import test from 'node:test';
import assert from 'node:assert/strict';
import { access } from 'node:fs/promises';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { QUERY_FAULT_COPY, classifyQueryToolBlock, textLeaksQueryFacts } from '../src/query-fault.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const cardSource = await readFile(join(here, '../src/client/query-card.tsx'), 'utf8');

const queryCall = { callId: 'query-fault-call', name: 'analytics_channel_followup_query', argsRaw: '{}', turn: 1, step: 1, time: 0, subCalls: [] };
const unknownBlock = {
  kind: 'tool-result', seq: 2, time: 1, callId: queryCall.callId,
  call: { name: queryCall.name, argsRaw: queryCall.argsRaw }, callTime: 0, content: [], isError: false, subCalls: [],
  meta: { schema_version: 'future/v999', run_id: 'run_1', result: { facts: { observation_days: 30, totals: { channel_repeat_count: 99 } } } },
};
const extraBlock = { ...unknownBlock, meta: { schema_version: 'analytics-run-channel-followup-native-receipt/v1', html: '<img src=x onerror=bad()>' } };
const errorBlock = { ...unknownBlock, isError: true, meta: undefined, content: [{ type: 'text', text: 'N=30 1100.00 元 SENSITIVE' }] };

test('query-card source keeps existing fault copy and stamps data-query-fault', () => {
  assert.match(cardSource, /data-query-fault="running"/);
  assert.match(cardSource, /data-query-fault="tool-error"/);
  assert.match(cardSource, /data-query-fault=\{queryFaultKind\(block\)\}/);
  assert.match(cardSource, /data-query-fault="malformed"/);
  assert.match(cardSource, /data-query-fault="ok"/);
  assert.match(cardSource, /合成查询运行中…/);
  assert.match(cardSource, /data-testid="analytics-query-cancel"/);
  assert.match(cardSource, /停止查询/);
  assert.match(cardSource, /\/api\/session\/cancel/);
  assert.match(cardSource, /classifyCancelOutcome/);
  assert.match(cardSource, /data-cancel-state/);
  assert.match(cardSource, /查询工具失败；没有可用结果。未执行业务动作。/);
  assert.match(cardSource, /查询结果格式无法识别或版本不支持；不推断分析成功。/);
  assert.match(cardSource, /QUERY_RECEIPT_SCHEMA/);
});

test('unknown version, extra fields, and tool errors classify without leaking channel facts', () => {
  const unknown = classifyQueryToolBlock(unknownBlock);
  const extra = classifyQueryToolBlock(extraBlock);
  const failed = classifyQueryToolBlock(errorBlock);
  const running = classifyQueryToolBlock(queryCall);
  assert.equal(unknown.kind, 'unknown-version');
  assert.equal(extra.kind, 'malformed');
  assert.equal(failed.kind, 'tool-error');
  assert.equal(running.kind, 'running');
  for (const row of [unknown, extra, failed, running]) {
    assert.equal(textLeaksQueryFacts(row.copy), false);
    assert.ok(Object.values(QUERY_FAULT_COPY).includes(row.copy));
  }
});

test('compiled query fault cards hide channel digits when lib/client.js is present', async (t) => {
  const lib = join(here, '../lib/client.js');
  try { await access(lib); } catch { t.skip('compiled client not built'); return; }
  const { loadCardHarness } = await import('./tool-card-harness.mjs');
  const harness = await loadCardHarness();
  for (const [id, block, expected, fault] of [
    ['unknown', unknownBlock, '版本不支持', 'unknown-version'],
    ['extra', extraBlock, '无法识别', 'malformed'],
    ['error', errorBlock, '查询工具失败', 'tool-error'],
    ['running', queryCall, '合成查询运行中', 'running'],
  ]) {
    const html = harness.renderQuery(block);
    assert.ok(html.includes(expected), id);
    assert.ok(html.includes(`data-query-fault="${fault}"`), id);
    assert.equal(html.includes('data-testid="analytics-query-tool-result"'), false, id);
    assert.equal(html.includes('data-testid="analytics-query-cancel"'), id === 'running');
    assert.doesNotMatch(html, /N=30|1100\.00 元|result_ref|25%|SENSITIVE|onerror=/i);
  }
});
