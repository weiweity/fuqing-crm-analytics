/** Server-backed canvas state. No service token, local fake save or automatic write retry. */
import { boardSnapshot as snapshot, boardPreview, boardIdentity, boardEditContext } from '../board-spec/receipt.mjs';
import { changedLayouts, validatePlacement } from '../board-spec/grid-layout.mjs';

const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);

export function createLibraryBoardClient(call, { editNative } = {}) {
  const listeners = new Set();
  const lifetime = new AbortController();
  let state = { busy: false, message: '', boards: [], saved: null, preview: null, confirmationUncertain: false, layoutDraft: null, editContext: null, incoming: null, history: [] };
  const emit = patch => {
    if (lifetime.signal.aborted) return;
    if (patch.saved) {
      // A validated saved receipt is sufficient to update its selector entry;
      // a later list/head refresh must not be required to acknowledge the save.
      const { board_id, session_id, title, version } = patch.saved.spec;
      const boards = patch.boards ?? state.boards;
      const index = boards.findIndex(row => row.board_id === board_id);
      const summary = { board_id, session_id, title, version };
      patch = { ...patch, boards: index < 0 ? [...boards, summary]
        : boards.map((row, i) => i === index && row.version <= version ? summary : row) };
    }
    state = { ...state, ...patch };
    for (const listener of listeners) listener();
  };
  async function request(operation, payload) {
    const reply = await call('/shine-mage-board', operation, payload, lifetime.signal);
    lifetime.signal.throwIfAborted();
    if (!reply?.ok) throw new Error(reply?.error?.message || '未取得看板服务回执；当前内容不变。');
    return reply.value;
  }
  async function perform(work) {
    if (state.busy || lifetime.signal.aborted) return;
    emit({ busy: true, message: '' });
    try { await work(); }
    catch (error) { emit({ message: error instanceof Error ? error.message : '看板操作失败，当前内容不变。' }); }
    finally { emit({ busy: false }); }
  }
  async function reloadList() {
    const value = await request('list', {});
    if (!Array.isArray(value?.items) || value.items.some(item => !record(item) || !boardIdentity(item.board_id)
      || !boardIdentity(item.session_id) || typeof item.title !== 'string' || !Number.isSafeInteger(item.version) || item.version < 1)) {
      throw new Error('看板列表响应不合法。');
    }
    // Reconcile only returned rows. An omitted entry may reflect a changed
    // permission or list page; do not resurrect it from the local snapshot.
    const known = new Map(state.boards.map(row => [row.board_id, row]));
    emit({ boards: value.items.map(row => {
      const previous = known.get(row.board_id);
      return previous?.session_id === row.session_id && previous.version > row.version ? previous : row;
    }) });
  }
  async function readBoard(id, minimumVersion = 0) {
    const value = snapshot(await request('get', { board_id: id }));
    if (value.spec.board_id !== id) throw new Error('看板响应目标不一致。');
    if (value.spec.version < minimumVersion) throw new Error('保存状态已应用，但看板回执仍是旧版本；继续保留待核对状态。');
    const listed = state.boards.find(row => row.board_id === id);
    const knownVersion = Math.max(listed?.version ?? 0, state.saved?.spec.board_id === id ? state.saved.spec.version : 0);
    if (knownVersion > value.spec.version) throw new Error('读取到旧版本回执；保留已知较新版本，请刷新核对。');
    emit({ saved: value, preview: null, confirmationUncertain: false, layoutDraft: null, editContext: null, incoming: null, history: [] });
  }
  async function readPreview(id, contextId) {
    const value = boardPreview(await request('preview', { preview_id: id }));
    if (value.preview_id !== id) throw new Error('草稿响应目标不一致。');
    if (value.status === 'APPLIED') return readBoard(value.snapshot.spec.board_id);
    if (value.status === 'CANCELLED') throw new Error('这份草稿已取消，当前看板不变。');
    if (value.expires_at_ms <= Date.now()) throw new Error('这份草稿已过期，请回到对话重新生成。');
    if (contextId && !state.editContext) {
      const edit = boardEditContext(await request('current_edit', { board_id: value.snapshot.spec.board_id }));
      if (edit.edit_context_id !== contextId || edit.preview_id !== id || value.operation !== 'PATCH') throw new Error('工具卡与当前组件编辑不一致，请重新点选。');
      const saved = snapshot(await request('get', { board_id: edit.board_id }));
      if (saved.spec.board_id !== edit.board_id || saved.spec.version !== edit.base_version) throw new Error('看板已有新版本，不能应用旧组件修改。');
      emit({ saved, editContext: edit });
    }
    if (state.editContext) {
      const edit = boardEditContext(await request('current_edit', { board_id: state.editContext.board_id }));
      if (edit.edit_context_id !== state.editContext.edit_context_id || edit.preview_id !== id
        || value.operation !== 'PATCH' || value.base_version !== edit.base_version
        || value.snapshot.spec.board_id !== edit.board_id) throw new Error('预览不是当前选中组件的修改，保留当前编辑。');
      emit({ editContext: edit });
    }
    emit({ preview: value, layoutDraft: null, incoming: null, history: [] });
  }
  async function navigate(intent) {
    if (state.layoutDraft || (state.preview && !(intent.kind === 'preview' && state.preview.preview_id === intent.id))
      || (state.editContext && !(intent.kind === 'preview' && intent.contextId === state.editContext.edit_context_id))) {
      emit({ incoming: intent, message: '有未确认的草稿。请继续检查，或取消当前草稿后切换。' });
      return;
    }
    await (intent.kind === 'preview' ? readPreview(intent.id, intent.contextId) : intent.kind === 'edit' ? selectEdit(intent.id) : readBoard(intent.id));
  }
  async function sendEdit() {
    lifetime.signal.throwIfAborted();
    if (!state.editContext || !editNative) throw new Error('原生会话编辑入口不可用；当前看板未改变。');
    await editNative(state.editContext);
    emit({ message: '已将选中组件交给原生对话，请输入修改要求。返回看板可检查预览或取消编辑。' });
  }
  async function selectEdit(blockId) {
    const saved = state.saved;
    if (!saved || !saved.spec.blocks.some(block => block.block_id === blockId)) throw new Error('请先打开看板并选择其中的组件。');
    const existing = await request('current_edit', { board_id: saved.spec.board_id });
    const context = boardEditContext(existing ?? await request('select_edit', {
      board_id: saved.spec.board_id, base_version: saved.spec.version, block_id: blockId,
    }));
    if (context.board_id !== saved.spec.board_id || context.base_version !== saved.spec.version
      || context.session_id !== saved.spec.session_id || (!existing && context.block_id !== blockId)) throw new Error('编辑上下文与当前看板不一致，请刷新核对。');
    emit({ editContext: context, history: [] });
    if (context.block_id !== blockId) {
      emit({ incoming: { kind: 'edit', id: blockId }, message: '该会话有另一组件的未确认编辑，请先处理，不能静默换目标。' }); return;
    }
    if (context.preview_id) { await readPreview(context.preview_id); return; }
    await sendEdit();
  }
  async function cancelEdit() {
    const id = state.editContext.edit_context_id;
    const cancelled = await request('cancel_edit', { edit_context_id: id });
    if (cancelled?.status !== 'CANCELLED' || cancelled.edit_context_id !== id) throw new Error('未取得取消回执，保留当前组件编辑。');
    emit({ editContext: null, preview: null, confirmationUncertain: false });
  }
  return Object.freeze({
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    dispose() { lifetime.abort(); listeners.clear(); },
    refresh: () => perform(async () => {
      await reloadList();
      if (state.saved && !state.preview && !state.layoutDraft && !state.editContext) await readBoard(state.saved.spec.board_id);
    }),
    openBoard: id => perform(() => navigate({ kind: 'board', id })),
    openPreview: (id, contextId) => perform(() => navigate({ kind: 'preview', id, ...(contextId ? { contextId } : {}) })),
    beginEdit: blockId => perform(() => navigate({ kind: 'edit', id: blockId })),
    resumeEdit: () => perform(sendEdit),
    inspectEdit: () => perform(async () => {
      if (!state.editContext) return;
      const active = state.editContext;
      const value = await request('current_edit', { board_id: active.board_id });
      if (value === null) {
        const saved = snapshot(await request('get', { board_id: active.board_id }));
        if (saved.spec.board_id !== active.board_id || saved.spec.version < active.base_version) throw new Error('编辑状态回执不一致，保留当前内容。');
        emit({ saved, editContext: null, preview: null, confirmationUncertain: false, incoming: null, message: '本次编辑已结束或过期，已读取当前保存版本；如需修改请重新点选。' });
        return;
      }
      const context = boardEditContext(value);
      if (context.edit_context_id !== state.editContext.edit_context_id) throw new Error('编辑上下文已变化，请取消当前编辑后重新点选。');
      if (!context.preview_id) { emit({ message: 'AI 尚未生成可检查的预览，请在原生对话中继续。' }); return; }
      await readPreview(context.preview_id);
    }),
    keepDraft: () => emit({ incoming: null, message: '' }),
    discardAndNavigate: () => perform(async () => {
      const intent = state.incoming;
      if (!intent || (!state.preview && !state.layoutDraft && !state.editContext)) return;
      if (state.editContext) await cancelEdit();
      else if (state.preview) {
        const cancelled = await request('cancel', { preview_id: state.preview.preview_id });
        if (cancelled?.status !== 'CANCELLED' || cancelled.preview_id !== state.preview.preview_id) throw new Error('未取得取消回执，保留当前草稿。');
      }
      emit({ preview: null, layoutDraft: null, confirmationUncertain: false });
      await navigate(intent);
    }),
    cancel: () => perform(async () => {
      if (state.editContext) {
        await cancelEdit(); emit({ incoming: null, message: '已取消组件编辑及其待确认预览；已保存版本不变。' }); return;
      }
      if (state.layoutDraft) {
        emit({ layoutDraft: null, incoming: null, message: '已取消布局调整；已保存版本不变。' });
        return;
      }
      if (!state.preview) return;
      const cancelled = await request('cancel', { preview_id: state.preview.preview_id });
      if (cancelled?.status !== 'CANCELLED' || cancelled.preview_id !== state.preview.preview_id) throw new Error('未取得取消回执，保留当前草稿。');
      emit({ preview: null, incoming: null, confirmationUncertain: false, message: '已取消草稿；已保存看板不变。' });
    }),
    beginLayout() {
      if (state.busy || state.preview || !state.saved || state.layoutDraft || state.editContext) return;
      emit({ layoutDraft: state.saved, history: [], message: '布局编辑中：拖动手柄移动或缩放；方向键也可调整，检查后再确认保存。' });
    },
    updateLayout(blockId, box) {
      if (state.busy || !state.layoutDraft || state.preview) return;
      const placement = validatePlacement(state.layoutDraft.spec.blocks, blockId, box);
      if (!placement.ok) { emit({ message: placement.message }); return; }
      const draft = state.layoutDraft;
      emit({ layoutDraft: { ...draft, spec: { ...draft.spec,
        blocks: draft.spec.blocks.map(block => block.block_id === blockId ? { ...block, layout: placement.value } : block) } },
        message: '布局尚未保存。继续调整，或检查布局后确认。' });
    },
    previewLayout: () => perform(async () => {
      const draft = state.layoutDraft, saved = state.saved;
      if (!draft || !saved || state.preview) return;
      const layouts = changedLayouts(saved.spec, draft.spec);
      if (!layouts.length) { emit({ message: '布局没有变化，无需保存。' }); return; }
      const value = boardPreview(await request('layout_preview', { board_id: saved.spec.board_id, base_version: saved.spec.version, layouts }));
      if (value.status !== 'PENDING' || value.operation !== 'LAYOUT' || value.base_version !== saved.spec.version
        || value.snapshot.spec.board_id !== saved.spec.board_id || value.snapshot.spec.session_id !== saved.spec.session_id) {
        throw new Error('布局预览目标不一致；保留本地调整，未保存。');
      }
      emit({ preview: value, layoutDraft: null, history: [], message: '布局已通过服务端检查；确认后才保存。' });
    }),
    confirm: () => perform(async () => {
      const draft = state.preview;
      if (!draft) return;
      // Until a matching success receipt arrives, failure cannot prove the write did not commit.
      emit({ confirmationUncertain: true });
      const saved = snapshot(await request('confirm', { preview_id: draft.preview_id, key: `board-confirm:${draft.preview_id}` }));
      if (saved.spec.board_id !== draft.snapshot.spec.board_id || saved.spec.version !== draft.snapshot.spec.version) {
        throw new Error('保存回执与预览版本不一致，保留草稿以便核对。');
      }
      const current = state.saved;
      emit({ saved: current?.spec.board_id === saved.spec.board_id && current.spec.version > saved.spec.version ? current : saved,
        preview: null, confirmationUncertain: false, editContext: null, incoming: null, message: '已确认保存。' });
      try { await readBoard(saved.spec.board_id); await reloadList(); emit({ message: '已保存并读取当前版本。' }); }
      catch { emit({ message: '保存已确认，但当前版本刷新失败；保留收到的快照，可稍后刷新核对。' }); }
    }),
    inspectConfirmation: () => perform(async () => {
      const draft = state.preview;
      if (!draft || !state.confirmationUncertain) return;
      const value = boardPreview(await request('preview', { preview_id: draft.preview_id }));
      if (value.preview_id !== draft.preview_id || value.operation !== draft.operation || value.base_version !== draft.base_version
        || value.snapshot.spec.board_id !== draft.snapshot.spec.board_id || value.snapshot.spec.session_id !== draft.snapshot.spec.session_id
        || value.snapshot.spec.version !== draft.snapshot.spec.version) throw new Error('保存状态回执与当前草稿不一致，继续保留待核对状态。');
      if (value.status === 'APPLIED') {
        await readBoard(value.snapshot.spec.board_id, value.snapshot.spec.version);
        emit({ message: '已核对：这份草稿已保存，现显示服务端当前版本。' });
        try { await reloadList(); }
        catch { emit({ message: '已核对：这份草稿已保存，当前快照已读取；看板列表刷新失败，可稍后刷新。' }); }
      } else if (value.status === 'CANCELLED') {
        emit({ preview: null, editContext: null, incoming: null, confirmationUncertain: false,
          message: '已核对：这份草稿已取消。保留当前显示快照，可刷新核对最新版本。' });
      } else {
        // A pending read can race a still-running write: do not label it definitively unsaved.
        emit({ message: '服务端暂未记录应用；保存结果仍待核对。可重试这次保存，或尝试取消尚未应用的草稿。' });
      }
    }),
    loadHistory: () => perform(async () => {
      if (!state.saved) return;
      const value = await request('history', { board_id: state.saved.spec.board_id });
      if (!Array.isArray(value) || value.some(row => !record(row) || !Number.isSafeInteger(row.version) || row.version < 1
        || !['GENERATE', 'PATCH', 'LAYOUT', 'ROLLBACK'].includes(row.operation) || !Number.isSafeInteger(row.created_at_ms))) throw new Error('版本历史响应不合法。');
      emit({ history: value });
    }),
    rollback: toVersion => perform(async () => {
      if (!state.saved || state.preview || state.layoutDraft || state.editContext) return;
      const value = boardPreview(await request('rollback_preview', { board_id: state.saved.spec.board_id,
        base_version: state.saved.spec.version, to_version: toVersion }));
      if (value?.status !== 'PENDING' || value.operation !== 'ROLLBACK') throw new Error('未取得回退预览，当前内容不变。');
      if (value.snapshot.spec.board_id !== state.saved.spec.board_id || value.base_version !== state.saved.spec.version
        || value.snapshot.spec.session_id !== state.saved.spec.session_id) throw new Error('回退预览目标不一致，当前内容不变。');
      emit({ preview: value, history: [], message: '正在预览回退后的内容，确认后才保存。' });
    }),
  });
}
