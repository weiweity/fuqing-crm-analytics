/** UI-only operation allowlist. The model tool registry never exposes this RPC. */
import { boardServerConfigured, boardServerRequest } from './server-http.mjs';
import { validateBlockChanges } from './block-changes.mjs';

export const BOARD_RPC_CHANNEL = '/shine-mage-board';
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const exact = (value, required, optional = []) => record(value)
  && required.every(key => Object.hasOwn(value, key))
  && Object.keys(value).every(key => [...required, ...optional].includes(key));
const id = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value);
const version = value => Number.isSafeInteger(value) && value >= 1;
const refused = () => ({ ok: false, error: { code: 'INVALID_REQUEST', message: '不支持的看板界面操作。', details: { status: 400 } } });
const page = payload => (!Object.hasOwn(payload, 'limit') || (Number.isSafeInteger(payload.limit) && payload.limit >= 1 && payload.limit <= 100))
  && (!Object.hasOwn(payload, 'offset') || (Number.isSafeInteger(payload.offset) && payload.offset >= 0 && payload.offset <= 1000000));
const pageQuery = payload => `limit=${payload.limit ?? 100}&offset=${payload.offset ?? 0}`;

export async function handleBoardBrowserCall(operation, payload, signal) {
  signal?.throwIfAborted();
  if (operation === 'status' && exact(payload, [])) return { ok: true, value: {
    protocol: 'board-browser/v1', configured: boardServerConfigured(),
  } };
  if (operation === 'list' && exact(payload, [], ['limit', 'offset']) && page(payload)) {
    return boardServerRequest(`/boards?${pageQuery(payload)}`, { signal });
  }
  if (operation === 'get' && exact(payload, ['board_id'], ['version']) && id(payload.board_id)
    && (!Object.hasOwn(payload, 'version') || version(payload.version))) {
    return boardServerRequest(`/boards/${payload.board_id}${payload.version ? `?version=${payload.version}` : ''}`, { signal });
  }
  if (operation === 'history' && exact(payload, ['board_id'], ['limit', 'offset']) && id(payload.board_id) && page(payload)) {
    return boardServerRequest(`/boards/${payload.board_id}/versions?${pageQuery(payload)}`, { signal });
  }
  if (operation === 'preview' && exact(payload, ['preview_id']) && id(payload.preview_id)) {
    return boardServerRequest(`/previews/${payload.preview_id}`, { signal });
  }
  if (operation === 'cancel' && exact(payload, ['preview_id']) && id(payload.preview_id)) {
    return boardServerRequest(`/previews/${payload.preview_id}/cancel`, { method: 'POST', signal });
  }
  if (operation === 'select_edit' && exact(payload, ['board_id', 'base_version', 'block_id'])
    && id(payload.board_id) && version(payload.base_version)
    && typeof payload.block_id === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(payload.block_id)) {
    return boardServerRequest(`/boards/${payload.board_id}/edit-context`, { method: 'POST', signal,
      body: { base_version: payload.base_version, block_id: payload.block_id } });
  }
  if (operation === 'current_edit' && exact(payload, ['board_id']) && id(payload.board_id)) {
    const reply = await boardServerRequest(`/boards/${payload.board_id}/edit-context`, { signal });
    if (!reply.ok) return reply;
    if (exact(reply.value, ['context']) && (reply.value.context === null || record(reply.value.context))) {
      return { ok: true, value: reply.value.context };
    }
    return { ok: false, error: { code: 'INVALID_RESPONSE', message: '组件编辑状态回执不完整。', details: { status: 502 } } };
  }
  if (operation === 'cancel_edit' && exact(payload, ['edit_context_id']) && id(payload.edit_context_id)) {
    return boardServerRequest(`/edit-contexts/${payload.edit_context_id}/cancel`, { method: 'POST', signal });
  }
  if (operation === 'confirm' && exact(payload, ['preview_id', 'key']) && id(payload.preview_id)
    && typeof payload.key === 'string' && /^[!-~]{1,200}$/.test(payload.key)) {
    return boardServerRequest(`/previews/${payload.preview_id}/confirm`, { method: 'POST', key: payload.key, signal });
  }
  if (operation === 'layout_preview' && exact(payload, ['board_id', 'base_version', 'layouts'])
    && id(payload.board_id) && version(payload.base_version) && Array.isArray(payload.layouts)) {
    return boardServerRequest(`/boards/${payload.board_id}/layout-preview`, { method: 'POST', signal,
      body: { base_version: payload.base_version, layouts: payload.layouts } });
  }
  if (operation === 'rollback_preview' && exact(payload, ['board_id', 'base_version', 'to_version'])
    && id(payload.board_id) && version(payload.base_version) && version(payload.to_version)) {
    return boardServerRequest(`/boards/${payload.board_id}/rollback-preview`, { method: 'POST', signal,
      body: { base_version: payload.base_version, to_version: payload.to_version } });
  }
  if (operation === 'patch_preview' && exact(payload, ['board_id', 'base_version', 'block_id', 'changes'])
    && id(payload.board_id) && version(payload.base_version)
    && typeof payload.block_id === 'string' && /^[A-Za-z0-9_.:-]{1,128}$/.test(payload.block_id)) {
    const checked = validateBlockChanges(payload.changes);
    if (!checked.ok) {
      return { ok: false, error: { code: checked.code, message: checked.message, details: { status: 400 } } };
    }
    return boardServerRequest(`/boards/${payload.board_id}/patch-preview`, { method: 'POST', signal,
      body: { base_version: payload.base_version, block_id: payload.block_id, changes: checked.changes } });
  }
  return refused();
}
