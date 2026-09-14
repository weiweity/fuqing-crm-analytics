import test from 'node:test';
import assert from 'node:assert/strict';
import { COMPONENT_CATALOG, LIBRARY_KINDS, componentDefinition, parseComponentProps, mergeComponentProps, parseComponentLayout } from './component-catalog.mjs';
import { parseBoardSpec, parsePatchBlock, applyPatch } from './schema.mjs';
import { interpretBoard } from './interpret.mjs';

const version = COMPONENT_CATALOG.library_version;
const block = (kind, index = 0) => ({ block_id: `b${index}`, kind, title: kind, library_version: version,
  layout: { x: 0, y: index * 10, ...componentDefinition(kind).default_size },
  ...(componentDefinition(kind).allows_result === false ? {} : { source_result_id: `result${index}` }), props: {} });
const board = () => ({ board_id: 'catalog-contract', version: 1, blocks: LIBRARY_KINDS.map(block) });

test('core six retain Figma mappings; expansion status is explicit, with valid defaults and bounded layouts', () => {
  assert.deepEqual(LIBRARY_KINDS, ['METRIC', 'LINE', 'BAR', 'TABLE', 'TEXT', 'EVIDENCE', 'PROCESS', 'TIMELINE', 'WATERFALL', 'FUNNEL']);
  assert.equal(new Set(COMPONENT_CATALOG.components.map(c => c.figma_node_id)).size, LIBRARY_KINDS.length);
  for (const kind of LIBRARY_KINDS) {
    const definition = componentDefinition(kind);
    assert.match(definition.figma_node_id, /^\d+:\d+$/);
    if (['PROCESS', 'TIMELINE', 'WATERFALL', 'FUNNEL'].includes(kind)) assert.equal(definition.design_status, 'PARTIAL');
    assert.equal(definition.version, 1);
    const props = parseComponentProps(kind, {}, { defaults: true });
    assert.equal(props.ok, true, kind);
    assert.equal(parseComponentProps(kind, props.value).ok, true, kind);
    assert.equal(parseComponentLayout(kind, block(kind).layout).ok, true, kind);
  }
  assert.equal(parseBoardSpec(board()).ok, true);
  assert.equal(componentDefinition('FUNNEL').figma_node_id, '297:2');
  assert.throws(() => { COMPONENT_CATALOG.grid.columns = 99; }, TypeError);
});

test('unsupported components and unregistered styling, facts, query and script properties are explicit errors', () => {
  assert.equal(parseComponentProps('CUSTOM_SCRIPT', {}).error.code, 'COMPONENT_UNSUPPORTED');
  for (const kind of LIBRARY_KINDS) {
    for (const key of ['color', 'fontFamily', 'style', 'html', 'script', 'value', 'source_result_id', 'filters', 'date_range', '__proto__']) {
      const props = JSON.parse(`{"${key}":"untrusted"}`);
      assert.equal(parseComponentProps(kind, props).error.code, 'COMPONENT_PROPERTY', `${kind}.${key}`);
    }
  }
  for (const props of [null, [], 'text', Object.create({ tone: 'accent' })]) {
    assert.equal(parseComponentProps('METRIC', props).error.code, 'COMPONENT_PROPS');
  }
});

test('property types, lengths, enum values and table field constraints are enforced', () => {
  const invalid = [
    ['METRIC', { show_comparison: 1 }], ['METRIC', { tone: 'blue' }],
    ['LINE', { show_points: 'false' }], ['LINE', { line_style: 'gradient' }],
    ['BAR', { orientation: 'diagonal' }], ['TEXT', { content: 'x'.repeat(4001) }],
    ['TEXT', { subtitle: 'x'.repeat(241) }], ['EVIDENCE', { summary: 'x'.repeat(1001) }],
    ['TABLE', { page_size: 4 }], ['TABLE', { page_size: 101 }], ['TABLE', { page_size: 5.5 }],
    ['TABLE', { columns: ['amount', 'amount'] }], ['TABLE', { columns: [''] }],
    ['TABLE', { columns: Array(1) }], ['TABLE', { columns: [null] }],
    ['TABLE', { columns: Array.from({ length: 13 }, (_, i) => `c${i}`) }],
  ];
  for (const [kind, props] of invalid) assert.equal(parseComponentProps(kind, props).error.code, 'COMPONENT_VALUE');
  assert.equal(parseComponentProps('TEXT', { content: 'x'.repeat(4000), align: 'center' }).ok, true);
  assert.equal(parseComponentProps('TEXT', { content: '🌱'.repeat(4000) }).ok, true, 'JSON Schema lengths count Unicode code points');
  assert.equal(parseComponentProps('TEXT', { content: '🌱'.repeat(4001) }).ok, false);
  assert.equal(parseComponentProps('TABLE', { page_size: 100, columns: ['amount', 'period'] }).ok, true);
});

