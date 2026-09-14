/** Pure grid math. Only the selected box changes; neighbours are never auto-pushed. */
import { COMPONENT_CATALOG, componentDefinition, parseComponentLayout } from './component-catalog.mjs';
export const GRID = COMPONENT_CATALOG.grid;

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
export const sameBox = (a, b) => ['x', 'y', 'w', 'h'].every(key => a[key] === b[key]);
export const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

export function gridMetrics(width) {
  const { columns, row_height_px: row_height, gap_px: gap } = COMPONENT_CATALOG.grid;
  if (!Number.isFinite(width) || width <= gap * (columns - 1)) throw new Error('画布尺寸不可用');
  return { column: (width - gap * (columns - 1)) / columns, columnPitch: (width + gap) / columns,
    row: row_height, rowPitch: row_height + gap, gap };
}

export function gestureBox(block, mode, dx, dy, metrics) {
  if (!['move', 'resize'].includes(mode) || ![dx, dy].every(Number.isFinite)
    || ![metrics?.columnPitch, metrics?.rowPitch].every(value => Number.isFinite(value) && value > 0)) throw new Error('布局手势无效');
  const original = block.layout, minimum = componentDefinition(block.kind)?.min_size;
  if (!minimum || !parseComponentLayout(block.kind, original).ok) throw new Error('组件布局不符合目录');
  const columns = Math.round(dx / metrics.columnPitch), rows = Math.round(dy / metrics.rowPitch);
  const { columns: maxColumns, max_rows: maxRows } = COMPONENT_CATALOG.grid;
  return mode === 'move'
    ? { ...original, x: clamp(original.x + columns, 0, maxColumns - original.w), y: clamp(original.y + rows, 0, maxRows - original.h) }
    : { ...original, w: clamp(original.w + columns, minimum.w, maxColumns - original.x), h: clamp(original.h + rows, minimum.h, maxRows - original.y) };
}

export function validatePlacement(blocks, blockId, box) {
  const target = blocks.find(block => block.block_id === blockId);
  if (!target) return { ok: false, message: '目标组件已不存在。' };
  const parsed = parseComponentLayout(target.kind, box);
  if (!parsed.ok) return { ok: false, message: parsed.error.message };
  const collision = blocks.find(block => block.block_id !== blockId && overlaps(block.layout, box));
  if (collision) return { ok: false, message: `与「${collision.title}」重叠，请换一个位置或尺寸。` };
  return { ok: true, value: parsed.value };
}

export function changedLayouts(before, after) {
  return after.blocks.filter(block => {
    const old = before.blocks.find(item => item.block_id === block.block_id);
    return !old || !sameBox(old.layout, block.layout);
  }).map(block => ({ block_id: block.block_id, layout: { ...block.layout } }));
}
