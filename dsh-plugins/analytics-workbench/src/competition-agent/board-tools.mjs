/** Native model surface: catalogue and draft only. No confirm/delete/HTTP passthrough. */
import { COMPONENT_CATALOG, LIBRARY_KINDS, isPlainObject, parseComponentProps, parseComponentLayout } from '../board-spec/component-catalog.mjs';
import { catalogKinds } from '../board-spec/waterfall-pack.mjs';
import { overlaps } from '../board-spec/grid-layout.mjs';
import { boardServerRequest } from '../board-spec/server-http.mjs';
import { boardPreview, boardEditContext } from '../board-spec/receipt.mjs';
import { BOARD_CATALOG_TOOL_NAME, BOARD_GENERATE_TOOL_NAME, BOARD_EDIT_CONTEXT_TOOL_NAME, BOARD_EDIT_TOOL_NAME } from './family.mjs';

const identity = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
const SAVED_BOARD_STATUSES = new Set(['complete', 'truncated', 'unavailable', 'unknown']);
function isBoardTitle(title) {
  if (typeof title !== 'string') return false;
  const points = Array.from(title);
  return points.length >= 1 && points.length <= 160 && /\S/.test(title);
}
function savedBoardSummaries(value) {
  if (!Array.isArray(value)) return null;
  const items = [];
  for (const row of value) {
    if (!row || typeof row !== 'object' || Array.isArray(row)) return null;
    const boardId = row.board_id, title = row.title, version = row.version;
    if (!identity(boardId) || !isBoardTitle(title)
      || !Number.isSafeInteger(version) || version < 1) return null;
    items.push({ board_id: boardId, title, version });
  }
  return items;
}
const integer = { type: 'integer', required: true };
const layout = { type: 'object', required: true, additionalProperties: false,
  properties: { x: integer, y: integer, w: integer, h: integer },
  description: '12-column non-overlapping integer grid. Use catalogue min_size/default_size. A block ends at y+h; place the next row at or below that end, accounting for the tallest block. No pixel CSS.' };

// Reuse the same catalogue validators as the canvas. The server still owns
// request validation and result binding; this preflight only explains common
// configuration failures before HTTP and never changes or retries the draft.
function generationError(args) {
  const fail = (code, message) => ({ code, message, details: { phase: 'preflight' } });
  if (!isBoardTitle(args.title) || !Array.isArray(args.blocks) || args.blocks.length < 1 || args.blocks.length > 60) {
    return fail('INVALID_REQUEST', 'title 须为 1–160 字符的非空标题，blocks 须包含 1–60 个组件。');
  }
  const seen = new Set();
  for (const [index, block] of args.blocks.entries()) {
    const at = `blocks[${index}]`;
    if (!isPlainObject(block) || !identity(block.block_id) || !isBoardTitle(block.title)) {
      return fail('INVALID_REQUEST', `${at} 须包含有效的 block_id 和非空标题。`);
    }
    if (seen.has(block.block_id)) return fail('INVALID_REQUEST', `${at}.block_id 重复；请使用唯一标识。`);
    seen.add(block.block_id);
    if (!catalogKinds(LIBRARY_KINDS).includes(block.kind)) return fail('COMPONENT_UNSUPPORTED', `${at}.kind 不在当前组件目录中。`);
    if (block.library_version !== undefined && block.library_version !== COMPONENT_CATALOG.library_version) {
      return fail('COMPONENT_VERSION', `${at}.library_version 须为 ${COMPONENT_CATALOG.library_version}。`);
    }
    const props = parseComponentProps(block.kind, block.props === undefined ? {} : block.props);
    if (!props.ok) return fail(props.error.code, `${at}.props：${props.error.message.slice(0, 240)}。请只按该组件的目录属性修正。`);
    const box = parseComponentLayout(block.kind, block.layout);
    if (!box.ok) return fail(box.error.code, `${at}.layout：${box.error.message}；请核对目录最小尺寸和画布边界。`);
    const collision = args.blocks.slice(0, index).findIndex(other => overlaps(other.layout, block.layout));
    if (collision !== -1) return fail('COMPONENT_OVERLAP', `${at}.layout 与 blocks[${collision}].layout 重叠；按 y+h 核对行末，只修正布局，保留所需组件及来源。`);
  }
  return undefined;
}

