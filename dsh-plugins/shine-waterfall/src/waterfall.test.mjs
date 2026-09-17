import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { waterfallGeometry } from './waterfall.mjs';
import { projectComponent } from '../../analytics-workbench/src/board-spec/component-view.mjs';
import { parseComponentProps } from '../../analytics-workbench/src/board-spec/component-catalog.mjs';

const cases = JSON.parse(readFileSync(new URL('../tests/waterfall-cases.json', import.meta.url)));
for (const item of cases) test(`waterfall shared geometry contract: ${item.name}`, () => {
  const before = structuredClone(item.data), geometry = waterfallGeometry(item.data);
  assert.equal(Boolean(geometry), item.valid);
  assert.deepEqual(item.data, before);
  const view = projectComponent({ kind: 'WATERFALL', source_result_id: 'r', props: {} }, {
    schema_version: 'board-component-facts/v1', waterfall: item.data });
  assert.equal(view.status, item.valid ? 'ready' : 'error');
  if (!geometry) return;
  assert.equal(geometry.bars.length, item.data.contributions.length + 2);
  assert.ok(geometry.min <= 0 && geometry.max >= 0);
  geometry.bars.forEach((bar, index) => {
    assert.ok(Number.isFinite(bar.top) && Number.isFinite(bar.bottom) && bar.top <= bar.bottom);
    assert.ok(bar.top >= 40 && bar.bottom <= 240);
    if (bar.role === 'delta') {
      assert.equal(bar.from, geometry.bars[index - 1].to);
      assert.equal(bar.to, bar.from + bar.value);
      if (!bar.value) assert.equal(bar.top, bar.bottom, 'zero never inflated for visibility');
    } else assert.equal(bar.from, 0, 'totals anchor to zero, including negative starts');
  });
});

test('large contribution list remains complete, scrollable and geometrically proportional', () => {
  const data = { unit: '个', start: { label: '起点', value: 0 }, end: { label: '终点', value: 200 },
    contributions: Array.from({ length: 200 }, (_, i) => ({ label: `渠道${i}`, value: 1 })) };
  const geometry = waterfallGeometry(data);
  assert.equal(geometry.bars.length, 202);
  assert.ok(geometry.width > 19000);
  assert.ok(Math.abs(geometry.bars[1].bottom - geometry.bars[1].top - 1) < 1e-8);
  data.contributions.push({ label: '不能截断', value: 0 });
  assert.equal(waterfallGeometry(data), null);
});

test('AI changes display only, not contributions, data units or executable content', () => {
  assert.equal(parseComponentProps('WATERFALL', { show_values: false, show_table: false }).ok, true);
  for (const props of [{ contributions: [] }, { unit: '元' }, { start: 100 }, { script: 'x' }, { show_values: 1 }]) {
    assert.equal(parseComponentProps('WATERFALL', props).ok, false);
  }
  assert.equal(projectComponent({ kind: 'WATERFALL', props: {} }, null).status, 'empty');
  assert.equal(projectComponent({ kind: 'WATERFALL', source_result_id: 'r', props: {} }, {
    current_gsv: 100, comparison_gsv: 80 }).status, 'error', 'legacy two-period totals are not a waterfall');
});
