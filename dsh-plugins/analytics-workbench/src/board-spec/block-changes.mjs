/** Strict BlockChanges allowlist for the browser RPC. Server remains SSOT. */

import { LIBRARY_KINDS, componentDefinition } from './component-catalog.mjs';

const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
export const BLOCK_CHANGE_KEYS = Object.freeze(['title', 'props', 'layout', 'kind', 'source_result_id']);
export const BOARD_KINDS = LIBRARY_KINDS;
const KIND_SET = new Set(BOARD_KINDS);
const identity = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
const title = value => typeof value === 'string' && value.trim().length > 0 && value.length <= 160;

export function catalogComponent(kind) {
  return componentDefinition(kind);
}

export function describeBlockPatch(block, { factsByResultId } = {}) {
  const def = catalogComponent(block?.kind);
  if (!def) {
    return { supported: false, reason: 'unknown-kind', kind: block?.kind ?? null };
  }
  const propKeys = Object.keys(def.properties ?? {});
  const factIds = factsByResultId && typeof factsByResultId === 'object' && !Array.isArray(factsByResultId)
    ? Object.keys(factsByResultId)
    : [];
  return {
    supported: true,
    kind: def.kind,
    title: true,
    props: propKeys,
    source_result_id: def.requires_result === true,
    source_result_options: def.requires_result === true ? factIds : [],
    layout: 'use-layout-preview',
    requires_result: def.requires_result === true,
  };
}

export function validateBlockChanges(changes, { block, factsByResultId } = {}) {
  if (!record(changes)) {
    return { ok: false, code: 'INVALID_REQUEST', message: 'changes 必须是对象' };
  }
  const keys = Object.keys(changes);
  if (!keys.length) return { ok: false, code: 'INVALID_REQUEST', message: 'changes 不能为空' };
  for (const key of keys) {
    if (!BLOCK_CHANGE_KEYS.includes(key)) {
      return { ok: false, code: 'INVALID_REQUEST', message: `changes 含未知字段 ${key}` };
    }
    if (changes[key] == null) {
      return { ok: false, code: 'INVALID_REQUEST', message: 'changes 字段必须是明确非空修改' };
    }
  }
  if (Object.hasOwn(changes, 'title') && !title(changes.title)) {
    return { ok: false, code: 'INVALID_REQUEST', message: 'title 不合法' };
  }
  if (Object.hasOwn(changes, 'kind') && !KIND_SET.has(changes.kind)) {
    return { ok: false, code: 'INVALID_REQUEST', message: 'kind 不在组件目录中' };
  }
  if (Object.hasOwn(changes, 'source_result_id')) {
    if (!identity(changes.source_result_id)) {
      return { ok: false, code: 'INVALID_REQUEST', message: 'source_result_id 不合法' };
    }
    const factIds = factsByResultId && typeof factsByResultId === 'object' && !Array.isArray(factsByResultId)
      ? Object.keys(factsByResultId)
      : [];
    if (factIds.length && !factIds.includes(changes.source_result_id)) {
      return { ok: false, code: 'INVALID_REQUEST', message: 'source_result_id 不在当前可用结果中' };
    }
  }
  if (Object.hasOwn(changes, 'layout')) {
    return { ok: false, code: 'INVALID_REQUEST', message: '布局请使用 layout_preview，不要混入 PATCH changes.layout' };
  }
  if (Object.hasOwn(changes, 'props')) {
    if (!record(changes.props) || Array.isArray(changes.props)) {
      return { ok: false, code: 'INVALID_REQUEST', message: 'props 必须是对象' };
    }
    const kind = changes.kind ?? block?.kind;
    const def = catalogComponent(kind);
    if (!def) return { ok: false, code: 'INVALID_REQUEST', message: '无法校验 props：缺少合法 kind' };
    const allowed = new Set(Object.keys(def.properties ?? {}));
    for (const key of Object.keys(changes.props)) {
      if (key === 'metric_ref') {
        return { ok: false, code: 'INVALID_REQUEST', message: 'metric_ref 不是 board-spec 字段；请改 source_result_id' };
      }
      if (!allowed.has(key)) {
        return { ok: false, code: 'INVALID_REQUEST', message: `props.${key} 不是该组件的可编辑字段` };
      }
    }
  }
  return { ok: true, changes };
}
