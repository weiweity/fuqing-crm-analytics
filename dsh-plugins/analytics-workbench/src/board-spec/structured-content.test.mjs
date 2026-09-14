import test from 'node:test';
import assert from 'node:assert/strict';
import cases from '../../tests/structured-component-cases.json' with { type: 'json' };
import { parseComponentProps } from './component-catalog.mjs';
import { projectComponent } from './component-view.mjs';
import { processGeometry, timelineGeometry } from './structured-content.mjs';
import { parseBoardSpec } from './schema.mjs';

for (const c of cases) test(`structured contract: ${c.name}`, () => {
  assert.equal(parseComponentProps(c.kind, c.props, { defaults: true }).ok, c.valid);
});
test('timeline has proportional days, stable same-day grouping and collision-free marker lanes', () => {
  const events = [
    { id: 'last', date: '2026-01-11', label: '末日' },
    { id: 'a', date: '2026-01-01', label: '开始' },
    { id: 'b', date: '2026-01-02', label: '第二天' },
    { id: 'c', date: '2026-01-02', label: '同日事件' },
  ];
  const before = structuredClone(events), data = timelineGeometry(events);
  assert.deepEqual(data.groups.map(g => g.position), [0, .1, 1]);
  assert.deepEqual(data.groups[1].events.map(e => e.id), ['b', 'c']);
  assert.deepEqual(events, before);
  const clustered = timelineGeometry([...events, { id: 'far', date: '2028-01-01', label: '远期' }]);
  for (const a of clustered.groups) for (const b of clustered.groups) {
    if (a !== b && a.lane === b.lane) assert.ok(Math.abs(a.position - b.position) >= .085);
  }
  assert.equal(timelineGeometry([events[0]]).groups[0].position, .5);
});

test('directed process graph preserves branch, return, self-loop and disconnected nodes without crossing node boxes', () => {
  const content = {
    nodes: ['a', 'b', 'c', 'd'].map(id => ({ id, label: id })),
    edges: [{ from: 'a', to: 'b' }, { from: 'a', to: 'c' }, { from: 'c', to: 'a' }, { from: 'b', to: 'b' }],
  };
  const original = structuredClone(content), graph = processGeometry(content);
  assert.deepEqual(content, original);
  assert.equal(graph.nodes.length, 4); assert.equal(graph.edges.length, 4);
  assert.deepEqual(graph.edges.map(({ from, to }) => ({ from, to })), content.edges);
  assert.equal(graph.edges[0].side, 'left'); assert.equal(graph.edges[2].side, 'right');
  assert.notEqual(graph.edges[0].lane, graph.edges[1].lane, 'overlapping intervals cannot share a routing lane');
  for (const edge of graph.edges) {
    assert.ok(edge.x < graph.nodes[0].x || edge.x > graph.nodes[0].x + graph.nodes[0].w);
    assert.ok(edge.x >= 0 && edge.x <= graph.width && edge.y >= 0 && edge.y <= graph.height);
    assert.doesNotMatch(edge.path, /NaN|undefined|Infinity/);
  }
  const dense = { nodes: Array.from({ length: 40 }, (_, i) => ({ id: `n${i}`, label: '长节点'.repeat(40) })),
    edges: Array.from({ length: 100 }, (_, i) => ({ from: `n${i % 40}`, to: `n${(i * 7) % 40}`, label: `条件${i}` })) };
  const max = processGeometry(dense);
  assert.equal(max.edges.length, 100); assert.equal(max.nodes.length, 40);
  assert.deepEqual(processGeometry(dense), max, 'layout is stable, not random or dependent on the browser');
  assert.throws(() => processGeometry({ nodes: [], edges: [{ from: 'missing', to: 'missing' }] }), /不存在/);
});
test('planning diagrams are source-free; missing content is empty and never an invented process', () => {
  for (const kind of ['PROCESS', 'TIMELINE']) {
    assert.equal(projectComponent({ kind, props: {} }, null).status, 'empty');
    assert.equal(projectComponent({ kind, props: {}, source_result_id: 'borrowed-result' }, {}).status, 'error');
    assert.equal(parseBoardSpec({ board_id: 'b', version: 1, blocks: [{ block_id: 'a', kind, title: kind,
      props: {}, source_result_id: 'borrowed-result' }] }).ok, false);
  }
});
test('nested values are bounded, clone-safe and reject prototype-bearing objects', () => {
  const props = { nodes: [{ id: 'a', label: '核对' }], edges: [] };
  const parsed = parseComponentProps('PROCESS', props, { defaults: true });
  parsed.value.nodes[0].label = '修改'; assert.equal(props.nodes[0].label, '核对');
  assert.equal(parseComponentProps('PROCESS', { nodes: [Object.create({ id: 'a', label: 'x' })] }).ok, false);
  assert.equal(parseComponentProps('PROCESS', { nodes: Array.from({ length: 41 }, (_, i) => ({ id: `n${i}`, label: 'x' })) }).ok, false);
});
