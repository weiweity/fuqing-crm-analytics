export function librarySnapshot({ boardId = 'board_test', version = 1, content = '初始说明' } = {}) {
  return { spec: { schema_version: 'board-spec/v1', board_id: boardId, version, title: '合成经营看板', session_id: 'native_session',
    blocks: [{ block_id: 'note', title: '说明', kind: 'TEXT', library_version: 'board-components/v1',
      props: { content }, layout: { x: 0, y: 0, w: 6, h: 5 }, source_result_id: null }] }, facts_by_result_id: {} };
}
export function libraryPreview(snapshot = librarySnapshot(), overrides = {}) {
  return { preview_id: 'preview_test', status: 'PENDING', operation: snapshot.spec.version === 1 ? 'GENERATE' : 'PATCH',
    base_version: snapshot.spec.version - 1, expires_at_ms: Date.now() + 600000, snapshot, ...overrides };
}
export const ok = value => ({ ok: true, value: structuredClone(value) });
export const failed = (code = 'TRANSPORT_ERROR') => ({ ok: false, error: { code, message: `隔离故障：${code}` } });
export const listOf = snapshot => ({ items: [Object.fromEntries(['board_id', 'version', 'title', 'session_id'].map(key => [key, snapshot.spec[key]]))] });
