import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import { LibraryLayoutCanvas } from './library-layout-canvas.tsx';
import type { LibraryBoardClient, LibraryState } from './library-board-client.mjs';
import { ThemeProvider } from './competition-shell/index.ts';
import type { CompetitionColorScheme } from './competition-shell/tokens.ts';
import { ActionsWorkbench } from './competition-actions/index.ts';
import { OverlayErrorBoundary } from './overlay-error-boundary.mjs';
import { crowdActionPackEnabled } from './crowd-action-pack.mjs';
import { FreeHtmlLibraryApp } from './free-html-library/FreeHtmlLibraryApp.tsx';
import { mergeCockpitProducts, type CockpitProduct } from './cockpit-products.mjs';

const KIND_LABEL = { html: 'HTML', spreadsheet: '表格', pdf: 'PDF', board: '看板' };
const EMPTY_PAGES: Array<{ page_id?: string; title?: string; version?: number }> = [];
const emptyPageSnap = {
  subscribe: (_listener: () => void) => () => {},
  getSnapshot: () => EMPTY_PAGES,
};

const css = `
.sm-library-workspace { --lib-rail:#f6f6f7; --lib-canvas:#fff; --lib-ink:#1f1f1f; --lib-muted:#8c8c8c; --lib-line:#ececec; --lib-active:#ececec; min-width:0; min-height:640px; height:100%; display:grid; grid-template-columns:240px minmax(0,1fr); grid-template-rows:minmax(0,1fr); background:var(--lib-rail); color:var(--lib-ink); font-family:var(--sm-font-body); }
.sm-library-rail { min-width:0; display:flex; flex-direction:column; gap:4px; padding:12px 10px 16px; border-right:1px solid var(--lib-line); background:var(--lib-rail); }
.sm-library-rail h1 { margin:4px 8px 12px; font:600 16px/22px var(--sm-font-body); }
.sm-library-search { display:flex; flex-direction:column; gap:4px; margin:0 4px 8px; color:var(--lib-muted); font-size:12px; }
.sm-library-search input { width:100%; min-height:32px; border:0; border-radius:8px; padding:6px 10px; background:#ececee; color:var(--lib-ink); font:inherit; }
.sm-library-nav { display:flex; flex-direction:column; gap:2px; margin:0 0 8px; }
.sm-library-nav button { justify-content:flex-start; min-height:32px; border:0; background:transparent; color:var(--lib-ink); border-radius:8px; padding:6px 10px; font:400 13px/18px var(--sm-font-body); }
.sm-library-nav button[aria-pressed="true"], .sm-library-products li[data-selected="1"] button { background:var(--lib-active); }
.sm-library-rail-foot { margin-top:auto; padding:8px 4px 0; }
.sm-library-canvas { min-width:0; min-height:0; display:flex; flex-direction:column; background:var(--lib-canvas); }
.sm-library-pathbar { display:flex; gap:8px; align-items:center; min-height:44px; padding:0 16px; border-bottom:1px solid var(--lib-line); font-size:13px; color:var(--lib-muted); }
.sm-library-pathbar strong { color:var(--lib-ink); font-weight:500; }
.sm-library-pathbar span { margin-right:auto; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.sm-library-document { position:relative; flex:1; min-height:0; overflow:auto; }
.sm-library-document iframe, .sm-library-document [data-testid="fhl-live-preview"] { display:block; width:100%; height:100%; min-height:560px; border:0; background:#fff; }
.sm-library-document [data-testid="fhl-root"] { min-height:100%; }
.sm-library-document [data-testid="fhl-root"] > header, .sm-library-document [data-testid="fhl-status-spine"], .sm-library-document [data-testid="fhl-home"], .sm-library-document [data-testid="fhl-skip-iframe"], .sm-library-document .sm-fhl-workspace-heading, .sm-library-document [data-testid="fhl-workspace"] > .sm-fhl-toolbar { display:none; }
.sm-library-ai-bar { position:absolute; top:12px; left:50%; transform:translateX(-50%); z-index:3; display:flex; gap:2px; padding:4px; background:#fff; border:1px solid #e8e8e8; border-radius:10px; box-shadow:0 6px 20px rgba(0,0,0,.08); }
.sm-library-ai-bar button { min-height:28px; border:0; background:transparent; padding:4px 10px; border-radius:8px; font:500 13px/18px var(--sm-font-body); }
.sm-library-empty { margin:48px auto; max-width:360px; color:var(--lib-muted); text-align:center; }
.sm-library-toolbar,.sm-library-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.sm-library-workspace p { margin:0; }
[data-testid="library-board-view"] p { color:var(--lib-muted); }
.sm-library-workspace button:not(.ant-btn),.sm-library-workspace select { font:inherit; color:inherit; background:transparent; border:1px solid var(--lib-line); border-radius:8px; padding:6px 10px; cursor:pointer; }
.sm-library-workspace button:not(.ant-btn):disabled { opacity:.5; cursor:not-allowed; }
.sm-library-workspace button:not(.ant-btn):focus-visible,.sm-library-workspace select:focus-visible,.sm-library-workspace [tabindex]:focus-visible,.sm-library-search input:focus-visible { outline:2px solid var(--sm-purple); outline-offset:2px; }
.sm-library-workspace .sm-library-confirm { background:var(--sm-purple); color:#fff; border-color:var(--sm-purple); }
.sm-library-banner { margin:12px 16px; padding:12px; border:1px solid var(--sm-purple); border-radius:8px; display:flex; flex-direction:column; gap:12px; }
.sm-library-products { display:flex; flex-direction:column; gap:4px; min-height:0; }
.sm-library-products-hint { color:var(--lib-muted); font-size:12px; padding:4px 10px; }
.sm-library-rail-section { display:flex; align-items:center; justify-content:space-between; padding:8px 10px 4px; color:var(--lib-muted); font-size:12px; }
.sm-library-products ul { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:2px; }
.sm-library-products li button { width:100%; display:flex; gap:8px; align-items:center; border:0; background:transparent; border-radius:8px; padding:8px 10px; text-align:left; font:400 13px/18px var(--sm-font-body); overflow:hidden; }
.sm-library-products li button span { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.sm-library-diff { overflow:auto; max-height:260px; }
.sm-library-diff table { width:100%; border-collapse:collapse; font-size:12px; table-layout:fixed; }
.sm-library-diff th,.sm-library-diff td { text-align:left; vertical-align:top; border-bottom:1px solid var(--lib-line); padding:8px; overflow-wrap:anywhere; white-space:pre-wrap; }
`;