export const BOARD_TOOL_PARAMETERS = Object.freeze({
  [BOARD_CATALOG_TOOL_NAME]: {
    offset: { type: 'integer', description: 'Omit for first page; use only the next_offset returned by this tool.' },
  },
  [BOARD_GENERATE_TOOL_NAME]: {
    title: { type: 'string', required: true, description: 'Board title; at most 160 Unicode code points.' },
    blocks: { type: 'array', required: true, items: {
      type: 'object', additionalProperties: false, properties: {
        block_id: { type: 'string', required: true, description: 'Unique stable local block identifier.' },
        title: { type: 'string', required: true },
        kind: { type: 'string', enum: [...catalogKinds(LIBRARY_KINDS)], required: true },
        library_version: { type: 'string', const: COMPONENT_CATALOG.library_version, required: true },
        source_result_id: { type: 'string', description: 'Exact current-session result_id when catalogue requires_result=true; never a run_id. PROCESS/TIMELINE forbid result IDs and are unverified planning content.' },
        props: { type: 'object', additionalProperties: true,
          description: 'Only the selected kind’s registered display properties; no facts, CSS, scripts, SQL or query conditions. See catalogue.' },
        layout,
      },
    }, description: '1–60 registered blocks. Choose component types matching actual result shapes. TEXT/PROCESS/TIMELINE are unverified explanatory/planning content, not evidence.' },
  },
  [BOARD_EDIT_CONTEXT_TOOL_NAME]: {
    edit_context_id: { type: 'string', required: true, description: 'Exact UI-created edit context from the user message. Never invent a target.' },
  },
  [BOARD_EDIT_TOOL_NAME]: {
    edit_context_id: { type: 'string', required: true },
    changes: { type: 'object', required: true, additionalProperties: false, properties: {
      title: { type: 'string' }, kind: { type: 'string', enum: [...catalogKinds(LIBRARY_KINDS)] },
      props: { type: 'object', additionalProperties: true, description: 'Partial registered display properties only. No facts, scripts, CSS or filters.' },
      layout: { type: 'object', additionalProperties: false, properties: layout.properties, description: layout.description },
      source_result_id: { type: 'string', description: 'For a data change, exact matching result from a controlled query in this native session. Reuse existing result for display-only edits.' },
    }, description: 'Only requested changes to the UI-selected component. Other components and the board title cannot be changed. Preview only.' },
  },
});