test('defaults and merges return independent values without mutating inputs or global definitions', () => {
  const defaults = parseComponentProps('TABLE', {}, { defaults: true }).value;
  defaults.columns.push('amount');
  assert.deepEqual(parseComponentProps('TABLE', {}, { defaults: true }).value.columns, []);
  const original = { columns: ['amount'], density: 'compact' };
  const patch = { columns: ['period'] };
  const merged = mergeComponentProps('TABLE', original, patch).value;
  merged.columns.push('label');
  assert.deepEqual(original, { columns: ['amount'], density: 'compact' });
  assert.deepEqual(patch, { columns: ['period'] });
});

test('new library layouts reject negative, fractional, unknown, oversize and undersize dimensions', () => {
  for (const kind of LIBRARY_KINDS) {
    const good = block(kind).layout;
    for (const bad of [null, [], { ...good, x: -1 }, { ...good, y: -1 }, { ...good, w: 1 },
      { ...good, h: 1 }, { ...good, w: 12.5 }, { ...good, x: 12 }, { ...good, y: 2000 },
      { ...good, z: 2 }, { ...good, x: Infinity }]) {
      assert.equal(parseComponentLayout(kind, bad).error.code, 'COMPONENT_LAYOUT', kind);
    }
    assert.equal(parseComponentLayout(kind, { ...good, x: 12 - good.w, y: 2000 - good.h }).ok, true);
  }
});

test('registered targeted property edits preserve other blocks, data binding and the original snapshot', () => {
  const edits = [{ show_comparison: false }, { line_style: 'dashed' }, { orientation: 'vertical' },
    { columns: ['period'], page_size: 5 }, { content: '需要关注复购质量', text_style: 'callout' }, { expanded: false },
    { show_owners: false }, { show_details: false }, { show_values: false }, { rate_basis: 'first' }];
  LIBRARY_KINDS.forEach((kind, index) => {
    const initial = board();
    const frozen = structuredClone(initial);
    const changed = applyPatch(initial, { op: 'set_props', block_id: `b${index}`, base_version: 1, props: edits[index] });
    assert.equal(changed.ok, true, kind);
    assert.equal(changed.value.version, 2);
    assert.deepEqual(initial, frozen);
    changed.value.blocks.forEach((item, i) => {
      assert.deepEqual(item, i === index ? { ...initial.blocks[i], props: edits[index] } : initial.blocks[i]);
    });
  });
});

test('style edits reject stale versions, missing target, cross-kind properties and new data bindings', () => {
  const initial = board();
  const patch = { op: 'set_props', block_id: 'b0', base_version: 1, props: { show_comparison: false } };
  assert.equal(applyPatch(initial, { ...patch, base_version: 2 }).error.code, 'PATCH_VERSION_CONFLICT');
  assert.equal(applyPatch(initial, { ...patch, block_id: 'absent' }).error.code, 'PATCH_BLOCK_MISSING');
  assert.equal(applyPatch(initial, { ...patch, props: { line_style: 'dashed' } }).error.code, 'COMPONENT_PROPERTY');
  assert.equal(applyPatch(initial, { ...patch, props: { source_result_id: 'other' } }).error.code, 'COMPONENT_PROPERTY');
  assert.equal(parseBoardSpec({ ...initial, blocks: [{ ...initial.blocks[0], library_version: 'future/v2' }] }).error.code, 'COMPONENT_VERSION');
  const layoutPatch = Object.freeze({ op: 'set_layout', block_id: 'b0', base_version: 1, layout: Object.freeze({ x: 0, y: 0, w: 4, h: 4 }) });
  assert.equal(parsePatchBlock(layoutPatch).ok, true);
  assert.equal(applyPatch(initial, layoutPatch).ok, true);
});

test('text is editable plain content without fabricated numeric facts; legacy boards remain readable', () => {
  const text = { ...block('TEXT'), props: { content: '<script>alert(1)</script>\n备注', align: 'center' } };
  delete text.source_result_id;
  const result = interpretBoard({ board_id: 'text', version: 1, blocks: [text] });
  assert.equal(result.value.blocks[0].paint.content, text.props.content);
  assert.equal(result.value.blocks[0].bind, 'unbound');
  assert.equal(result.value.blocks[0].paint.headline, undefined);
  assert.equal(parseBoardSpec({ board_id: 'legacy', version: 1, blocks: [{ block_id: 'b', kind: 'METRIC', layout: { x: 0, y: 0, w: 1, h: 1 } }] }).ok, true);
});
