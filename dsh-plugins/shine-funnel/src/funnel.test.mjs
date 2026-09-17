import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { funnelGeometry } from './funnel.mjs';
import { parseComponentProps } from '../../analytics-workbench/src/board-spec/component-catalog.mjs';
import { projectComponent } from '../../analytics-workbench/src/board-spec/component-view.mjs';

const content = counts => ({ unit: '人', cohort_label: '合成同一人群', counting_rule: '至少1/2/3笔有效订单',
  stages: counts.map((count, index) => ({ label: `阶段${index + 1}`, count })) });
const cases = JSON.parse(readFileSync(new URL('../tests/funnel-cases.json', import.meta.url)));
for (const sample of cases) test(`funnel shared contract: ${sample.name}`, () => {
  const input = content(sample.counts), before = structuredClone(input), geometry = funnelGeometry(input);
  assert.equal(!!geometry, sample.valid);
  assert.deepEqual(input, before);
  if (geometry) {
    assert.ok(geometry.stages.every(stage => Number.isFinite(stage.width) && stage.width >= 0 && stage.width <= 100));
    assert.equal(geometry.stages[0].previous_ratio, null);
  }
});

test('zero denominators are unavailable and rates are raw ratios, with no minimum fake bar width', () => {
  assert.deepEqual(funnelGeometry(content([10, 5, 0])).stages.map(s => s.previous_ratio), [null, .5, 0]);
  assert.deepEqual(funnelGeometry(content([10, 5, 0])).stages.map(s => s.first_ratio), [1, .5, 0]);
  assert.deepEqual(funnelGeometry(content([0, 0, 0])).stages.map(s => s.first_ratio), [null, null, null]);
  assert.deepEqual(funnelGeometry(content([10, 0, 0])).stages.map(s => s.previous_ratio), [null, 0, null]);
  assert.equal(funnelGeometry(content([10, 0, 0])).stages[1].width, 0);
});

test('unregistered facts, units, missing/duplicate labels and scripts cannot become funnel props', () => {
  for (const mutate of [x => { x.unit = '元'; }, x => { delete x.unit; }, x => { x.stages[0].label = ' '; },
    x => { x.stages[1].label = x.stages[0].label; }, x => { x.stages[1].extra = 0; }, x => { x.cohort_label = ''; },
    x => { x.script = 'alert(1)'; }, x => { x.counting_rule = ''; }, x => { x.stages[0].count = Infinity; }]) {
    const input = content([10, 5, 0]); mutate(input); assert.equal(funnelGeometry(input), null);
  }
  for (const key of ['counts', 'stages', 'unit', 'counting_rule', 'cohort_label', 'script']) {
    assert.equal(parseComponentProps('FUNNEL', { [key]: [] }).ok, false);
  }
  assert.equal(projectComponent({ kind: 'FUNNEL', props: {}, source_result_id: 'r1' },
    { schema_version: 'board-component-facts/v1', scalar: { value: 100, unit: '元' } }).code, 'COMPONENT_DATA');
});