function EditDiff({ state }: { state: LibraryState }) {
  if (state.preview?.operation !== 'PATCH' || !state.editContext) return null;
  const before = state.editContext.block;
  const after = state.preview.snapshot.spec.blocks.find(block => block.block_id === before.block_id);
  if (!after) return <p role="alert">修改目标缺失，请取消预览并核对。</p>;
  const fields = (block: typeof before): Record<string, unknown> => ({ 标题: block.title, 类型: block.kind,
    数据来源: block.source_result_id ?? '无', 布局: block.layout, ...block.props });
  const a = fields(before), b = fields(after);
  const changed = [...new Set([...Object.keys(a), ...Object.keys(b)])].filter(key => JSON.stringify(a[key]) !== JSON.stringify(b[key]));
  const display = (value: unknown) => value === undefined ? '不适用' : typeof value === 'string' ? value : JSON.stringify(value);
  return <div className="sm-library-diff" data-testid="library-edit-diff">
    <p>仅修改「{before.title}」；其他组件不变。</p>
    <table><caption>组件修改前后对照</caption><thead><tr><th scope="col">属性</th><th scope="col">修改前</th><th scope="col">修改后</th></tr></thead>
      <tbody>{changed.map(key => <tr key={key}><th scope="row">{key}</th><td>{display(a[key])}</td><td>{display(b[key])}</td></tr>)}</tbody></table>
  </div>;
}

function asSrcDoc(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return '';
  if (/<html[\s>]/i.test(trimmed) || /<!doctype/i.test(trimmed)) return trimmed;
  return `<!doctype html><html><head><meta charset="utf-8"></head><body>${trimmed}</body></html>`;
}

