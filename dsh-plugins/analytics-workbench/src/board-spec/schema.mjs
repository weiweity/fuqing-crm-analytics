import { BOARD_SPEC_KINDS, PATCH_OPS } from './kinds.mjs';

const KIND_SET = new Set(BOARD_SPEC_KINDS);
const PATCH_SET = new Set(PATCH_OPS);

/**
 * @typedef {{ ok: true, value: object } | { ok: false, error: { code: string, message: string } }} SpecResult
 */

function fail(code, message) {
  return { ok: false, error: { code, message } };
}

function isNonEmptyString(v) {
  return typeof v === 'string' && v.trim().length > 0;
}

function isInt(v) {
  return typeof v === 'number' && Number.isInteger(v);
}

/**
 * @param {unknown} raw
 * @returns {SpecResult}
 */
export function parseBoardSpec(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return fail('SPEC_NOT_OBJECT', 'BoardSpec 必须是对象');
  }
  const spec = /** @type {Record<string, unknown>} */ (raw);
  if (!isNonEmptyString(spec.board_id)) return fail('SPEC_BOARD_ID', '缺少 board_id');
  if (!isInt(spec.version) || spec.version < 1) return fail('SPEC_VERSION', 'version 须为 >= 1 的整数');
  if (!Array.isArray(spec.blocks)) return fail('SPEC_BLOCKS', 'blocks 须为数组');

  const ids = new Set();
  for (let i = 0; i < spec.blocks.length; i += 1) {
    const block = spec.blocks[i];
    if (block === null || typeof block !== 'object' || Array.isArray(block)) {
      return fail('SPEC_BLOCK', `blocks[${i}] 须为对象`);
    }
    const b = /** @type {Record<string, unknown>} */ (block);
    if (!isNonEmptyString(b.block_id)) return fail('SPEC_BLOCK_ID', `blocks[${i}] 缺少 block_id`);
    if (ids.has(b.block_id)) return fail('SPEC_BLOCK_DUP', `重复 block_id: ${b.block_id}`);
    ids.add(b.block_id);
    if (!KIND_SET.has(b.kind)) {
      return fail('SPEC_KIND', `非法 kind: ${String(b.kind)}`);
    }
    if (b.kind === 'LINK' && !isNonEmptyString(b.url) && !isNonEmptyString(b.href)) {
      return fail('SPEC_LINK', `LINK 块 ${b.block_id} 需要 url`);
    }
    if (b.layout != null) {
      const layout = parseLayout(b.layout);
      if (!layout.ok) return fail('SPEC_LAYOUT', `blocks[${i}] layout 非法`);
    }
  }
  return { ok: true, value: spec };
}

function parseLayout(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return fail('SPEC_LAYOUT', 'layout 须为 {x,y,w,h}');
  }
  const layout = /** @type {Record<string, unknown>} */ (raw);
  if (!isInt(layout.x) || !isInt(layout.y) || !isInt(layout.w) || !isInt(layout.h)) {
    return fail('SPEC_LAYOUT', 'layout 须为整数 x y w h');
  }
  if (layout.w < 1 || layout.h < 1) return fail('SPEC_LAYOUT', 'layout.w/h 须 >= 1');
  return { ok: true, value: { x: layout.x, y: layout.y, w: layout.w, h: layout.h } };
}

/**
 * @param {unknown} raw
 * @returns {SpecResult}
 */
export function parsePatchBlock(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return fail('PATCH_NOT_OBJECT', 'PATCH_BLOCK 必须是对象');
  }
  const p = /** @type {Record<string, unknown>} */ (raw);
  if (!isNonEmptyString(p.block_id)) return fail('PATCH_BLOCK_ID', '缺少 block_id');
  if (!isInt(p.base_version) || p.base_version < 1) {
    return fail('PATCH_BASE_VERSION', 'base_version 须为 >= 1 的整数');
  }
  if (!PATCH_SET.has(p.op)) return fail('PATCH_OP', `非法 op: ${String(p.op)}`);
  if (p.op === 'set_title' && !isNonEmptyString(p.title)) {
    return fail('PATCH_TITLE', 'set_title 需要 title');
  }
  if (p.op === 'set_kind' && !KIND_SET.has(p.kind)) {
    return fail('PATCH_KIND', `set_kind 非法 kind: ${String(p.kind)}`);
  }
  if (p.op === 'set_metric_ref' && !isNonEmptyString(p.metric_ref)) {
    return fail('PATCH_METRIC', 'set_metric_ref 需要 metric_ref');
  }
  if (p.op === 'set_layout') {
    const layout = parseLayout(p.layout);
    if (!layout.ok) return layout;
    p.layout = layout.value;
  }
  return { ok: true, value: p };
}

/**
 * @param {unknown} raw
 * @returns {SpecResult}
 */
export function parseRollback(raw) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return fail('ROLLBACK_NOT_OBJECT', 'ROLLBACK 必须是对象');
  }
  const r = /** @type {Record<string, unknown>} */ (raw);
  if (!isNonEmptyString(r.board_id)) return fail('ROLLBACK_BOARD_ID', '缺少 board_id');
  if (!isInt(r.to_version) || r.to_version < 1) {
    return fail('ROLLBACK_VERSION', 'to_version 须为 >= 1 的整数');
  }
  return { ok: true, value: r };
}

/**
 * Apply a validated patch onto a validated spec. Does not mutate facts.
 * @param {object} spec
 * @param {object} patch
 * @returns {SpecResult}
 */
export function applyPatch(spec, patch) {
  const parsedSpec = parseBoardSpec(spec);
  if (!parsedSpec.ok) return parsedSpec;
  const parsedPatch = parsePatchBlock(patch);
  if (!parsedPatch.ok) return parsedPatch;
  const board = parsedSpec.value;
  const p = parsedPatch.value;
  if (p.base_version !== board.version) {
    return fail('PATCH_VERSION_CONFLICT', `base_version ${p.base_version} != spec.version ${board.version}`);
  }
  const blocks = Array.isArray(board.blocks) ? board.blocks.map((b) => ({ ...b })) : [];
  const idx = blocks.findIndex((b) => b.block_id === p.block_id);
  if (idx < 0) return fail('PATCH_BLOCK_MISSING', `没有 block_id ${p.block_id}`);
  const next = { ...blocks[idx] };
  if (p.op === 'set_title') next.title = p.title;
  if (p.op === 'set_kind') next.kind = p.kind;
  if (p.op === 'set_metric_ref') next.metric_ref = p.metric_ref;
  if (p.op === 'set_layout' && p.layout && typeof p.layout === 'object') next.layout = p.layout;
  blocks[idx] = next;
  return parseBoardSpec({ ...board, version: board.version + 1, blocks });
}