export async function executeBoardTool(name, args, execution) {
  if (!Object.hasOwn(BOARD_TOOL_PARAMETERS, name)) throw new Error('UNREGISTERED_BOARD_TOOL');
  execution.signal?.throwIfAborted();
  const sessionId = execution.agent?.session?.id;
  if (!identity(sessionId)) return { schema_version: 'board-tool-result/v1', status: 'REFUSED',
    error: { code: 'SESSION_REQUIRED', message: '需要当前原生会话，不接受模型指定的会话。' } };
  if (!args || typeof args !== 'object' || Array.isArray(args)) return { schema_version: 'board-tool-result/v1', status: 'REFUSED',
    error: { code: 'INVALID_REQUEST', message: '看板工具参数必须为对象。' } };
  if (name === BOARD_GENERATE_TOOL_NAME) {
    const error = generationError(args);
    if (error) return { schema_version: 'board-tool-result/v1', status: 'REFUSED', error,
      next_action: '配置未提交到服务端。仅按本次错误与 competition_board_catalog 修正配置后重提一次；仍失败则停止并说明。不得使用 bash、文件、脚本或其他工具排查，不得删除所需组件来绕过校验。' };
  }
  let result, edit;
  const editing = name === BOARD_EDIT_CONTEXT_TOOL_NAME || name === BOARD_EDIT_TOOL_NAME;
  if (editing) {
    if (typeof args.edit_context_id !== 'string' || !/^edit_[a-f0-9]{32}$/.test(args.edit_context_id)) {
      return { schema_version: 'board-tool-result/v1', status: 'REFUSED',
        error: { code: 'SELECTION_REQUIRED', message: '请先在看板点选组件；不能由模型创建编辑目标。' } };
    }
    result = await boardServerRequest(`/edit-contexts/${args.edit_context_id}?session_id=${encodeURIComponent(sessionId)}`, { signal: execution.signal });
    if (!result.ok) return { schema_version: 'board-tool-result/v1', status: 'REFUSED', error: result.error };
    try { edit = boardEditContext(result.value); } catch { /* Validate before supplying context or proposing. */ }
    if (!edit || edit.edit_context_id !== args.edit_context_id || edit.session_id !== sessionId
      || !['OPEN', 'PROPOSED'].includes(edit.status)) return { schema_version: 'board-tool-result/v1', status: 'REFUSED',
      error: { code: 'INVALID_RESPONSE', message: '组件编辑上下文与当前原生会话不一致。' } };
    if (name === BOARD_EDIT_CONTEXT_TOOL_NAME) return { ...edit, catalog: COMPONENT_CATALOG };
    if (edit.status !== 'OPEN') return { schema_version: 'board-tool-result/v1', status: 'REFUSED',
      error: { code: 'EDIT_PROPOSED', message: '已有待确认预览，请用户先应用或取消。' } };
  }
  if (name === BOARD_CATALOG_TOOL_NAME) {
    const offset = args.offset ?? 0;
    if (!Number.isSafeInteger(offset) || offset < 0 || offset > 1000000) throw new Error('INVALID_OFFSET');
    result = await boardServerRequest(`/context?session_id=${encodeURIComponent(sessionId)}&offset=${offset}`, { signal: execution.signal });
  } else if (name === BOARD_EDIT_TOOL_NAME) {
    result = await boardServerRequest(`/edit-contexts/${args.edit_context_id}/propose`, { method: 'POST', signal: execution.signal,
      body: { session_id: sessionId, changes: args.changes } });
  } else {
    result = await boardServerRequest('/previews', { method: 'POST', signal: execution.signal,
      // Copy only model-authored fields. No spread of owner, session, status or facts.
      body: { title: args.title, blocks: args.blocks, session_id: sessionId } });
  }
  execution.signal?.throwIfAborted();
  if (!result.ok) return { schema_version: 'board-tool-result/v1', status: 'REFUSED', error: result.error };
  if (name === BOARD_CATALOG_TOOL_NAME) {
    if (!(result.value?.schema_version === 'board-generation-context/v1' && result.value.session_id === sessionId
      && result.value.catalog?.library_version === COMPONENT_CATALOG.library_version && Array.isArray(result.value.results))) {
      return { schema_version: 'board-tool-result/v1', status: 'REFUSED', error: { code: 'INVALID_RESPONSE', message: '组件目录回执与当前会话不一致。' } };
    }
    const context = { ...result.value };
    if (Object.hasOwn(context, 'saved_boards')) {
      const summaries = savedBoardSummaries(context.saved_boards);
      if (summaries === null) return { schema_version: 'board-tool-result/v1', status: 'REFUSED',
        error: { code: 'INVALID_RESPONSE', message: '已保存看板摘要不符合合同。' } };
      context.saved_boards = summaries;
    }
    if (Object.hasOwn(context, 'saved_boards_status')) {
      if (typeof context.saved_boards_status !== 'string' || !SAVED_BOARD_STATUSES.has(context.saved_boards_status)) {
        context.saved_boards_status = 'unknown';
      } else if (context.saved_boards_status === 'complete' && !Object.hasOwn(context, 'saved_boards')) {
        context.saved_boards_status = 'unknown';
      }
    }
    return context;
  }
  let preview;
  try { preview = boardPreview(result.value); } catch { /* Fail closed on a malformed service receipt. */ }
  if (!preview || preview.status !== 'PENDING' || preview.operation !== (editing ? 'PATCH' : 'GENERATE')
    || !identity(preview.preview_id) || preview.snapshot?.spec?.session_id !== sessionId
    || (edit && (preview.snapshot.spec.board_id !== edit.board_id || preview.base_version !== edit.base_version
      || !preview.snapshot.spec.blocks.some(block => block.block_id === edit.block_id)))) {
    return { schema_version: 'board-tool-result/v1', status: 'REFUSED',
      error: { code: 'INVALID_RESPONSE', message: '草稿回执与当前会话不一致，未确认保存。' } };
  }
  return { schema_version: 'board-tool-result/v1', status: 'PREVIEW_READY',
    operation: preview.operation, ...(edit ? { edit_context_id: edit.edit_context_id, block_id: edit.block_id } : {}),
    session_id: sessionId, preview_id: preview.preview_id, board_id: preview.snapshot.spec.board_id,
    title: preview.snapshot.spec.title, component_count: preview.snapshot.spec.blocks.length,
    expires_at_ms: preview.expires_at_ms, published: false,
    next_action: '在原生对话工具卡中打开预览；用户确认后才保存。' };
}