function CockpitProductsView({ items, busy, query, selectedId, onQuery, onRefresh, onOpen, showSearch = true }: {
  items: CockpitProduct[];
  busy: boolean;
  query: string;
  selectedId: string | null;
  onQuery(value: string): void;
  onRefresh(): void;
  onOpen(item: CockpitProduct): void;
  showSearch?: boolean;
}) {
  const needle = query.trim().toLowerCase();
  const filtered = needle ? items.filter(item => item.title.toLowerCase().includes(needle)) : items;
  return (
    <div className="sm-library-products" data-testid="library-products">
      {showSearch ? <label className="sm-library-search">搜索
        <input data-testid="library-products-search" value={query} placeholder="搜索" onChange={event => onQuery(event.target.value)} />
      </label> : null}
      <div className="sm-library-rail-section">
        <span>我的资料</span>
        <button type="button" data-testid="library-products-refresh" disabled={busy} onClick={onRefresh}>刷新</button>
      </div>
      {filtered.length === 0
        ? <p data-testid="library-products-empty">还没有产物。</p>
        : (
          <ul data-testid="library-products-list">
            {filtered.map(item => (
              <li key={item.id} data-kind={item.kind} data-selected={selectedId === item.id ? '1' : '0'}>
                <button type="button" data-testid="library-product-open" aria-current={selectedId === item.id}
                  onClick={() => onOpen(item)}>
                  <span>{item.title}</span>
                  <span data-testid="library-product-kind">{KIND_LABEL[item.kind as keyof typeof KIND_LABEL] ?? item.kind}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}

export function LibraryCockpitPanel({ library, goConversation, themeSource, initialSurface = 'board', pageStore,
  listWorkspaceFiles, openWorkspaceFile, readWorkspaceFile }: {
  library: LibraryBoardClient; goConversation(): void;
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
  initialSurface?: 'pages' | 'board';
  pageStore?: ReturnType<typeof import('./free-html-library/store.mjs').createFreeHtmlLibraryStore>;
  listWorkspaceFiles?: () => Promise<Array<Record<string, unknown>>>;
  openWorkspaceFile?: (product: Record<string, unknown>) => void;
  readWorkspaceFile?: (product: Record<string, unknown>) => Promise<string | null>;
}) {
  const state = useSyncExternalStore(library.subscribe, library.getSnapshot);
  const colorScheme = useSyncExternalStore(themeSource.subscribe, themeSource.getSnapshot);
  const heading = useRef<HTMLHeadingElement>(null);
  const previewBanner = useRef<HTMLDivElement>(null);
  const recovery = useRef<HTMLButtonElement>(null);
  const lastFocused = useRef<HTMLElement | null>(null);
  const wasBusy = useRef(state.busy);
  const [panel, setPanel] = useState<'pages' | 'board' | 'actions'>(initialSurface);
  const [visitedActions, setVisitedActions] = useState(false);
  const [workspaceFiles, setWorkspaceFiles] = useState<Array<Record<string, unknown>>>([]);
  const [editingHtml, setEditingHtml] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filePreview, setFilePreview] = useState('');
  const pageList = useSyncExternalStore(
    pageStore ? pageStore.subscribe : emptyPageSnap.subscribe,
    () => (pageStore ? pageStore.getSnapshot().pages : EMPTY_PAGES),
  );
  useEffect(() => { void library.refresh(); }, [library]);
  const refreshProducts = () => {
    if (typeof listWorkspaceFiles !== 'function') { setWorkspaceFiles([]); return; }
    void listWorkspaceFiles().then(items => setWorkspaceFiles(Array.isArray(items) ? items : [])).catch(() => setWorkspaceFiles([]));
  };
  useEffect(() => { if (panel === 'pages') refreshProducts(); }, [panel, listWorkspaceFiles]);
  useEffect(() => { heading.current?.focus(); }, [state.preview?.preview_id, state.saved?.spec.board_id, Boolean(state.layoutDraft)]);
  useEffect(() => {
    if (state.busy || !state.confirmationUncertain || !state.preview) return;
    // Disabling an in-flight action can leave browser focus on the body. Hand
    // recovery back to the keyboard, but do not steal focus from native chat.
    const active = recovery.current?.ownerDocument.activeElement;
    if (active === recovery.current?.ownerDocument.body || active === heading.current ||
        (active && previewBanner.current?.contains(active))) recovery.current?.focus();
  }, [state.busy, state.confirmationUncertain, state.preview?.preview_id]);
  useEffect(() => {
    const settled = wasBusy.current && !state.busy;
    wasBusy.current = state.busy;
    const doc = heading.current?.ownerDocument;
    if (!settled || !doc || doc.activeElement !== doc.body) return;
    const target = lastFocused.current;
    if (target?.isConnected && !target.matches(':disabled')) target.focus();
    else heading.current?.focus();
  }, [state.busy]);
  useEffect(() => {
    if (!library.hasUnsavedChanges()) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [library, state.layoutDraft, state.preview, state.confirmationUncertain, state.editContext]);
  const shown = state.preview?.snapshot ?? state.layoutDraft ?? state.saved;
  const actionsEnabled = crowdActionPackEnabled();
  const boardChrome = panel !== 'pages';
  const products = mergeCockpitProducts({ files: workspaceFiles, boards: state.boards, pages: pageList });
  const selected = products.find(item => item.id === selectedId) ?? null;
  const openProduct = (item: CockpitProduct) => {
    setSelectedId(item.id);
    setEditingHtml(false);
    setFilePreview('');
    if (item.kind === 'board' && item.board_id) {
      void library.openBoard(item.board_id);
      setPanel('board');
      return;
    }
    setPanel('pages');
    if (item.page_id && pageStore) {
      void pageStore.openPage(item.page_id);
      return;
    }
    if (item.kind === 'html') {
      if (readWorkspaceFile) {
        void readWorkspaceFile(item).then(text => setFilePreview(typeof text === 'string' ? text : '')).catch(() => setFilePreview(''));
      }
      return;
    }
    openWorkspaceFile?.(item);
  };
  const editHtml = (item: CockpitProduct | null = selected) => {
    if (!item || item.kind !== 'html') return;
    if (item.page_id && pageStore) {
      void pageStore.openPage(item.page_id);
      pageStore.enterEdit();
    }
    setEditingHtml(true);
    setPanel('pages');
  };
  return <ThemeProvider colorScheme={colorScheme} className="sm-library-theme">
    <style>{css}</style>
    <main className="sm-library-workspace" data-testid="library-workspace" aria-busy={state.busy}
      onFocusCapture={event => { lastFocused.current = event.target; }}>
      <aside className="sm-library-rail">
        <h1 tabIndex={-1} ref={heading}>资料库</h1>
        <nav className="sm-library-nav" aria-label="驾驶舱页面">
          <button type="button" aria-pressed={panel === 'pages'} data-testid="library-panel-pages"
            onClick={() => { setEditingHtml(false); setPanel('pages'); }}>本地产物</button>
          <button type="button" aria-pressed={panel === 'board'} data-testid="library-panel-board"
            onClick={() => setPanel('board')}>我的驾驶舱</button>
          {actionsEnabled ? <button type="button" aria-pressed={panel === 'actions'} data-testid="analytics-competition-actions"
            onClick={() => { setVisitedActions(true); setPanel('actions'); }}>人群行动</button> : null}
        </nav>
        <CockpitProductsView items={products} busy={state.busy} query={query} selectedId={selectedId}
          onQuery={setQuery} onRefresh={refreshProducts} onOpen={openProduct} showSearch={panel === 'pages'} />
        <div className="sm-library-rail-foot">
          <button type="button" onClick={goConversation}>返回原生对话</button>
        </div>
      </aside>
      <div className="sm-library-canvas">
      {state.message ? <p role="status" aria-live="polite" data-testid="library-message">{state.message}</p> : null}
      {boardChrome && state.incoming ? <div className="sm-library-banner" role="group" aria-label="处理未确认草稿">
        <p>{state.confirmationUncertain ? '保存结果待核对。切换前可尝试取消尚未应用的草稿；已保存内容需通过回退处理。' : '切换前，是否取消当前未确认草稿？'}</p>
        <div className="sm-library-actions">
          <button type="button" disabled={state.busy} onClick={() => library.keepDraft()}>继续检查当前草稿</button>
          <button type="button" disabled={state.busy} onClick={() => { void library.discardAndNavigate(); }}>{state.confirmationUncertain ? '尝试取消草稿并切换' : '取消草稿并切换'}</button>
        </div>
      </div> : null}
      {boardChrome && state.preview ? <div className="sm-library-banner" data-testid="library-preview-banner" ref={previewBanner}>
        <p>{{ ROLLBACK: '回退预览', LAYOUT: '布局预览', PATCH: '组件修改预览', GENERATE: '生成预览' }[state.preview.operation]} · v{state.preview.snapshot.spec.version} · {state.confirmationUncertain
          ? '保存结果待核对。可能已写入服务端；请核对状态，或重试同一次保存。取消草稿不会撤销已保存内容。'
          : '尚未保存。请检查下方内容和出处。'}</p>
        <EditDiff state={state} />
        <div className="sm-library-actions">
          {state.confirmationUncertain ? <button type="button" disabled={state.busy} data-testid="library-inspect-confirmation" ref={recovery}
            onClick={() => { void library.inspectConfirmation(); }}>核对保存结果</button> : null}
          <button type="button" disabled={state.busy} data-testid="library-cancel" onClick={() => { void library.cancel(); }}>{state.confirmationUncertain ? '尝试取消未应用草稿' : '取消，保留已保存版本'}</button>
          <button type="button" className="sm-library-confirm" disabled={state.busy} data-testid="library-confirm"
            onClick={() => { void library.confirm(); }}>{state.busy ? '处理中…' : state.confirmationUncertain ? '重试这次保存' : '确认保存这份看板'}</button>
        </div>
      </div> : null}
      {boardChrome && state.editContext && !state.preview ? <div className="sm-library-banner" data-testid="library-edit-banner">
        <p>已选中「{state.editContext.block.title}」· 基于 v{state.editContext.base_version}。请在原生对话描述修改要求；当前内容尚未改变。</p>
        <div className="sm-library-actions">
          <button type="button" disabled={state.busy} onClick={() => { void library.resumeEdit(); }}>转到原生对话描述修改</button>
          <button type="button" disabled={state.busy} onClick={() => { void library.inspectEdit(); }}>检查 AI 修改预览</button>
          <button type="button" disabled={state.busy} onClick={() => { void library.cancel(); }}>取消组件编辑</button>
        </div>
      </div> : null}
      {boardChrome && state.layoutDraft ? <div className="sm-library-banner" aria-label="布局编辑" data-testid="library-layout-banner">
        <p>布局编辑中 · 仅修改位置和尺寸，不改数据。检查后还需确认保存。</p>
        <div className="sm-library-actions">
          <button type="button" disabled={state.busy} data-testid="layout-cancel" onClick={() => { void library.cancel(); }}>取消布局调整</button>
          <button type="button" disabled={state.busy} data-testid="layout-preview" onClick={() => { void library.previewLayout(); }}>检查布局</button>
        </div>
      </div> : null}
      <div className="sm-library-pathbar" data-testid="library-pathbar">
        <span>{selected ? <>我的资料 / <strong>{selected.title}</strong></> : '我的资料'}</span>
        {selected && (editingHtml || selected.kind === 'html' || panel === 'board')
          ? <button type="button" data-testid="library-products-back" onClick={() => { setEditingHtml(false); setSelectedId(null); setFilePreview(''); setPanel('pages'); }}>关闭</button>
          : null}
      </div>
      <section hidden={panel !== 'pages'} data-testid="library-pages-view" className="sm-library-document">
        {panel === 'pages' && selected?.kind === 'html' && !editingHtml
          ? <div className="sm-library-ai-bar" data-testid="library-ai-bar" role="toolbar" aria-label="AI 编辑">
            <button type="button" data-testid="library-product-edit" onClick={() => editHtml(selected)}>AI 编辑</button>
          </div>
          : null}
        {panel === 'pages' && selected?.kind === 'html' && (editingHtml || selected.page_id)
          ? <FreeHtmlLibraryApp goConversation={goConversation} themeSource={themeSource}
            store={pageStore} hostOwnsConversationLeave={Boolean(pageStore)} />
          : null}
        {panel === 'pages' && selected?.kind === 'html' && !editingHtml && !selected.page_id && filePreview
          ? <iframe title={selected.title} data-testid="library-html-preview" srcDoc={asSrcDoc(filePreview)} sandbox="allow-scripts" />
          : null}
        {panel === 'pages' && selected && selected.kind !== 'html'
          ? <p className="sm-library-empty">表格和 PDF 在官方预览中打开，不改上游壳。</p>
          : null}
        {panel === 'pages' && !(selected?.kind === 'html' && (editingHtml || selected.page_id || filePreview)) && (!selected || selected.kind === 'html')
          ? <p className="sm-library-empty" data-testid="library-canvas-empty">对话里生成的页面会出现在左侧。点开 HTML 后整页预览，再用 AI 编辑。</p>
          : null}
      </section>
      <section hidden={panel !== 'board'} data-testid="library-board-view" className="sm-library-document">
      <div className="sm-library-toolbar">
        <button type="button" disabled={state.busy} onClick={() => { void library.refresh(); }}>刷新已保存看板</button>
      </div>
      <label>已保存看板　<select aria-label="打开已保存看板" disabled={state.busy} value={state.saved?.spec.board_id ?? ''}
        onChange={event => { if (event.target.value) void library.openBoard(event.target.value); }}>
        <option value="">请选择看板</option>
        {state.boards.map(board => <option key={board.board_id} value={board.board_id}>{board.title} · v{board.version}</option>)}
      </select></label>
      {shown ? <><p>v{shown.spec.version} · {state.preview ? state.confirmationUncertain ? '保存结果待核对' : '待确认草稿' : state.layoutDraft ? '本地布局草稿' : '服务端已保存快照'} · 数据为合成验证来源</p>
        <LibraryLayoutCanvas key={shown.spec.board_id} snapshot={shown} editing={Boolean(state.layoutDraft)} disabled={state.busy}
          updateLayout={library.updateLayout} selectedBlockId={state.editContext?.block_id}
          selectBlock={!state.preview && !state.layoutDraft ? blockId => { void library.beginEdit(blockId); } : undefined} /></> : <p>问数后，在原生对话生成驾驶舱；已保存的看板不依赖模型在线。</p>}
      {state.saved && !state.preview && !state.layoutDraft && !state.editContext ? <div className="sm-library-actions">
        <button type="button" disabled={state.busy} data-testid="layout-start" onClick={() => library.beginLayout()}>调整布局</button>
        <button type="button" disabled={state.busy} onClick={() => { void library.loadHistory(); }}>查看历史版本</button>
        {state.history.map(version => <button type="button" key={version.version}
          disabled={state.busy || version.version >= state.saved!.spec.version}
          onClick={() => { void library.rollback(version.version); }}>预览回退到 v{version.version}</button>)}
      </div> : null}
      </section>
      {actionsEnabled && (panel === 'actions' || visitedActions) ? <section hidden={panel !== 'actions'} data-panel="competition-actions"
        data-testid="analytics-competition-actions-view">
        <OverlayErrorBoundary resetKey="library-actions">
          <ActionsWorkbench modelAvailable={false} />
        </OverlayErrorBoundary>
      </section> : null}
      </div>
    </main>
  </ThemeProvider>;
}

export function GenerateChipIcon() {
  return <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <rect x="1.75" y="2.625" width="10.5" height="8.75" rx="1.75" stroke="currentColor" strokeWidth="1.225" />
    <path d="M1.75 5.25h10.5" stroke="currentColor" strokeWidth="1.225" />
  </svg>;
}

export function LibraryGenerateDock({ sessionId, generate }: { sessionId: string; generate(sessionId: string): Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const generation = useRef(0);
  useEffect(() => {
    setBusy(false); setMessage('');
    return () => { generation.current++; };
  }, [sessionId]);
  return <div className="analytics-b0-artifacts" data-testid="library-generate-dock">
    <button type="button" className="analytics-b0-generate-dock" disabled={busy} aria-label="生成驾驶舱" onClick={() => {
      setBusy(true); setMessage('');
      const requestGeneration = ++generation.current;
      void generate(sessionId).then(() => {
        if (generation.current === requestGeneration) setMessage('已交给当前原生对话生成，结果会出现在工具卡。');
      }).catch(() => {
        if (generation.current === requestGeneration) setMessage('未能提交生成请求；请在当前原生对话输入“生成驾驶舱”。');
      }).finally(() => { if (generation.current === requestGeneration) setBusy(false); });
    }}><GenerateChipIcon />生成驾驶舱</button>
    <span role="status">{message}</span>
  </div>;
}

export function LibraryPreviewToolCard(props: ToolCallViewProps & { library?: LibraryBoardClient; openCockpit?(): boolean }) {
  const block = props.block;
  if (!('kind' in block) || block.kind !== 'tool-result') return <p role="status">正在生成驾驶舱草稿…</p>;
  const meta = block.meta as Record<string, unknown> | undefined;
  if (block.isError || meta?.schema_version !== 'board-tool-result/v1' || meta.status !== 'PREVIEW_READY'
    || typeof meta.preview_id !== 'string' || meta.published !== false) {
    return <p role="status">未生成可确认的看板草稿，请查看原生对话中的原因。</p>;
  }
  return <div data-testid="library-preview-tool-card">
    <p>{String(meta.title ?? '驾驶舱')} · {String(meta.component_count)} 个组件 · 尚未保存</p>
    <button type="button" disabled={!props.library} onClick={() => {
      void props.library?.openPreview(meta.preview_id as string, typeof meta.edit_context_id === 'string' ? meta.edit_context_id : undefined);
      props.openCockpit?.();
    }}>打开预览，检查后确认</button>
  </div>;
}
