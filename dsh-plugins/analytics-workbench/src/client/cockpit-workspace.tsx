import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { ThemeProvider } from './competition-shell/index.ts';
import type { CompetitionColorScheme } from './competition-shell/tokens.ts';
import type { LibraryBoardClient } from './library-board-client.mjs';
import type { FreeHtmlLibraryState, FreeHtmlLibraryStore } from './free-html-library/store.mjs';
import type { createCockpitDelivery, DeliverySnapshot } from './cockpit-delivery.mjs';
import { mergeCockpitProducts, type CockpitProduct } from './cockpit-products.mjs';
import { LibraryLayoutCanvas } from './library-layout-canvas.tsx';
import { CockpitSidebar } from './CockpitSidebar.tsx';
import { CockpitPageEditor, HtmlPreview } from './cockpit-page-editor.tsx';
import { BoardEditor, boardChangeSummary } from './cockpit-board-editor.tsx';
import { createLeaveCoordinator, type LeaveCoordinator } from './leave/leave-coordinator.mjs';
import { LeavePrompt } from './leave/leave-prompt.tsx';
import { cockpitCss } from './cockpit-workspace-style.ts';

const noopSubscribe = () => () => {};
const EMPTY_PAGE = { pages: [], current: null, mode: 'browse', busy: false, preview: null, importCandidate: null,
  message: '', confirmationUncertain: false, liveStatus: '' } as unknown as FreeHtmlLibraryState;
const EMPTY_DELIVERY: DeliverySnapshot = { status: 'no-session', sessionId: null, files: [], truncated: false, error: null, epoch: 0, refreshMode: 'manual' };
const groups = [{ key: 'html', name: 'HTML 页面', icon: '</>' }, { key: 'board', name: '数据看板', icon: '▦' },
  { key: 'spreadsheet', name: '表格与 CSV', icon: '▤' }, { key: 'pdf', name: 'PDF 文档', icon: 'PDF' }];

