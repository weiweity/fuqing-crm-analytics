import test from 'node:test';
import assert from 'node:assert/strict';
import { COMPONENT_FACTS_VERSION, projectComponent } from './component-view.mjs';
import { COMPONENT_CATALOG, LIBRARY_KINDS, componentDefinition } from './component-catalog.mjs';
import { interpretBoard } from './interpret.mjs';

function facts() {
  return { schema_version: COMPONENT_FACTS_VERSION,
    scalar: { value: 0, comparison: -5, unit: '万元' },
    funnel: { unit: '人', cohort_label: '合成购买客户', counting_rule: '同一人群至少一笔、两笔、三笔有效订单',
      stages: [{ label: '一笔', count: 10 }, { label: '两笔', count: 5 }, { label: '三笔', count: 0 }] },
    waterfall: { unit: '万元', start: { label: '起点', value: -5 }, end: { label: '终点', value: 0 },
      contributions: [{ label: '核验变化', value: 5 }, { label: '零项', value: 0 }] },
    series: { ordered: true, unit: '万元', points: [{ label: '七月', value: -5 }, { label: '八月', value: null }, { label: '九月', value: 0 }] },
    table: { columns: [{ key: 'period', label: '期间' }, { key: 'value', label: '金额', unit: '万元' }],
      rows: [{ period: '七月', value: -5 }, { period: '八月', value: null }, { period: '九月', value: 0 }] },
    evidence: { source_label: '合成测试结果', items: [{ label: '日期', value: '2026-09-13' }] },
  };
}
const block = kind => ({ kind, source_result_id: 'verified_result', props: kind === 'TEXT' ? { content: '备注' } : {} });

test('registered projections preserve explicit zeros, negatives, null gaps and the declared numeric unit', () => {
  const source = facts(), before = structuredClone(source);
  for (const kind of LIBRARY_KINDS.filter(kind => componentDefinition(kind).allows_result !== false)) {
    assert.equal(projectComponent(block(kind), source).status, 'ready', kind);
  }
  assert.deepEqual(projectComponent(block('METRIC'), source).scalar, source.scalar);
  assert.deepEqual(projectComponent(block('LINE'), source).series.points.map(p => p.value), [-5, null, 0]);
  assert.deepEqual(source, before);
});

test('table presentation edits sort/filter existing fields without coercion or mutating source', () => {
  const source = facts(), before = structuredClone(source);
  const result = projectComponent({ ...block('TABLE'), props: { columns: ['value'], sort_field: 'value', sort_direction: 'desc' } }, source);
  assert.equal(result.status, 'ready');
  assert.deepEqual(result.table.columns.map(c => c.key), ['value']);
  assert.deepEqual(result.table.rows.map(r => r.value), [0, -5, null]);
  assert.deepEqual(source, before);
  for (const props of [{ columns: ['profit'] }, { sort_field: 'profit' }]) {
    assert.equal(projectComponent({ ...block('TABLE'), props }, source).code, 'COMPONENT_DATA');
  }
});

test('empty/missing data is distinct from true zero; category order cannot masquerade as a trend', () => {
  assert.equal(projectComponent(block('METRIC'), null).code, 'RESULT_MISSING');
  assert.equal(projectComponent(block('METRIC'), { ...facts(), scalar: { value: null, unit: '元' } }).status, 'empty');
  assert.equal(projectComponent(block('TABLE'), { ...facts(), table: { ...facts().table, rows: [] } }).status, 'empty');
  assert.equal(projectComponent(block('BAR'), { ...facts(), series: { ...facts().series, points: [] } }).status, 'empty');
  const unordered = { ...facts(), series: { ...facts().series, ordered: false } };
  assert.equal(projectComponent(block('LINE'), unordered).status, 'error');
  assert.equal(projectComponent(block('BAR'), unordered).status, 'ready');
});

test('malformed, excessive, non-finite and unknown-version facts fail without partial rendering', () => {
  const cases = [
    ['METRIC', { ...facts(), scalar: { value: Infinity, unit: '元' } }],
    ['METRIC', { ...facts(), scalar: { value: '123', unit: '元' } }],
    ['METRIC', { ...facts(), scalar: { value: 123 } }],
    ['LINE', { ...facts(), series: { ...facts().series, points: [{ label: 'A', value: 1 }, { label: 'A', value: 2 }] } }],
    ['LINE', { ...facts(), series: { ...facts().series, points: Array.from({ length: 367 }, (_, i) => ({ label: `${i}`, value: i })) } }],
    ['TABLE', { ...facts(), table: { ...facts().table, rows: [{ period: '七月' }] } }],
    ['TABLE', { ...facts(), table: { ...facts().table, rows: [{ period: '七月', value: NaN }] } }],
    ['TABLE', { ...facts(), table: { ...facts().table, rows: [{ period: '七月', value: 1, invented: 2 }] } }],
    ['TABLE', { ...facts(), table: { columns: [{ key: '__proto__', label: 'bad' }], rows: [] } }],
    ['EVIDENCE', { ...facts(), evidence: { source_label: '', items: [] } }],
    ['METRIC', { ...facts(), schema_version: 'future/v2', current_gsv: 123, comparison_gsv: 100 }],
  ];
  for (const [kind, source] of cases) {
    const result = projectComponent(block(kind), source);
    assert.equal(result.code, 'COMPONENT_DATA', kind);
    assert.equal(result.scalar, undefined);
    assert.equal(result.series, undefined);
    assert.equal(result.table, undefined);
  }
});

test('legacy GSV migration does not invent a money unit or multiply an old ratio', () => {
  const result = projectComponent(block('METRIC'), { current_gsv: 0.125, comparison_gsv: 0.1 });
  assert.deepEqual(result.scalar, { value: 0.125, comparison: 0.1, unit: null });
  assert.equal(projectComponent(block('LINE'), { current_gsv: 125, comparison_gsv: 100 }).status, 'error');
});

test('LINE uses explicit daily facts while BAR preserves comparisons and refuses malformed daily fallback', () => {
  const source = facts();
  source.series.ordered = false;
  source.time_series = { ordered: true, unit: null, points: Array.from({ length: 366 }, (_, i) => ({ label: `${i}`, value: i === 365 ? null : 0 })) };
  assert.equal(projectComponent(block('LINE'), source).series.points.length, 366);
  assert.deepEqual(projectComponent(block('BAR'), source).series, source.series);
  source.time_series = null;
  assert.equal(projectComponent(block('LINE'), source).status, 'error');
});

test('current BoardSpec interpretation invokes library projection and ignores inherited result IDs', () => {
  const b = { ...block('METRIC'), block_id: 'metric', library_version: COMPONENT_CATALOG.library_version,
    layout: { x: 0, y: 0, ...componentDefinition('METRIC').default_size } };
  const board = { board_id: 'test', version: 1, blocks: [b] };
  assert.equal(interpretBoard(board, { verified_result: facts() }).value.blocks[0].library.scalar.value, 0);
  assert.equal(interpretBoard(board, Object.create({ verified_result: facts() })).value.blocks[0].library.code, 'RESULT_MISSING');
});
