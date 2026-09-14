/** Defensive response checks shared by native tools and UI; input authority remains server-side. */
import { parseBoardSpec } from './schema.mjs';
import { COMPONENT_CATALOG, componentDefinition, isPlainObject } from './component-catalog.mjs';

export const boardIdentity = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
const title = value => typeof value === 'string' && value.trim().length > 0 && Array.from(value).length <= 160;
const operations = new Set(['GENERATE', 'PATCH', 'LAYOUT', 'ROLLBACK']);
const invalid = () => new Error('看板响应不符合合同，已保留当前内容。');

export function boardSnapshot(value) {
  const spec = value?.spec;
  if (!isPlainObject(value) || !isPlainObject(spec) || spec.schema_version !== 'board-spec/v1'
    || !boardIdentity(spec.board_id) || !boardIdentity(spec.session_id) || !title(spec.title)
    || !Number.isSafeInteger(spec.version) || !parseBoardSpec(spec).ok
    || spec.blocks.length < 1 || spec.blocks.length > 60 || !isPlainObject(value.facts_by_result_id)) throw invalid();
  for (const [index, block] of spec.blocks.entries()) {
    const definition = componentDefinition(block.kind);
    if (!definition || block.library_version !== COMPONENT_CATALOG.library_version || !boardIdentity(block.block_id)
      || !title(block.title) || !isPlainObject(block.props)) throw invalid();
    if (block.source_result_id != null) {
      if (!boardIdentity(block.source_result_id) || !Object.hasOwn(value.facts_by_result_id, block.source_result_id)
        || !isPlainObject(value.facts_by_result_id[block.source_result_id])) throw invalid();
    } else if (definition.requires_result) throw invalid();
    const a = block.layout;
    for (const other of spec.blocks.slice(0, index)) {
      const b = other.layout;
      if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) throw invalid();
    }
  }
  return value;
}

export function boardPreview(value) {
  if (!isPlainObject(value) || !boardIdentity(value.preview_id)
    || !['PENDING', 'APPLIED', 'CANCELLED'].includes(value.status) || !operations.has(value.operation)
    || !Number.isSafeInteger(value.base_version) || value.base_version < 0
    || !Number.isSafeInteger(value.expires_at_ms) || value.expires_at_ms < 0) throw invalid();
  boardSnapshot(value.snapshot);
  if (value.snapshot.spec.version !== value.base_version + 1
    || (value.operation === 'GENERATE') !== (value.base_version === 0)) throw invalid();
  return value;
}

export function boardEditContext(value) {
  if (!isPlainObject(value) || value.schema_version !== 'board-edit-context/v1'
    || !boardIdentity(value.edit_context_id) || !boardIdentity(value.block_id)
    || !['OPEN', 'PROPOSED', 'CANCELLED', 'APPLIED'].includes(value.status)
    || !Number.isSafeInteger(value.expires_at_ms) || value.expires_at_ms < 0
    || (value.preview_id !== null && !boardIdentity(value.preview_id))
    || value.block?.block_id !== value.block_id) throw invalid();
  boardSnapshot({ spec: { schema_version: 'board-spec/v1', title: '组件编辑上下文',
    board_id: value.board_id, session_id: value.session_id, version: value.base_version, blocks: [value.block] },
    facts_by_result_id: value.facts_by_result_id });
  return value;
}
