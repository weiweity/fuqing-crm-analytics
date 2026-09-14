import test from 'node:test';
import assert from 'node:assert/strict';
import { COMPONENT_CATALOG } from './component-catalog.mjs';
import { gridMetrics, gestureBox, validatePlacement, changedLayouts, sameBox } from './grid-layout.mjs';

const block = (id = 'a', box = { x: 0, y: 0, w: 4, h: 4 }) => ({ block_id: id, title: id, kind: 'TEXT', layout: box });
test('pixel metrics use catalog px fields at multiple fluid canvas widths', () => {
  for (const width of [560, 721, 1000, 1440.5]) {
    const metrics = gridMetrics(width), grid = COMPONENT_CATALOG.grid;
    assert.equal(metrics.row, grid.row_height_px); assert.equal(metrics.gap, grid.gap_px);
    assert.equal(metrics.rowPitch, 56);
    assert.ok(Math.abs(metrics.column * 12 + metrics.gap * 11 - width) < 1e-8);
  }
  for (const width of [NaN, Infinity, -1, 0, 176]) assert.throws(() => gridMetrics(width));
});
test('continuous displacement snaps to any grid position; bounds and kind-specific minimums clamp', () => {
  const metrics = gridMetrics(1000), original = block('a', { x: 2, y: 5, w: 4, h: 4 });
  for (let x = -2; x <= 6; x++) for (let y = -5; y <= 30; y++) {
    const target = gestureBox(original, 'move', x * metrics.columnPitch + 0.1, y * metrics.rowPitch + 0.1, metrics);
    assert.deepEqual(target, { x: x + 2, y: y + 5, w: 4, h: 4 });
  }
  assert.equal(gestureBox(original, 'move', metrics.columnPitch * .49, 0, metrics).x, 2);
  assert.equal(gestureBox(original, 'move', metrics.columnPitch * .51, 0, metrics).x, 3);
  assert.deepEqual(gestureBox(original, 'move', -1e8, 1e8, metrics), { x: 0, y: 1996, w: 4, h: 4 });
  for (const definition of COMPONENT_CATALOG.components) {
    const item = { ...original, kind: definition.kind, layout: { x: 0, y: 0, ...definition.default_size } };
    assert.deepEqual(gestureBox(item, 'resize', -1e8, -1e8, metrics), { x: 0, y: 0, ...definition.min_size });
    assert.deepEqual(gestureBox(item, 'resize', 1e8, 1e8, metrics), { x: 0, y: 0, w: 12, h: 2000 });
  }
  assert.throws(() => gestureBox(original, 'move', 0, 0, { ...metrics, rowPitch: NaN }));
  assert.throws(() => gestureBox(original, 'other', 0, 0, metrics));
  assert.throws(() => gestureBox(original, 'move', Infinity, 0, metrics));
});
test('collisions refuse only the candidate; touching edges is valid; no neighbour is moved', () => {
  const items = [block(), block('b', { x: 6, y: 0, w: 6, h: 4 })], before = structuredClone(items);
  assert.equal(validatePlacement(items, 'a', { x: 2, y: 0, w: 4, h: 4 }).ok, true);
  assert.match(validatePlacement(items, 'a', { x: 3, y: 0, w: 4, h: 4 }).message, /b.*重叠/);
  assert.equal(validatePlacement(items, 'a', { x: 6, y: 4, w: 4, h: 4 }).ok, true);
  assert.equal(validatePlacement(items, 'a', { x: 9, y: 0, w: 4, h: 4 }).ok, false);
  assert.equal(validatePlacement(items, 'missing', items[0].layout).ok, false);
  assert.deepEqual(items, before);
});
test('layout diff includes only changed boxes and copies the values', () => {
  const before = { blocks: [block(), block('b', { x: 6, y: 0, w: 6, h: 4 })] };
  const after = structuredClone(before); after.blocks[0].layout.y = 5;
  const diff = changedLayouts(before, after);
  assert.deepEqual(diff, [{ block_id: 'a', layout: { x: 0, y: 5, w: 4, h: 4 } }]);
  diff[0].layout.y = 100; assert.equal(after.blocks[0].layout.y, 5);
  assert.equal(sameBox(before.blocks[1].layout, after.blocks[1].layout), true);
});