function workspacePackage(text: string) {
  const parsed = new DOMParser().parseFromString(text, 'text/html');
  // Build a fragment under the trusted wrapper; untrusted meta/base cannot replace its CSP.
  parsed.querySelectorAll('meta,base').forEach(node => node.remove());
  return { html: [...parsed.head.children].map(node => node.outerHTML).join('') + parsed.body.innerHTML, css: '', js: '', resources: [] };
}
export function LibraryCockpitPanel({ library, goConversation, themeSource, initialSurface = 'board', pageStore, delivery, leaveCoordinator,
  listWorkspaceFiles, openWorkspaceFile, readWorkspaceFile }: {
  library: LibraryBoardClient; goConversation(): void; leaveCoordinator?: LeaveCoordinator;
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
  initialSurface?: 'pages' | 'board'; pageStore?: FreeHtmlLibraryStore;
  delivery?: ReturnType<typeof createCockpitDelivery>;
  listWorkspaceFiles?: () => Promise<Array<Record<string, unknown>>>;
  openWorkspaceFile?: (product: Record<string, unknown>) => void;
  readWorkspaceFile?: (product: Record<string, unknown>) => Promise<string | null>;
}) {
  const state = useSyncExternalStore(library.subscribe, library.getSnapshot);
  const page = useSyncExternalStore(pageStore?.subscribe ?? noopSubscribe, pageStore?.getSnapshot ?? (() => EMPTY_PAGE));
  const deliveryState = useSyncExternalStore(delivery?.subscribe ?? noopSubscribe, delivery?.getSnapshot ?? (() => EMPTY_DELIVERY));
  const colorScheme = useSyncExternalStore(themeSource.subscribe, themeSource.getSnapshot);
  const root = useRef<HTMLElement>(null);
  const [width, setWidth] = useState(1440), [rail, setRail] = useState(true), [boardEdit, setBoardEdit] = useState(Boolean(state.fieldDraft || state.editContext));
  const [mobileInspector, setMobileInspector] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ html: true, board: true, spreadsheet: true, pdf: true });
  const [selectedId, setSelectedId] = useState<string | null>(() => page.cockpitSelectionId ?? (pageStore?.hasUnsavedChanges() && page.current
    ? 'page:' + page.current.page_id : state.saved ? 'board:' + state.saved.spec.board_id : null));
  const [legacyFiles, setLegacyFiles] = useState<Array<Record<string, unknown>>>([]);
  const [file, setFile] = useState({ text: '', loading: false, error: '' });
  const [notice, setNotice] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const readSeq = useRef(0), autoOpened = useRef(false);
  const readFileId = useRef<string | null>(null);
  const lastPage = useRef(page.current?.page_id);
  const shown = state.preview?.snapshot ?? state.layoutDraft ?? state.saved;
  const files = delivery ? deliveryState.files : legacyFiles;
  const products = mergeCockpitProducts({ files, pages: page.pages, boards: state.boards });
  const selected = products.find(item => item.id === selectedId) ?? null;
  const previewBoardId = state.preview && !pageStore?.hasUnsavedChanges() ? state.preview.snapshot.spec.board_id : null;
  const boardVisible = Boolean(previewBoardId) || selectedId?.startsWith('board:') || (!selectedId && initialSurface === 'board' && Boolean(shown));
  const savedHtml = Boolean(page.current && selectedId === 'page:' + page.current.page_id);
  const editing = boardVisible ? boardEdit : savedHtml && page.mode === 'edit';
  const busy = state.busy || page.busy || file.loading;
  const uncertain = state.confirmationUncertain || page.confirmationUncertain;
  const dirty = () => library.hasUnsavedChanges() || Boolean(pageStore?.hasUnsavedChanges());
  const rawPackage = useMemo(() => file.text ? workspacePackage(file.text) : null, [file.text]);
  const coordinator = useMemo(() => leaveCoordinator ?? createLeaveCoordinator({
    snapshot: () => ({ ...library.getSnapshot(), htmlUnsaved: Boolean(pageStore?.hasUnsavedChanges()),
      confirmationUncertain: library.getSnapshot().confirmationUncertain || Boolean(pageStore?.getSnapshot().confirmationUncertain) }),
    beginEpoch: kind => library.beginNavigation(kind),
    save: async () => {
      if (pageStore?.hasUnsavedChanges()) { const result = await pageStore.persistForLeave(); if (!result.ok) return result; }
      return library.saveForLeave();
    },
    discard: async () => {
      if (pageStore?.hasUnsavedChanges()) { const result = await pageStore.discardForLeave(); if (!result.ok) return result; }
      return library.discardDraft();
    },
    navigate: intent => intent.performLocal?.(),
  }), [leaveCoordinator, library, pageStore]);
  useEffect(() => () => { if (!leaveCoordinator) coordinator.dispose(); }, [coordinator, leaveCoordinator]);
  const guard = (action: () => void | Promise<void>) => {
    if (!busy) void coordinator.request({ kind: 'asset', performLocal: action });
  };
  const back = () => { if (leaveCoordinator) goConversation(); else guard(goConversation); };
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented || coordinator.getSnapshot().status !== 'idle' || state.preview || state.layoutDraft || page.preview) return;
      if (page.contextPanel) pageStore?.closeContext();
      else if (boardEdit) guard(() => setBoardEdit(false));
      else if (page.mode === 'edit') guard(() => pageStore?.exitEdit());
    };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [coordinator, boardEdit, page.contextPanel, page.mode, state.preview, state.layoutDraft, page.preview, busy]);
  const isDirty = dirty();
  useEffect(() => {
    if (!isDirty || leaveCoordinator) return;
    const prevent = (event: BeforeUnloadEvent) => {
      if (dirty()) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, [library, pageStore, isDirty, leaveCoordinator]);
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => {
    if (state.layoutDraft) root.current?.querySelector<HTMLElement>('.sm-layout-scroll')?.focus();
  }, [Boolean(state.layoutDraft)]);
  useEffect(() => {
    const active = document.activeElement;
    if (uncertain && !busy && (active === document.body || (active && root.current?.contains(active)))) {
      root.current?.querySelector<HTMLButtonElement>('[data-testid="library-inspect-confirmation"], [data-testid="html-confirm"]')?.focus();
    }
  }, [uncertain, busy]);
  const refresh = async () => {
    setNotice('');
    await Promise.all([library.refresh(), pageStore?.refreshPages(), delivery ? delivery.refresh() : listWorkspaceFiles?.().then(value => { if (!Array.isArray(value)) throw new Error('文件列表格式错误'); setLegacyFiles(value); }).catch(() => setNotice('工作区文件读取失败，请重试。'))]);
  };
  useEffect(() => { void refresh(); return () => { readSeq.current++; }; }, [library, pageStore, delivery, listWorkspaceFiles]);
  useEffect(() => {
    if (!root.current || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    observer.observe(root.current); return () => observer.disconnect();
  }, []);
  useEffect(() => { if (width < 1180 && editing) setRail(false); }, [width, editing]);
  useEffect(() => { if (state.preview || state.layoutDraft || page.preview) setMobileInspector(false); }, [state.preview, state.layoutDraft, page.preview]);
  useEffect(() => {
    if (page.current?.page_id && page.current.page_id !== lastPage.current) { setSelectedId('page:' + page.current.page_id); pageStore?.selectCockpitAsset('page:' + page.current.page_id); }
    lastPage.current = page.current?.page_id;
  }, [page.current?.page_id]);
  useEffect(() => {
    // Native tool cards can open a new, unsaved board while the panel is unmounted.
    // Its preview is the display intent, even if the last selection was HTML.
    if (!previewBoardId) return;
    readSeq.current++; readFileId.current = null;
    setFile({ text: '', loading: false, error: '' });
    setSelectedId('board:' + previewBoardId); pageStore?.selectCockpitAsset('board:' + previewBoardId);
  }, [previewBoardId, pageStore]);
  const source = deliveryState.sessionId;
  const lastSource = useRef(source);
  useEffect(() => {
    if (!delivery || lastSource.current === source) return;
    lastSource.current = source;
    if (!dirty()) { readSeq.current++; setSelectedId(null); pageStore?.selectCockpitAsset(null); setFile({ text: '', loading: false, error: '' }); autoOpened.current = false; }
    void delivery.refresh();
  }, [source, delivery]);

  const open = async (item: CockpitProduct) => {
    const seq = ++readSeq.current; setNotice(''); setBoardEdit(false);
    readFileId.current = item.kind === 'html' && !item.page_id ? item.id : null;
    if (item.board_id) {
      if (library.getSnapshot().saved?.spec.board_id !== item.board_id) await library.openBoard(item.board_id);
      if (library.getSnapshot().saved?.spec.board_id !== item.board_id) return;
    } else if (item.page_id && pageStore) {
      if (!await pageStore.openPage(item.page_id)) return;
    }
    setSelectedId(item.id); pageStore?.selectCockpitAsset(item.id);
    if (width < 760) setRail(false);
    if (item.kind === 'html' && !item.page_id) {
      setFile({ text: '', loading: true, error: '' });
      try {
        const text = delivery && item.path ? await delivery.readFile(item.path, { sessionId: item.sessionId }).then(result => {
          if (result.status !== 'ok') throw new Error('文件未能完整读取，请刷新后重试。'); return result.text;
        }) : await readWorkspaceFile?.(item);
        if (seq !== readSeq.current) return;
        if (typeof text !== 'string' || !text.trim()) throw new Error('文件为空或暂不可读取。');
        setFile({ text, loading: false, error: '' });
      } catch (error) { if (seq === readSeq.current) setFile({ text: '', loading: false, error: error instanceof Error ? error.message : '文件读取失败' }); }
    } else {
      setFile({ text: '', loading: false, error: '' });
      if (!item.page_id && !item.board_id) openWorkspaceFile?.(item);
    }
  };
  useEffect(() => {
    if (selectedId || autoOpened.current || busy || state.preview || dirty()) return;
    const first = initialSurface === 'board' ? products.find(item => item.kind === 'board') ?? products[0] : products.find(item => item.kind === 'html') ?? products[0];
    if (first) { autoOpened.current = true; void open(first); }
  }, [selectedId, files, page.pages, state.boards, busy]);
  useEffect(() => {
    // The shared store keeps selection across host panel switches, but the file
    // body is local. Re-read the exact session/path once when that row returns.
    if (busy || previewBoardId || dirty() || selected?.kind !== 'html' || selected.page_id || readFileId.current === selected.id) return;
    void open(selected);
  }, [selectedId, files, busy, previewBoardId]);

  const createImport = async () => {
    if (!selected?.path || !selected.sessionId || !pageStore || !file.text) return;
    const item = selected;
    await pageStore.previewImport({ html: file.text, path: item.path!, sessionId: item.sessionId!, title: item.title,
      readResource: async path => {
        // The Host text API cannot supply binary bytes. Fail explicitly for those resources.
        if (!/\.(css|m?js|svg)$/i.test(path) || !delivery) return null;
        const result = await delivery.readFile(path, { sessionId: item.sessionId });
        return result.status === 'ok' && typeof result.text === 'string' ? { text: result.text } : null;
      } });
  };
  const title = boardVisible ? shown?.spec.title ?? '数据看板' : selected?.title ?? '产物预览';
  const message = notice || (boardVisible ? state.message : page.message);
  const version = boardVisible ? state.saved?.spec.version : savedHtml ? page.current?.version : null;
  return <ThemeProvider colorScheme={colorScheme} className="sm-library-theme"><style>{cockpitCss}</style>
    <main ref={root} className="sm-library-workspace" data-testid="library-workspace" aria-busy={busy} data-mobile-inspector={mobileInspector}>
      <header className="sm-library-pagehead" data-testid="sm-library-pagehead">
        <div className="cockpit-heading"><button data-testid="sm-cockpit-back" aria-label="返回对话" onClick={back}>← <span className="cockpit-back-label">返回对话</span></button>
          <div><h1 ref={heading} tabIndex={-1}>项目驾驶舱</h1><small>会话产物 · 预览与编辑</small></div></div>
        <div className="cockpit-head-actions"><button aria-expanded={rail} onClick={() => setRail(!rail)}>{rail ? '收起产物' : '产物列表'}</button>
          {!boardVisible && selected?.kind === 'html' && !selected.page_id ? <button className="cockpit-primary" data-testid="html-import-start"
            disabled={busy || !file.text || Boolean(page.importCandidate) || uncertain || !pageStore}
            onClick={() => guard(createImport)}>保存为可编辑副本</button>
            : <button data-testid="cockpit-edit-btn" className={editing ? '' : 'cockpit-primary'} aria-pressed={editing}
              disabled={busy || uncertain || Boolean(page.preview) || (!savedHtml && !(boardVisible && state.saved))}
              onClick={() => {
                if (editing) guard(() => { if (boardVisible) setBoardEdit(false); else pageStore?.exitEdit(); });
                else { if (boardVisible) setBoardEdit(true); else pageStore?.enterEdit(); if (width < 1180) setRail(false); }
              }}>{editing ? '完成编辑' : '编辑'}</button>}
        </div>
      </header>
      <div className="cockpit-shell-body">
        <aside className="sm-library-rail" hidden={!rail} aria-label="产物列表">
          <div className="cockpit-rail-heading"><h2>产物</h2><button disabled={busy || dirty()} onClick={() => void refresh()} aria-label="刷新产物">刷新</button></div>
          <p className="cockpit-muted">已保存内容与当前会话交付</p>
          {delivery && deliveryState.status === 'loading' ? <p role="status" className="cockpit-muted">正在查找会话文件…</p> : null}
          {delivery && ['error','no-session'].includes(deliveryState.status) ? <div className="cockpit-rail-status" role={deliveryState.status === 'error' ? 'alert' : 'status'}>
            <p className="cockpit-muted">{deliveryState.status === 'error' ? '会话文件读取失败。已保存产物仍可使用。' : '尚未选择来源会话。回到对话后再打开驾驶舱。'}</p>
            {deliveryState.status === 'error' ? <button disabled={busy} onClick={() => void delivery.refresh()}>重试</button> : null}
          </div> : null}
          {deliveryState.truncated ? <p role="status" className="cockpit-muted">文件较多，当前显示有界扫描结果，列表未包含全部文件。</p> : null}
          <div className="sm-library-products" data-testid="library-products">
            {groups.map(group => {
              const rows = products.filter(item => item.kind === group.key);
              if (!rows.length) return null;
              return <div key={group.key}><button className="cockpit-group" aria-expanded={expanded[group.key]} data-testid={'library-panel-' + (group.key === 'html' ? 'pages' : group.key)}
                onClick={() => setExpanded(current => ({ ...current, [group.key]: !current[group.key] }))}><span>{expanded[group.key] ? '⌄' : '›'}　{group.name}</span><span>{rows.length}</span></button>
                <ul hidden={!expanded[group.key]}>{rows.map(item => <li key={item.id} data-kind={item.kind} data-selected={selectedId === item.id ? '1' : '0'}>
                  <button className="cockpit-product" data-testid="library-product-open" aria-current={selectedId === item.id} disabled={busy || uncertain}
                    onClick={() => guard(() => open(item))}><span className="cockpit-file-icon" aria-hidden="true">{group.icon}</span>
                    <span className="cockpit-product-copy"><strong>{item.title}</strong><small>{item.page_id ? '已保存页面' : item.board_id ? '已保存看板' : item.path} {item.subtitle}</small></span></button>
                </li>)}</ul></div>;
            })}
            {!products.length && deliveryState.status !== 'loading' ? <p className="cockpit-muted" data-testid="library-products-empty">暂无产物。会话交付的 HTML、表格和 PDF 会出现在这里。</p> : null}
          </div>
          <div className="cockpit-rail-footer"><p className="cockpit-muted">生成新内容请回到原生对话。<br />返回驾驶舱后刷新查看交付。</p></div>
        </aside>
        <section className="sm-library-canvas" aria-label="产物工作区">
          <div className="sm-library-pathbar" data-testid="library-pathbar"><div><p className="cockpit-eyebrow">{boardVisible ? '数据看板' : savedHtml ? '已保存页面' : selected ? '会话文件' : '工作区'}</p><h2>{title}</h2></div>
            <span className={'cockpit-badge' + (dirty() ? ' pending' : '')}>{uncertain ? '保存待核对' : dirty() ? '有未保存修改' : version ? '版本 ' + version : selected ? '只读预览' : '请选择产物'}</span></div>
          {message ? <p className="cockpit-live" role="status" data-testid="library-message">{message}</p> : null}
          {file.error ? <p className="cockpit-error" role="alert">{file.error} <button onClick={() => selected && void open(selected)}>重试读取</button></p> : null}
          {width < 760 && (editing || Boolean(page.contextPanel)) ? <div className="cockpit-mobile-context" aria-label="工作区视图">
            <button aria-pressed={!mobileInspector} onClick={() => setMobileInspector(false)}>画布预览</button>
            <button aria-pressed={mobileInspector} onClick={() => setMobileInspector(true)}>编辑设置</button>
          </div> : null}
          <div className="cockpit-content">
            {boardVisible ? <div className="cockpit-editor-layout"><div className="cockpit-editor-canvas">
              {state.preview ? <div className="cockpit-notice" data-testid="library-preview-banner"><div><strong>{state.preview.operation === 'ROLLBACK' ? '回退预览' : state.preview.operation === 'LAYOUT' ? '布局已通过检查' : '修改预览'}</strong>
                <p>{uncertain ? '保存结果待核对，请重试确认或核对结果。' : '尚未保存。画布已显示候选内容，确认后才保存。'}</p>
                {state.preview.operation === 'PATCH' && state.editContext ? <p data-testid="library-edit-diff">{boardChangeSummary(state.editContext.block, shown?.spec.blocks.find(row => row.block_id === state.editContext?.block_id))}</p> : null}</div>
                {uncertain ? <button data-testid="library-inspect-confirmation" disabled={busy} onClick={() => void library.inspectConfirmation()}>核对保存结果</button> : null}
                <button data-testid="library-cancel" disabled={busy} onClick={() => void library.cancel()}>{uncertain ? '尝试取消未应用草稿' : state.preview.operation === 'LAYOUT' ? '返回调整' : '取消预览'}</button>
                <button className="cockpit-primary" data-testid="library-confirm" disabled={busy} onClick={() => void library.confirm()}>{uncertain ? '重试确认' : '确认保存'}</button></div> : null}
              {state.layoutDraft ? <div className="cockpit-notice" data-testid="library-layout-banner"><div><strong>调整布局</strong><p>拖动手柄或用方向键调整，检查后再确认。</p></div>
                <button data-testid="layout-cancel" disabled={busy} onClick={() => void library.cancel()}>取消布局</button><button className="cockpit-primary" data-testid="layout-preview" disabled={busy} onClick={() => void library.previewLayout()}>检查布局</button></div> : null}
              <div className="cockpit-board-wrap" data-testid="library-board-view">{shown ? <LibraryLayoutCanvas snapshot={shown} editing={Boolean(state.layoutDraft)} disabled={busy || uncertain || Boolean(state.preview)}
                updateLayout={library.updateLayout} selectedBlockId={state.editContext?.block_id}
                selectBlock={boardEdit && !state.preview && !state.layoutDraft ? id => guard(async () => { await library.selectComponent(id); setMobileInspector(true); }) : undefined} />
                : <div className="cockpit-empty" data-testid="library-board-empty"><h2>还没有看板</h2><p>在原生对话生成后，回到这里查看。</p></div>}</div>
            </div><CockpitSidebar visible={boardEdit} title="编辑看板" onClose={() => guard(() => setBoardEdit(false))}>
              <BoardEditor library={library} state={state} />
              {!state.editContext && !state.preview && !state.layoutDraft ? <div className="cockpit-sidebar-tools">
                <button data-testid="layout-start" disabled={busy} onClick={() => library.beginLayout()}>调整布局</button>
                <button data-testid="library-rollback-previous" disabled={busy} onClick={() => void library.rollbackPrevious()}>预览回退上一版</button>
                <button disabled={busy} onClick={() => void library.loadHistory()}>查看版本历史</button>
                {state.history.map(row => <div className="cockpit-history-row" key={row.version}><span>版本 {row.version}</span><button disabled={busy || row.version === state.saved?.spec.version} onClick={() => void library.rollback(row.version)}>预览回退</button></div>)}
              </div> : null}
            </CockpitSidebar></div>
            : savedHtml && pageStore ? <CockpitPageEditor store={pageStore} onInspect={() => setMobileInspector(true)} />
            : page.importCandidate ? <><div className="cockpit-notice" data-testid="html-import-preview"><div><strong>保存为可编辑副本</strong><p>{uncertain ? '保存结果待核对。请用同一请求重试确认。' : '先检查页面。确认后进入页库，原工作区文件保持不变。'}</p></div>
              <button disabled={busy || uncertain} onClick={() => void pageStore?.cancelPreview()}>取消入库</button><button className="cockpit-primary" disabled={busy} onClick={() => void pageStore?.confirmImport()}>{uncertain ? '重试确认' : '确认保存副本'}</button></div>
              <div className="cockpit-frame-wrap"><HtmlPreview pkg={page.importCandidate.package} title={selected?.title ?? '副本预览'} /></div></>
            : selected?.kind === 'html' && rawPackage ? <><div className="cockpit-document-tools"><span className="cockpit-badge">工作区文件</span><span className="cockpit-muted">保存副本后可编辑映射文字；外部资源受限。</span></div>
              <div className="cockpit-frame-wrap"><HtmlPreview pkg={rawPackage} title={selected.title} /></div></>
            : selected && selected.kind !== 'html' ? <div className="cockpit-empty"><h2>{selected.title}</h2><p>在文件预览中查看这份{selected.kind === 'pdf' ? '文档' : '表格'}。</p><button onClick={() => openWorkspaceFile?.(selected)}>打开文件预览</button></div>
            : <div className="cockpit-empty" data-testid="library-canvas-empty"><div className="cockpit-empty-mark" aria-hidden="true">▧</div><h2>{file.loading ? '正在打开页面' : '从一份产物开始'}</h2><p>{file.loading ? '正在读取完整内容，请稍候。' : '在左侧选择会话交付或已保存产物，预览后就地修改。'}</p><button onClick={back}>返回对话</button></div>}
          </div>
        </section>
      </div>
      {!leaveCoordinator ? <LeavePrompt coordinator={coordinator} pageName={title} /> : null}
    </main>
  </ThemeProvider>;
}
