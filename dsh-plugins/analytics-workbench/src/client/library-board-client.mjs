/** Server-backed canvas state. No service token, local fake save or automatic write retry. */
import { boardSnapshot as snapshot, boardPreview, boardIdentity, boardEditContext } from '../board-spec/receipt.mjs';
import { changedLayouts, validatePlacement } from '../board-spec/grid-layout.mjs';
import { createNavigationEpoch, isEpochDiscarded, isSupersededRead, SupersededRead } from './navigation/navigation-epoch.mjs';
import { cancelDraft, cancelTarget } from './leave/cancel-receipt.mjs';
import { verifySaveReceipt, confirmIdempotencyKey } from './leave/save-receipt.mjs';
import { hasUnsavedChanges, hasActiveEditContext, unsavedReasons, layoutChanged } from './leave/dirty-predicate.mjs';
import { previousHistoryVersion } from '../board-spec/canvas-state.mjs';
import { describeBlockPatch, validateBlockChanges } from '../board-spec/block-changes.mjs';

const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);

export function createLibraryBoardClient(call, { editNative } = {}) {
  const listeners = new Set();
  const lifetime = new AbortController();
  const epoch = createNavigationEpoch();
  let state = { busy: false, message: '', boards: [], saved: null, preview: null, confirmationUncertain: false, layoutDraft: null, editContext: null, incoming: null, history: [], fieldDraft: null };
  const emit = patch => {
    if (lifetime.signal.aborted) return;
    if (patch.saved) {
      patch = { ...patch, fieldDraft: null };
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
  /**
   * One server call. Reads carry the navigation epoch that issued them: when a
   * newer intent has taken ownership, the settled result is dropped instead of
   * publishing an old page, an old list or an old error.
   *
   * Save/cancel operations are deliberately NOT epoch-gated — their receipt is
   * evidence matched by idempotency key/CAS, and a plain navigation must not
   * discard it. They are also never given the epoch signal, so a leave intent
   * cannot cancel a write in flight.
   */
  async function request(operation, payload) {
    const ticket = isEpochDiscarded(operation) ? epoch.ticket() : null;
    const stale = () => ticket !== null && !epoch.isCurrent(ticket.epoch);
    // The read is cancellable by the next intent as well as by plugin disposal.
    const signal = ticket ? AbortSignal.any([lifetime.signal, ticket.signal]) : lifetime.signal;
    let reply;
    try { reply = await call('/shine-mage-board', operation, payload, signal); }
    catch {
      lifetime.signal.throwIfAborted();
      if (stale()) throw new SupersededRead(ticket.epoch);
      throw new Error(operation === 'confirm'
        ? '未收到保存回执，保存结果待核对。请核对保存结果，或重试这次保存。'
        : '连接中断，未取得本次操作回执；保留当前内容，请稍后重试。');
    }
    lifetime.signal.throwIfAborted();
    if (stale()) throw new SupersededRead(ticket.epoch);
    if (!reply?.ok && operation === 'cancel' && reply?.error?.code === 'VERSION_CONFLICT') {
      const conflict = new Error('取消未成功：这份草稿已保存，不能通过取消撤销。请核对保存结果；如需恢复旧内容，请读取最新看板后预览回退。');
      conflict.cancelConflict = true;
      throw conflict;
    }
    if (!reply?.ok) throw new Error(reply?.error?.message || '未取得看板服务回执；当前内容不变。');
    return reply.value;
  }
  async function perform(work) {
    if (state.busy || lifetime.signal.aborted) return undefined;
    emit({ busy: true, message: '' });
    try { return await work(); }
    catch (error) {
      // A superseded read is not a user-facing failure: a newer intent owns the
      // page now, so there is nothing to report and nothing to overwrite.
      if (isSupersededRead(error)) return undefined;
      emit({ message: error instanceof Error ? error.message : '看板操作失败，当前内容不变。' });
      return undefined;
    }
    finally { emit({ busy: false }); }
  }
  /**
   * Submit a navigation intent: advance ownership, then run the work. An intent
   * that loses the busy gate does NOT advance the epoch, so an ignored second
   * click cannot kill the read the user is actually waiting for.
   */
  function intend(kind, work) {
    if (state.busy || lifetime.signal.aborted) return Promise.resolve(undefined);
    epoch.begin(kind);
    return perform(work);
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
    // The barrier reads the same dirty predicate the leave coordinator does
    // (D42): a merely-open layout mode or a clean selection is not a reason to
    // block, and only a real draft raises the switch prompt. Re-opening the
    // draft already on screen destroys nothing, so it stays allowed.
    const reopensSamePreview = intent.kind === 'preview' && state.preview?.preview_id === intent.id;
    if (unsavedReasons(state).length > 0 && !reopensSamePreview) {
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
  async function establishEdit(blockId, { sendNative }) {
    const saved = state.saved;
    if (!saved || !saved.spec.blocks.some(block => block.block_id === blockId)) throw new Error('请先打开看板并选择其中的组件。');
    if (state.confirmationUncertain || state.preview || state.layoutDraft || state.fieldDraft) throw new Error('请先处理当前修改，再切换组件。');
    let existing = await request('current_edit', { board_id: saved.spec.board_id });
    if (!sendNative && existing && existing.block_id !== blockId && !existing.preview_id) {
      const old = boardEditContext(existing);
      await cancelCurrent({ kind: 'edit', id: old.edit_context_id, idField: 'edit_context_id' });
      existing = null;
    }
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
    if (sendNative) await sendEdit();
  }
  async function selectEdit(blockId) {
    await establishEdit(blockId, { sendNative: true });
  }
  async function selectComponentOnly(blockId) {
    await establishEdit(blockId, { sendNative: false });
  }
  async function previewBlockPatch(changes) {
    const saved = state.saved;
    if (!saved) throw new Error('请先打开看板。');
    if (state.confirmationUncertain) {
      throw new Error('有未核对的保存回执，不能再发起内容 PATCH。');
    }
    if (state.layoutDraft || state.preview) {
      throw new Error('正在预览布局，不能同时做内容 PATCH；请先确认或取消布局。');
    }
    const blockId = state.editContext?.block_id;
    if (!blockId) throw new Error('请先选择组件。选择不会发送消息。');
    const block = saved.spec.blocks.find(item => item.block_id === blockId);
    const checked = validateBlockChanges(changes, {
      block,
      factsByResultId: { ...saved.facts_by_result_id, ...state.editContext?.facts_by_result_id },
    });
    if (!checked.ok) throw new Error(checked.message);
    const value = boardPreview(await request('patch_preview', {
      board_id: saved.spec.board_id,
      base_version: saved.spec.version,
      block_id: blockId,
      // The RPC validates props without an edit-context read. Carry the current
      // kind for a partial props edit; an unchanged kind preserves other props.
      changes: Object.hasOwn(checked.changes, 'props') && !Object.hasOwn(checked.changes, 'kind')
        ? { ...checked.changes, kind: block.kind } : checked.changes,
    }));
    if (value.status !== 'PENDING' || value.operation !== 'PATCH' || value.base_version !== saved.spec.version
      || value.snapshot.spec.board_id !== saved.spec.board_id) {
      throw new Error('内容补丁预览目标不一致；当前看板未保存。');
    }
    emit({ preview: { ...value, source: 'fields' }, layoutDraft: null, history: [], message: '组件修改已预览；确认后才保存。' });
  }
  /**
   * One cancellation path for all three entries (D45/T26). The receipt is
   * checked before any local state is cleared, so a missing, mismatched or
   * conflicting reply keeps the draft and the recovery prompt. The layout
   * special case lives in the helper, not here, so every caller shares it.
   */
  const cancelCurrent = async target => {
    const recovering = state.confirmationUncertain;
    const receipt = await cancelDraft({ ...target, request, emit });
    // A successful recovery must not leave a stale selection pinning the old
    // base version. Only a verified cancellation permits dropping this state.
    if (recovering) emit({ editContext: null, fieldDraft: null, layoutDraft: null });
    return receipt;
  };
  async function cancelEdit() {
    return cancelCurrent(cancelTarget({ editContext: state.editContext }));
  }
  async function readHistory(boardId) {
    const value = await request('history', { board_id: boardId });
    if (!Array.isArray(value) || value.some(row => !record(row) || !Number.isSafeInteger(row.version) || row.version < 1
      || !['GENERATE', 'PATCH', 'LAYOUT', 'ROLLBACK'].includes(row.operation) || !Number.isSafeInteger(row.created_at_ms))) {
      throw new Error('版本历史响应不合法。');
    }
    return value;
  }
  async function applyRollback(toVersion) {
    if (!state.saved || state.preview || state.layoutDraft || state.editContext) return;
    const value = boardPreview(await request('rollback_preview', { board_id: state.saved.spec.board_id,
      base_version: state.saved.spec.version, to_version: toVersion }));
    if (value?.status !== 'PENDING' || value.operation !== 'ROLLBACK') throw new Error('未取得回退预览，当前内容不变。');
    if (value.snapshot.spec.board_id !== state.saved.spec.board_id || value.base_version !== state.saved.spec.version
      || value.snapshot.spec.session_id !== state.saved.spec.session_id) throw new Error('回退预览目标不一致，当前内容不变。');
    emit({ preview: value, history: [], message: '正在预览回退后的内容，确认后才保存。' });
  }
  return Object.freeze({
    getSnapshot: () => state,
    setFieldDraft(changes) {
      if (state.busy || state.preview || state.confirmationUncertain) return;
      emit({ fieldDraft: changes && Object.keys(changes).length ? changes : null });
    },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    dispose() { lifetime.abort(); epoch.dispose(); listeners.clear(); },
    /** Dirty-draft predicate (D42): only real unsaved work blocks leaving. */
    hasUnsavedChanges: () => hasUnsavedChanges(state),
    /** Selection/focus context (D42): never a reason to block leaving. */
    hasActiveEditContext: () => hasActiveEditContext(state),
    unsavedReasons: () => unsavedReasons(state),
    /** Advance navigation ownership for a leave intent (D43/T25). */
    beginNavigation: kind => epoch.begin(kind),
    navigationEpoch: () => epoch.current,
    refresh: () => intend('refresh', async () => {
      await reloadList();
      if (state.saved && !state.preview && !state.layoutDraft && !state.editContext) await readBoard(state.saved.spec.board_id);
    }),
    openBoard: id => intend('board', () => navigate({ kind: 'board', id })),
    openPreview: (id, contextId) => intend('preview', () => navigate({ kind: 'preview', id, ...(contextId ? { contextId } : {}) })),
    beginEdit: blockId => intend('edit', () => navigate({ kind: 'edit', id: blockId })),
    selectComponent: blockId => intend('edit', () => selectComponentOnly(blockId)),
    describeSelectedPatch: () => {
      const block = state.saved?.spec.blocks.find(item => item.block_id === state.editContext?.block_id);
      return describeBlockPatch(block, { factsByResultId: { ...state.saved?.facts_by_result_id, ...state.editContext?.facts_by_result_id } });
    },
    previewBlockPatch: changes => perform(() => previewBlockPatch(changes)),
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
    /**
     * Drop the draft without navigating. Used by the leave coordinator's
     * "discard" choice; returns the receipt result instead of throwing so the
     * coordinator can stay on the page with the draft intact.
     *
     * `forLeave` keeps a clean selection out of the cancel targets: D42 says a
     * bare edit context is not an obstacle to leaving, so leaving must not
     * cancel it.
     */
    discardDraft: () => perform(async () => {
      const target = cancelTarget(state, { forLeave: true });
      if (!target) { emit({ fieldDraft: null }); return { ok: true }; }
      try {
        await cancelCurrent(target);
        emit({ incoming: null, fieldDraft: null });
        return { ok: true };
      } catch (error) {
        return { ok: false, message: error instanceof Error ? error.message : '未能放弃草稿，已留在当前页。' };
      }
    }),
    /**
     * Save the pending draft for a leave. Returns a receipt result; it never
     * throws, so the coordinator can apply the stay-on-failure rule. The receipt
     * is matched here, where the draft is in hand, and the idempotency key is
     * reused verbatim on a retry.
     *
     * A local layout draft has no saved receipt to match: it is only durable
     * once `previewLayout()` has produced a server-side preview. Saving one
     * directly would report success for a write that never happened, so it is
     * reported as unsaved instead of navigating away from the change.
     */
    saveForLeave: () => perform(async () => {
      if (!state.preview && state.fieldDraft) await previewBlockPatch(state.fieldDraft);
      const draft = state.preview;
      if (!draft) {
        if (layoutChanged(state)) return { ok: false, reason: 'layout_unsaved' };
        return { ok: true };
      }
      emit({ confirmationUncertain: true });
      const key = confirmIdempotencyKey(draft.preview_id);
      let saved;
      try {
        saved = snapshot(await request('confirm', { preview_id: draft.preview_id, key }));
      } catch (error) {
        // The write may or may not have landed; that is exactly what
        // `uncertain` means, and the coordinator must not navigate on it.
        return { ok: false, reason: 'uncertain', message: error instanceof Error ? error.message : undefined };
      }
      // The receipt is matched on the key that was actually sent: a snapshot
      // that merely shares board/session/version is not proof of this save.
      const receipt = verifySaveReceipt({ draft, saved, key });
      if (!receipt.ok) return receipt;
      const current = state.saved;
      emit({ saved: current?.spec.board_id === saved.spec.board_id && current.spec.version > saved.spec.version ? current : saved,
        preview: null, confirmationUncertain: false, editContext: null, incoming: null, message: '已确认保存。' });
      try { await readBoard(saved.spec.board_id); await reloadList(); }
      catch { emit({ message: '保存已确认，但当前版本刷新失败；保留收到的快照，可稍后刷新核对。' }); }
      return { ok: true };
    }),
    discardAndNavigate: () => perform(async () => {
      const intent = state.incoming;
      const target = cancelTarget(state);
      if (!intent || !target) return;
      await cancelCurrent(target);
      emit({ preview: null, layoutDraft: null, confirmationUncertain: false });
      await navigate(intent);
    }),
    cancel: () => perform(async () => {
      const target = cancelTarget(state);
      if (!target) return;
      if (target.kind === 'layout') { await cancelCurrent(target); return; }
      const restoreLayout = target.kind === 'preview' && state.preview?.operation === 'LAYOUT' && !state.confirmationUncertain
        ? state.preview.snapshot : null;
      await cancelCurrent(target);
      emit(restoreLayout
        ? { incoming: null, layoutDraft: restoreLayout, message: '已返回布局调整；尚未保存。' }
        : { incoming: null, fieldDraft: null });
    }),
    beginLayout() {
      if (state.busy || state.preview || !state.saved || state.layoutDraft || state.editContext || state.confirmationUncertain) return;
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
      const saved = snapshot(await request('confirm', { preview_id: draft.preview_id, key: confirmIdempotencyKey(draft.preview_id) }));
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
      emit({ history: await readHistory(state.saved.spec.board_id) });
    }),
    rollback: toVersion => perform(async () => { await applyRollback(toVersion); }),
    rollbackPrevious: () => perform(async () => {
      if (!state.saved || state.preview || state.layoutDraft || state.editContext) return;
      let history = state.history;
      if (!history.length) {
        history = await readHistory(state.saved.spec.board_id);
        emit({ history });
      }
      const previous = previousHistoryVersion({ spec: state.saved.spec, history });
      if (previous == null) { emit({ message: '没有可回退的更早版本。' }); return; }
      await applyRollback(previous);
    }),
  });
}
