/** Free-HTML library state. Dirty ≠ active edit context. Leave three-choice is host-owned. */
import { createHtmlImporter } from './html-import.mjs';
import { SAMPLE_PROMPTS } from './generate-context.mjs';
import { applyTextToShineNode, createMockPageAdapters } from './mock-adapters.mjs';
import { bindingLabel, defaultRailCollapsed, inspectPage, panelPresentation, widthBand } from './host-visual.mjs';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function asAgentPackage(pkg) {
  if (!pkg || typeof pkg.html !== 'string' || !String(pkg.html).trim()) return null;
  return {
    html: pkg.html,
    css: typeof pkg.css === 'string' ? pkg.css : '',
    js: typeof pkg.js === 'string' ? pkg.js : '',
    resources: Array.isArray(pkg.resources) ? pkg.resources : [],
    node_map: Array.isArray(pkg.node_map) ? pkg.node_map : [],
  };
}

function isLive(adapters) {
  return adapters?.kind === 'p12-live';
}

function emptyState(viewportWidth, adapters) {
  return {
    view: 'home',
    viewportWidth,
    railCollapsed: defaultRailCollapsed(viewportWidth),
    prompt: '',
    designGuide: null,
    skill: null,
    dataContext: null,
    assetsExpanded: false,
    assets: [],
    pages: [],
    cockpitSelectionId: null,
    current: null,
    mode: 'browse',
    selection: null,
    contextPanel: null,
    overlay: null,
    preview: null,
    importCandidate: null,
    textDraft: null,
    historyItems: [],
    confirmationUncertain: false,
    lastIdempotencyKey: null,
    pendingLeaveIntent: null,
    busy: false,
    message: '',
    liveStatus: '',
    hostError: '',
    inspector: null,
    previewAlive: true,
    adapterKind: adapters.kind,
    nativeChatReachable: true,
  };
}

function createLifetime() {
  if (typeof AbortController === 'function') return new AbortController();
  const listeners = new Set();
  const signal = {
    aborted: false,
    addEventListener(type, fn) { if (type === 'abort') listeners.add(fn); },
    removeEventListener(type, fn) { listeners.delete(fn); },
  };
  return {
    signal,
    abort() {
      if (signal.aborted) return;
      signal.aborted = true;
      for (const fn of listeners) fn();
    },
  };
}

export function createFreeHtmlLibraryStore({ adapters, now = () => Date.now(), viewportWidth = 1440 } = {}) {
  const bound = adapters ?? createMockPageAdapters({ now });
  const listeners = new Set();
  const lifetime = createLifetime();
  let state = emptyState(viewportWidth, bound);
  const importer = bound.documents ? createHtmlImporter({ documents: bound.documents }) : null;
  let openEpoch = 0;

  const emit = patch => {
    if (lifetime.signal.aborted) return;
    state = { ...state, ...patch };
    for (const listener of listeners) listener();
  };

  function snapshot() {
    return state;
  }

  function hasUnsavedChanges() {
    if (state.confirmationUncertain || state.importCandidate || state.textDraft?.changed) return true;
    if (state.preview?.status === 'PENDING') return true;
    if (state.current?.dirty) return true;
    return false;
  }

  function hasActiveEditContext() {
    return state.mode === 'edit' && Boolean(state.selection);
  }

  function refreshList() {
    emit({ pages: bound.assets.list() });
  }

  async function perform(work) {
    if (state.busy || lifetime.signal.aborted) return;
    emit({ busy: true, message: '' });
    try { return await work(); }
    catch (error) {
      emit({
        message: error instanceof Error ? error.message : '操作失败，当前内容不变',
        liveStatus: error instanceof Error ? error.message : '操作失败',
        hostError: error?.code === 'FORBIDDEN' || error?.code === 'UNAUTHORIZED' ? '权限或会话错误，请回到原生对话重试' : state.hostError,
      });
    }
    finally { emit({ busy: false }); }
  }

  function packageSrc(pkg) {
    return bound.preview.srcdoc(pkg);
  }

  function acceptSpec(spec) {
    if (!spec?.page_id || !spec.package) throw new Error('保存回执不完整，请重试核对');
    const same = state.current?.page_id === spec.page_id;
    const history = same ? state.current.history : [];
    const page = { ...spec, package: clone(spec.package), savedPackage: clone(spec.package), dirty: false,
      updated_at: now(), history: [...history.filter(row => row.version !== spec.version),
        { version: spec.version, title: spec.title, at: now(), package: clone(spec.package) }] };
    bound.assets.put(page); refreshList();
    emit({ current: page, view: 'workspace', preview: null, importCandidate: null, textDraft: null,
      selection: null, overlay: null, confirmationUncertain: false, historyItems: [],
      liveStatus: `已保存 · v${page.version}` });
  }
  function assertEditable() {
    if (state.confirmationUncertain || state.preview || state.importCandidate) throw new Error('请先处理当前预览或核对保存结果');
  }
  refreshList();

  function finishLeave(intent) {
    if (intent === 'home') {
      emit({
        view: 'home', current: null, mode: 'browse', selection: null, overlay: null,
        contextPanel: null, preview: null, pendingLeaveIntent: null,
        liveStatus: '已离开到资料库',
      });
      return;
    }
    emit({
      pendingLeaveIntent: null,
      liveStatus: intent === 'conversation' ? '可返回原生对话' : '已处理离开',
    });
  }

  return {
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    getSnapshot: snapshot,
    selectCockpitAsset(id) { emit({ cockpitSelectionId: id }); },
    hasUnsavedChanges,
    hasActiveEditContext,
    dispose() { lifetime.abort(); listeners.clear(); },
    adapters: bound,
    samplePrompts: SAMPLE_PROMPTS,
    setPrompt(value) { emit({ prompt: value }); },
    setViewport(width) {
      const next = Number(width) || state.viewportWidth;
      emit({
        viewportWidth: next,
        railCollapsed: defaultRailCollapsed(next) ? true : state.railCollapsed,
      });
    },
    toggleRail() {
      emit({ railCollapsed: !state.railCollapsed });
    },
    setRailOpen(open) {
      emit({ railCollapsed: !open });
    },
    setDesignGuide(guide) { emit({ designGuide: guide }); },
    setSkill(skill) { emit({ skill }); },
    setDataContext(dataContext) { emit({ dataContext }); },
    toggleAssets() { emit({ assetsExpanded: !state.assetsExpanded }); },
    applyExample(text) { emit({ prompt: text }); },
    async generate() {
      const prompt = state.prompt;
      await perform(async () => {
        let submitted;
        try {
          submitted = await Promise.resolve(
            bound.nativeChat.submitGeneratePrompt(prompt, { designGuide: state.designGuide, skill: state.skill }),
          );
        } catch (error) {
          emit({ prompt, liveStatus: '生成失败，已保留输入', message: error.message });
          throw error;
        }
        const title = prompt.slice(0, 32) || '未命名页面';
        if (isLive(bound)) {
          const pkg = asAgentPackage(submitted?.package);
          if (!pkg) {
            const error = new Error('原生 Agent 未返回页面源码包');
            error.code = 'NATIVE_GENERATE_UNAVAILABLE';
            emit({ prompt, liveStatus: '生成失败，已保留输入', message: error.message });
            throw error;
          }
          if (typeof bound.documents?.generateAndConfirm !== 'function') {
            const error = new Error('页面保存库尚未配置隔离 HTTP');
            error.code = 'http_not_configured';
            throw error;
          }
          const persisted = await bound.documents.generateAndConfirm({
            title,
            session_id: submitted?.session_id || 'native_session_fixture',
            package: pkg,
            binding_manifest: { bindings: [], result_refs: [] },
            idempotency_key: bound.nextId('idem'),
          });
          if (!persisted?.ok || !persisted.page) {
            const error = new Error('页面未能写入保存库');
            error.code = persisted?.reason || 'http_not_configured';
            throw error;
          }
          bound.assets.put(persisted.page);
          refreshList();
          emit({
            view: 'workspace', current: persisted.page, mode: 'browse', selection: null, overlay: null,
            contextPanel: null, preview: null, liveStatus: '已用原生对话生成并写入保存库',
            message: '无经营数据也可生成；当前为未绑定样例',
          });
          return;
        }
        const pageId = bound.nextId('page');
        const pkg = bound.samplePackage();
        pkg.html = applyTextToShineNode(pkg.html, 'n_title', title);
        const saved = clone(pkg);
        const page = {
          page_id: pageId,
          session_id: 'native_session_fixture',
          title,
          version: 1,
          base_version: 0,
          binding_state: 'UNBOUND_SAMPLE',
          binding_manifest: { bindings: [], result_refs: [] },
          package: pkg,
          savedPackage: saved,
          dirty: false,
          updated_at: now(),
          history: [{ version: 1, title, at: now(), package: clone(saved) }],
        };
        bound.assets.put(page);
        refreshList();
        emit({
          view: 'workspace', current: page, mode: 'browse', selection: null, overlay: null, contextPanel: null,
          preview: null, liveStatus: '已用原生对话生成示例页面', message: '无经营数据也可生成；当前为示例数据',
        });
      });
    },
    async refreshPages() {
      await perform(async () => {
        if (bound.documents?.pullList) {
          const got = await bound.documents.pullList();
          if (!got.ok) throw new Error('页库暂时不可用，请重试');
        }
        refreshList();
      });
    },
    async openPage(pageId) {
      if (state.busy || hasUnsavedChanges()) { emit({ message: '请先保存或放弃当前修改' }); return false; }
      const epoch = ++openEpoch;
      return perform(async () => {
        if (isLive(bound) && bound.documents?.pullPage) {
          const got = await bound.documents.pullPage(pageId);
          if (!got.ok) throw new Error('页面不存在、不可用或无权限');
        }
        if (epoch !== openEpoch) return false;
        const page = bound.assets.get(pageId);
        if (!page?.package) throw new Error('页面不存在或无权限');
        emit({ view: 'workspace', current: clone(page), mode: 'browse', selection: null, overlay: null,
          contextPanel: null, preview: null, textDraft: null, historyItems: [], pendingLeaveIntent: null,
          previewAlive: true, liveStatus: `已打开 ${page.title}` });
        return true;
      });
    },
    async previewImport(input) {
      return perform(async () => {
        assertEditable();
        if (hasUnsavedChanges()) throw new Error('请先处理当前修改');
        if (!importer) throw new Error('页库导入能力尚未连接');
        const got = await importer.createCandidate(input);
        if (!got.ok) {
          const details = [...(got.error.missing ?? []), ...(got.error.unsupported ?? [])]
            .map(row => row.path ?? row.url).filter(Boolean).slice(0, 4).join('、');
          throw new Error(`${got.error.message}${details ? `：${details}` : ''}`);
        }
        emit({ importCandidate: got, lastIdempotencyKey: bound.nextId('import'), liveStatus: '副本待确认，尚未保存' });
        return true;
      });
    },
    async confirmImport() {
      return perform(async () => {
        if (!state.importCandidate) return;
        const wasUncertain = state.confirmationUncertain;
        emit({ confirmationUncertain: true });
        const got = await importer.confirm(state.importCandidate.preview_id, state.lastIdempotencyKey);
        if (!got.ok) {
          emit({ confirmationUncertain: wasUncertain || got.error.recoverable !== false && (!got.error.status || got.error.status >= 500) });
          throw new Error(got.error.message);
        }
        const expected = state.importCandidate.snapshot?.spec;
        if (got.spec.session_id !== state.importCandidate.origin.session_id || got.spec.origin_path !== state.importCandidate.origin.path
          || got.spec.version !== 1 || (expected && got.spec.page_id !== expected.page_id)) throw new Error('入库回执不匹配，请用同一请求重试核对');
        acceptSpec(got.spec);
        return got.page_id;
      });
    },
    setReplacementText(value, original = state.textDraft?.original ?? '') {
      if (state.busy || state.preview || state.confirmationUncertain || !state.selection?.ok) return;
      emit({ textDraft: { value, original, changed: value !== original } });
    },
    discardTextDraft() { if (!state.busy && !state.confirmationUncertain) emit({ textDraft: null }); },
    async loadHistory() {
      await perform(async () => {
        if (!state.current) return;
        const got = bound.documents?.pullHistory ? await bound.documents.pullHistory(state.current.page_id)
          : { ok: true, items: state.current.history };
        if (!got.ok) throw new Error('版本历史读取失败');
        emit({ historyItems: got.items, contextPanel: 'history' });
      });
    },
    async previewRollback(version) {
      await perform(async () => {
        assertEditable();
        if (hasUnsavedChanges()) throw new Error('请先处理当前修改');
        if (!bound.documents?.rollbackPreview) throw new Error('版本回退尚未连接');
        const got = await bound.documents.rollbackPreview({ page_id: state.current.page_id,
          base_version: state.current.version, to_version: version });
        if (!got.ok || !got.body?.snapshot?.spec?.package) throw new Error('无法取得回退预览');
        emit({ preview: { preview_id: got.body.preview_id, operation: 'ROLLBACK', status: 'PENDING',
          snapshot: got.body.snapshot.spec.package, base_package: state.current.package },
          lastIdempotencyKey: bound.nextId('rollback'), contextPanel: null, selection: null,
          liveStatus: `回退到 v${version} 的预览，确认后保存为新版本` });
      });
    },
    requestLeave(intent) {
      if (!hasUnsavedChanges()) {
        if (intent === 'home') emit({ view: 'home', current: null, mode: 'browse', selection: null, overlay: null, contextPanel: null, preview: null, pendingLeaveIntent: null });
        else emit({ pendingLeaveIntent: null });
        return { blocked: false, hasUnsavedChanges: false, hasActiveEditContext: hasActiveEditContext() };
      }
      emit({ pendingLeaveIntent: intent, liveStatus: '存在未保存修改；请选择保存、放弃或留在当前页' });
      return { blocked: true, hasUnsavedChanges: true, hasActiveEditContext: hasActiveEditContext() };
    },
    stayLeave() {
      emit({ pendingLeaveIntent: null, liveStatus: '已留在当前页，未保存也未放弃' });
      return { navigated: false, intent: null };
    },
    async persistForLeave() {
      if (state.busy) return { ok: false, reason: 'busy' };
      if (!hasUnsavedChanges()) return { ok: true };
      if (state.confirmationUncertain) {
        emit({ message: '保存结果待核对，请先核对', liveStatus: '保存结果待核对' });
        return { ok: false, reason: 'confirmation_uncertain' };
      }
      if (state.importCandidate) await this.confirmImport();
      else if (state.textDraft?.changed && !state.preview) { await this.previewPatch(state.textDraft.value); if (state.preview) await this.confirmPatch(); }
      else if (state.preview?.status === 'PENDING') await this.confirmPatch();
      else if (state.current?.dirty) await this.saveDraft();
      if (hasUnsavedChanges()) return { ok: false, reason: 'save_failed' };
      return { ok: true };
    },
    async discardForLeave() {
      if (state.busy) return { ok: false, reason: 'busy' };
      if (!hasUnsavedChanges()) return { ok: true };
      if (state.confirmationUncertain) {
        emit({ message: '保存结果待核对，不能放弃后离开', liveStatus: '保存结果待核对' });
        return { ok: false, reason: 'confirmation_uncertain' };
      }
      if (state.preview || state.importCandidate) {
        await this.cancelPreview();
        if (state.preview || state.importCandidate) return { ok: false, reason: 'cancel_failed' };
      }
      const restored = state.current ? { ...state.current,
        package: clone(state.current.savedPackage ?? state.current.package), dirty: false } : null;
      if (restored) bound.assets.put(restored);
      emit({ current: restored, textDraft: null, overlay: null, pendingLeaveIntent: null });
      return { ok: !hasUnsavedChanges() };
    },
    async saveAndLeave() {
      const intent = state.pendingLeaveIntent;
      if (!intent) return { navigated: false, intent: null };
      const persisted = await this.persistForLeave();
      if (!persisted.ok) return { navigated: false, intent, reason: persisted.reason };
      finishLeave(intent);
      return { navigated: true, intent };
    },
    async discardAndLeave() {
      const intent = state.pendingLeaveIntent;
      if (!intent) return { navigated: false, intent: null };
      const dropped = await this.discardForLeave();
      if (!dropped.ok) return { navigated: false, intent, reason: 'save_failed' };
      finishLeave(intent);
      return { navigated: true, intent };
    },
    enterEdit() { if (!state.current || state.busy || state.confirmationUncertain) return; emit({ mode: 'edit', liveStatus: '编辑中', overlay: 'selection' }); },
    exitEdit() {
      if (state.busy || hasUnsavedChanges()) { emit({ message: '请先确认或放弃当前修改' }); return; }
      emit({ mode: 'browse', selection: null, overlay: null, contextPanel: state.contextPanel === 'ai' ? null : state.contextPanel, liveStatus: '浏览中。退出编辑未保存' });
    },
    selectLocatable(request) {
      if (state.mode !== 'edit' || state.busy || state.confirmationUncertain || state.preview) return;
      if (state.textDraft?.changed) { emit({ message: '请先预览或放弃当前文本修改' }); return; }
      const located = bound.edit.locate(state.current?.package, request);
      if (!located.ok) {
        emit({ selection: { ok: false, stale: true, requireReselect: true, label: located.error.message, code: located.error.code }, overlay: 'selection', liveStatus: located.error.message });
        return;
      }
      emit({ selection: located, textDraft: null, overlay: 'selection', liveStatus: `当前范围：${located.label}` });
    },
    selectWholePage() { this.selectLocatable({ kind: 'whole_page', user_switched: true }); },
    clearSelection() { if (state.busy || hasUnsavedChanges()) return; emit({ selection: null, overlay: state.mode === 'edit' ? 'selection' : null, liveStatus: '已取消选区' }); },
    openContext(panel) { emit({ contextPanel: panel }); },
    closeContext() { emit({ contextPanel: null, liveStatus: '已关闭上下文面板，未保存' }); },
    async previewPatch(replacementText, extras = {}) {
      await perform(async () => {
        assertEditable();
        const located = state.selection?.ok ? state.selection : null;
        if (!located) throw Object.assign(new Error('请先选择有效范围'), { code: 'MAPPING_STALE' });
        try {
          const preview = bound.edit.previewPatch({ pkg: state.current.package, selection: { ...located, ...extras }, replacementText, instruction: isLive(bound) ? undefined : replacementText,
            page_id: state.current.page_id, session_id: state.current.session_id, base_version: state.current.version,
            binding_manifest: state.current.binding_manifest, affectsShared: extras.affectsShared });
          if (isLive(bound) && bound.documents?.patchPreview) {
            const remote = await bound.documents.patchPreview({
              page_id: state.current.page_id,
              base_version: state.current.version,
              package: preview.snapshot,
            });
            if (!remote.ok) {
              const error = new Error('页面保存库尚未配置隔离 HTTP');
              error.code = remote.reason || 'http_not_configured';
              throw error;
            }
            emit({
              preview: { ...preview, preview_id: remote.body.preview_id, base_package: state.current.package },
              overlay: 'patch', lastIdempotencyKey: preview.idempotency_key, liveStatus: '补丁预览待确认',
            });
            return;
          }
          emit({ preview, overlay: 'patch', lastIdempotencyKey: preview.idempotency_key, liveStatus: '补丁预览待确认' });
        } catch (error) {
          if (error.code === 'SCOPE_REQUIRES_CONFIRMATION' && error.preview?.preview_id) {
            emit({ preview: error.preview, overlay: 'patch', lastIdempotencyKey: error.preview.idempotency_key, liveStatus: error.message, message: error.message });
            return;
          }
          throw error;
        }
      });
    },
    confirmExpandedPatch() {
      if (!state.preview) return;
      emit({ preview: { ...state.preview, selection: { ...state.preview.selection, confirmExpanded: true } }, liveStatus: '已确认扩大范围，请确认提交补丁' });
    },
    async confirmPatch() {
      await perform(async () => {
        const preview = state.preview;
        if (!preview) throw new Error('没有待确认补丁');
        if (preview.expanded_scope === 'preview_expanded_range' && !preview.selection?.confirmExpanded) {
          throw Object.assign(new Error('共享样式影响超出选区，请确认实际范围'), { code: 'SCOPE_REQUIRES_CONFIRMATION' });
        }
        const wasUncertain = state.confirmationUncertain;
        try {
          if (isLive(bound) && bound.documents?.confirmPreview) {
            emit({ confirmationUncertain: true });
            const confirmed = await bound.documents.confirmPreview(preview.preview_id, state.lastIdempotencyKey);
            const spec = confirmed.body?.spec ?? confirmed.spec;
            if (spec?.page_id !== state.current.page_id || spec?.session_id !== state.current.session_id
              || spec?.version !== state.current.version + 1) throw new Error('保存回执不匹配，请重试核对');
            acceptSpec(spec);
            return;
          }
          const applied = bound.edit.confirmPatch(preview.preview_id, { idempotency_key: state.lastIdempotencyKey });
          const nextVersion = state.current.version + 1;
          const snapshot = clone(applied.snapshot);
          const page = {
            ...state.current,
            package: snapshot,
            savedPackage: clone(snapshot),
            version: nextVersion,
            base_version: state.current.version,
            dirty: false,
            history: [...state.current.history, { version: nextVersion, title: state.current.title, at: now(), package: clone(snapshot) }],
          };
          bound.assets.put(page);
          refreshList();
          emit({ current: page, preview: null, textDraft: null, overlay: null, confirmationUncertain: false, liveStatus: `D6 补丁已确认 · v${page.version}` });
        } catch (error) {
          if (isLive(bound) && (wasUncertain || error.status == null || error.status >= 500)) {
            emit({ confirmationUncertain: true, liveStatus: '保存结果待核对；使用同一确认请求重试' });
          } else if (isLive(bound)) emit({ confirmationUncertain: false });
          else if (error.message.includes('未收到') || error.code === 'RECEIPT_UNCERTAIN') emit({ confirmationUncertain: true });
          throw error;
        }
      });
    },
    async cancelPreview() {
      await perform(async () => {
        if (state.confirmationUncertain) throw new Error('保存结果待核对，暂不能取消或切换');
        if (state.importCandidate) {
          const got = await importer.cancel(state.importCandidate.preview_id);
          if (!got.ok) throw new Error(got.error.message);
        }
        if (state.preview) {
          if (isLive(bound) && bound.documents?.cancelPreview) {
            const got = await bound.documents.cancelPreview(state.preview.preview_id);
            if (!got.ok || got.body?.status !== 'CANCELLED' || got.body?.preview_id !== state.preview.preview_id) throw new Error('未取得取消回执，保留当前预览');
          }
          bound.edit.cancelPatch(state.preview.preview_id);
        }
        emit({ preview: null, importCandidate: null, textDraft: null,
          overlay: state.mode === 'edit' ? 'selection' : null, liveStatus: '已取消预览，已保存版本不变' });
      });
    },
    async saveDraft() {
      if (isLive(bound) && bound.documents?.savePreview) {
        const prepared = await perform(async () => {
          assertEditable();
          if (!state.current) throw new Error('没有可保存的页面');
          const remote = await bound.documents.savePreview({ page_id: state.current.page_id,
            base_version: state.current.version, title: state.current.title,
            package: state.current.package, binding_manifest: state.current.binding_manifest });
          if (!remote.ok || !remote.body?.preview_id) throw new Error('无法取得保存预览');
          emit({ preview: { preview_id: remote.body.preview_id, operation: 'SAVE', status: 'PENDING',
            snapshot: clone(state.current.package), base_package: state.current.savedPackage },
            lastIdempotencyKey: bound.nextId('save'), liveStatus: '保存待确认' });
          return true;
        });
        if (prepared) await this.confirmPatch();
        return;
      }
      await perform(async () => {
        if (!state.current) throw new Error('没有可保存的页面');
        const nextVersion = state.current.version + 1;
        const snapshot = clone(state.current.package);
        const page = {
          ...state.current,
          savedPackage: snapshot,
          version: nextVersion,
          base_version: state.current.version,
          dirty: false,
          history: [...state.current.history, { version: nextVersion, title: state.current.title, at: now(), package: clone(snapshot) }],
        };
        bound.assets.put(page);
        refreshList();
        emit({ current: page, liveStatus: `D9 已显式保存 · v${page.version}`, message: '退出编辑或关面板不会走这条保存' });
      });
    },
    markLocalDraft(pkg) {
      if (!state.current || state.busy || state.preview || state.confirmationUncertain) return;
      emit({ current: { ...state.current, package: pkg, dirty: true }, liveStatus: '本地草稿待显式保存' });
    },
    async rollback(version) {
      if (isLive(bound) && bound.documents?.rollbackPreview) {
        const previous = state.preview;
        await this.previewRollback(version);
        if (state.preview && state.preview !== previous && state.preview.operation === 'ROLLBACK') await this.confirmPatch();
        if (!hasUnsavedChanges()) emit({ mode: 'browse', selection: null });
        return;
      }
      await perform(async () => {
        const entry = state.current?.history.find(item => item.version === version);
        if (!entry?.package) throw new Error('没有该历史版本');
        const restored = clone(entry.package);
        const page = {
          ...state.current,
          version: entry.version,
          title: entry.title,
          dirty: false,
          package: restored,
          savedPackage: clone(restored),
          history: state.current.history.filter(item => item.version <= entry.version),
        };
        bound.assets.put(page);
        refreshList();
        emit({ current: page, mode: 'browse', selection: null, preview: null, liveStatus: `已回退到 v${version}，请重核授权` });
      });
    },
    inspectConfirmation() {
      if (!state.confirmationUncertain) return;
      if (state.importCandidate) return this.confirmImport();
      if (state.preview) return this.confirmPatch();
      emit({ message: '尚未取得可核对回执，请保留当前页' });
    },
    stopPreview() { emit({ previewAlive: false, liveStatus: '已停止页面预览，宿主仍可操作' }); },
    restartPreview() { emit({ previewAlive: true, liveStatus: '已重启页面预览' }); },
    inspectCurrent() {
      const binding = state.current ? bindingLabel(state.current.binding_state) : '';
      const result = inspectPage({
        host: { landmarks: true, nativeChat: state.nativeChatReachable, statusSpineVisible: true, keyboard: true },
        page: {
          focusableActions: Boolean(state.current?.package.html.includes('button') || state.current?.package.html.includes('href')),
          textStatus: Boolean(binding),
          chartAlternative: Boolean(state.current?.package.html.includes('<table') || state.current?.package.html.includes('摘要')),
          hostOverflow: false,
          canvasUnknown: Boolean(state.current?.package.html.includes('<canvas')),
        },
      });
      emit({ inspector: result, contextPanel: 'source' });
    },
    closeOverlay() {
      if (state.overlay === 'patch') return this.cancelPreview();
      if (state.selection) return this.clearSelection();
      if (state.contextPanel) return this.closeContext();
      if (state.mode === 'edit') return this.exitEdit();
      return undefined;
    },
    layout() {
      return {
        band: widthBand(state.viewportWidth),
        rail: state.railCollapsed ? 'collapsed' : 'open',
        panel: panelPresentation(state.viewportWidth),
        pointerEvents: bound.preview.pointerEvents(state.mode),
        srcdoc: state.current && state.previewAlive ? packageSrc(state.preview?.snapshot ?? state.current.package) : '',
      };
    },
  };
}
