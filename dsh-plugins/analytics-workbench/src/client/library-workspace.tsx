import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import { LibraryLayoutCanvas } from './library-layout-canvas.tsx';
import type { LibraryBoardClient, LibraryState } from './library-board-client.mjs';
import { ThemeProvider } from './competition-shell/index.ts';
import type { CompetitionColorScheme } from './competition-shell/tokens.ts';
import { FreeHtmlLibraryApp } from './free-html-library/FreeHtmlLibraryApp.tsx';
import { HtmlHoverLayer } from './HtmlHoverLayer.tsx';
import { htmlWithHoverRuntime } from './html-hover-layer.mjs';
import { mergeCockpitProducts, type CockpitProduct } from './cockpit-products.mjs';
import { CockpitSidebar } from './CockpitSidebar.tsx';
import { FREE_PAGE_CSP, FREE_PAGE_REFERRER_POLICY, FREE_PAGE_SANDBOX } from '../free-page/runtime/isolation-policy.mjs';
import './cockpit-theme.css';

const KIND_LABEL = { html: 'HTML', spreadsheet: 'CSV', pdf: 'PDF', board: '看板' };
const TREE_GROUPS = [
  { key: 'html', label: 'HTML' },
  { key: 'board', label: '看板' },
  { key: 'csv', label: 'CSV' },
  { key: 'sheet', label: '表格' },
] as const;

function treeBucket(item: CockpitProduct) {
  if (item.kind === 'html') return 'html';
  if (item.kind === 'board') return 'board';
  if (item.kind !== 'spreadsheet') return null;
  const name = String(item.path ?? item.title ?? '');
  return /\.csv$/i.test(name) ? 'csv' : 'sheet';
}

function pathKindLabel(item: CockpitProduct) {
  const bucket = treeBucket(item);
  if (bucket === 'board') return '看板';
  if (bucket === 'html') return 'HTML';
  if (bucket === 'csv') return 'CSV';
  if (bucket === 'sheet') return '表格';
  if (item.kind === 'pdf') return 'PDF';
  return item.kind;
}

function previewCancelLabel(preview: LibraryState['preview'], uncertain: boolean) {
  if (uncertain) return '尝试取消未应用草稿';
  if (preview?.operation === 'LAYOUT') return '返回调整';
  return '取消，保留已保存版本';
}

function previewConfirmLabel(busy: boolean, uncertain: boolean, operation: string) {
  if (busy) return '处理中…';
  if (uncertain) return '重试这次保存';
  if (operation === 'LAYOUT') return '确认保存';
  return '确认保存这份看板';
}

function previewStatusLine(preview: NonNullable<LibraryState['preview']>, uncertain: boolean) {
  const op = preview.operation === 'ROLLBACK' ? '回退预览'
    : preview.operation === 'LAYOUT' ? '布局已通过检查'
    : preview.operation === 'PATCH' ? '组件修改预览'
    : '生成预览';
  return uncertain ? `${op} · 保存结果待核对` : `${op} · 尚未保存`;
}

function groupTestId(key: string) {
  if (key === 'html') return 'library-panel-pages';
  if (key === 'board') return 'library-panel-board';
  return `library-panel-${key}`;
}

function groupPressed(key: string, panel: 'pages' | 'board') {
  if (key === 'html') return panel === 'pages';
  if (key === 'board') return panel === 'board';
  return false;
}

function pathbarCopy(
  selected: CockpitProduct | null,
  panel: 'pages' | 'board',
  shown: { spec: { title: string } } | null,
) {
  if (selected) return { title: selected.title, trail: `本会话 / ${pathKindLabel(selected)}` };
  if (panel === 'board' && shown) return { title: shown.spec.title, trail: '本会话 / 看板' };
  if (panel === 'board') return { title: null, trail: '本会话 / 看板' };
  return { title: null, trail: '产物文件夹' };
}

function initialLibraryPanel(library: LibraryBoardClient, initialSurface: 'pages' | 'board') {
  const snap = library.getSnapshot();
  if (snap.preview || snap.layoutDraft || snap.saved) return 'board';
  return initialSurface;
}
const EMPTY_PAGES: Array<{ page_id?: string; title?: string; version?: number }> = [];
const emptyPageSnap = {
  subscribe: (_listener: () => void) => () => {},
  getSnapshot: () => EMPTY_PAGES,
};

const css = `
.sm-library-workspace { --lib-rail:#f7f7f7; --lib-canvas:#fff; --lib-ink:#171717; --lib-muted:#737373; --lib-line:#e8e8e8; --lib-active:#fff; min-width:0; min-height:100%; height:100%; display:grid; grid-template-columns:300px minmax(0,1fr); grid-template-rows:auto minmax(0,1fr); background:var(--lib-rail); color:var(--lib-ink); font-family:var(--sm-font-body); }
.sm-library-workspace > header.sm-library-pagehead { grid-column:1 / -1; grid-row:1; display:flex; align-items:center; justify-content:space-between; gap:12px; height:56px; padding:0 24px; background:#fff; border-bottom:1px solid var(--lib-line); }
.sm-library-workspace > header.sm-library-pagehead h1 { margin:0; font:500 18px/25px var(--sm-font-body); color:var(--lib-ink); }
.sm-library-workspace button.cockpit-back-btn, .sm-library-workspace button.cockpit-edit-btn { display:inline-flex; align-items:center; gap:8px; min-height:32px; padding:6px 12px; background:#fff; color:var(--lib-ink); border:1px solid var(--lib-line); border-radius:6px; font:400 14px/20px var(--sm-font-body); cursor:pointer; }
.sm-library-workspace button.cockpit-back-btn:hover, .sm-library-workspace button.cockpit-edit-btn:hover { background:var(--lib-line); }
.sm-library-workspace button.cockpit-edit-btn.active { color:#ff6b35; border-color:#ff6b35; }
.library-cockpit-main { display:flex; flex:1; min-width:0; min-height:0; align-items:stretch; }
.library-content-area { flex:1 1 auto; min-width:0; min-height:0; display:flex; flex-direction:column; }
.cockpit-sidebar { box-sizing:border-box; flex:0 0 320px; width:320px; max-width:320px; align-self:stretch; min-height:0; background:var(--lib-rail); border-left:1px solid var(--lib-line); display:flex; flex-direction:column; z-index:10; overflow:hidden; }
.cockpit-sidebar-header { display:flex; justify-content:flex-end; align-items:center; height:48px; padding:0 16px; border-bottom:1px solid var(--lib-line); }
.sm-library-workspace button.cockpit-sidebar-close { width:32px; height:32px; min-height:0; padding:0; display:flex; align-items:center; justify-content:center; background:transparent; border:none; border-radius:4px; color:var(--lib-ink); font-size:20px; line-height:1; cursor:pointer; }
.cockpit-sidebar-body { flex:1; padding:16px; overflow-y:auto; }
.cockpit-sidebar-footer { padding:16px; border-top:1px solid var(--lib-line); }
.cockpit-sidebar-placeholder { margin:0; color:var(--lib-muted); font-size:12px; text-align:center; line-height:1.5; }
.cockpit-sidebar-tools { display:flex; flex-direction:column; gap:8px; }
.cockpit-sidebar-tools button { width:100%; min-height:36px; padding:8px 12px; text-align:left; }
.sm-library-rail { grid-column:1; grid-row:2; min-width:0; min-height:0; display:flex; flex-direction:column; gap:4px; padding:12px; border-right:1px solid var(--lib-line); background:var(--lib-rail); }
.sm-library-rail-title { margin:0 0 4px; font:500 16px/22px var(--sm-font-body); }
.sm-library-products li[data-selected="1"] button { background:var(--lib-active); }
.sm-library-canvas { grid-column:2; grid-row:2; min-width:0; min-height:0; display:flex; flex-direction:column; background:var(--lib-canvas); }
.sm-library-pathbar { display:flex; gap:8px; align-items:center; min-height:44px; padding:0 16px; border-bottom:1px solid var(--lib-line); font-size:13px; color:var(--lib-muted); }
.sm-library-pathbar strong { color:var(--lib-ink); font-weight:500; }
.sm-library-pathbar span { margin-right:auto; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.sm-library-document { position:relative; flex:1; min-height:0; overflow:auto; }
.sm-library-document iframe, .sm-library-document [data-testid="fhl-live-preview"] { display:block; width:100%; height:100%; min-height:560px; border:0; background:#fff; }
.library-html-container { position:relative; flex:1; min-height:0; display:flex; flex-direction:column; }
.library-html-iframe { display:block; width:100%; height:100%; min-height:560px; border:0; background:#fff; }
.sm-library-document [data-testid="fhl-root"] { min-height:100%; }
.sm-library-document [data-testid="fhl-root"] > header, .sm-library-document [data-testid="fhl-status-spine"], .sm-library-document [data-testid="fhl-home"], .sm-library-document [data-testid="fhl-skip-iframe"], .sm-library-document .sm-fhl-workspace-heading, .sm-library-document [data-testid="fhl-workspace"] > .sm-fhl-toolbar { display:none; }
.sm-library-empty { margin:48px auto; max-width:360px; color:var(--lib-muted); text-align:center; }
.sm-library-toolbar,.sm-library-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.sm-library-workspace p { margin:0; }
[data-testid="library-board-view"] p { color:var(--lib-muted); }
.sm-library-workspace button:not(.ant-btn):not(.cockpit-back-btn):not(.cockpit-edit-btn):not(.cockpit-sidebar-close),.sm-library-workspace select { font:inherit; color:inherit; background:transparent; border:1px solid var(--lib-line); border-radius:8px; padding:6px 10px; cursor:pointer; }
.sm-library-workspace button:not(.ant-btn):disabled { opacity:.5; cursor:not-allowed; }
.sm-library-workspace button:not(.ant-btn):focus-visible,.sm-library-workspace select:focus-visible,.sm-library-workspace [tabindex]:focus-visible { outline:2px solid var(--lib-ink); outline-offset:2px; }
.sm-library-workspace .sm-library-confirm { background:var(--lib-ink); color:#fff; border-color:var(--lib-ink); }
.sm-library-banner { margin:0; padding:8px 16px; border:0; border-bottom:1px solid var(--lib-line); display:flex; flex-wrap:wrap; gap:8px; align-items:center; background:#fff; }
.sm-library-banner p { color:var(--lib-muted); font-size:12px; margin-right:auto; max-width:42em; }
.sm-library-products { display:flex; flex-direction:column; gap:4px; min-height:0; flex:1; }
.sm-library-products-hint { color:var(--lib-muted); font-size:12px; padding:0 8px 8px; }
.sm-library-rail-section { display:flex; align-items:center; justify-content:space-between; padding:8px 8px 4px; color:var(--lib-muted); font-size:12px; }
.sm-library-tree-group { display:flex; flex-direction:column; gap:2px; padding:4px 0; }
.sm-library-tree-toggle { width:100%; display:flex; gap:8px; align-items:center; border:0; background:transparent; border-radius:8px; padding:6px 8px; text-align:left; font:500 13px/18px var(--sm-font-body); }
.sm-library-tree-toggle[aria-pressed="true"] { background:var(--lib-active); }
.sm-library-tree-count { margin-left:auto; color:var(--lib-muted); font:400 12px/17px var(--sm-font-body); }
.sm-library-products ul { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:2px; }
.sm-library-products li button { width:100%; display:flex; gap:8px; align-items:center; border:0; background:transparent; border-radius:8px; padding:8px 8px 8px 28px; text-align:left; font:400 13px/18px var(--sm-font-body); overflow:hidden; }
.sm-library-products li[data-selected="1"] button { background:var(--lib-active); }
.sm-library-products li button span { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.sm-library-products li button [data-testid="library-product-kind"] { display:none; }
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

function neutralizeWrapperBreakout(html: string) {
  return String(html)
    .replace(/<\/(?=html|head|body)\b/gi, '&lt;/')
    .replace(/<meta\b/gi, '&lt;meta');
}

function asSrcDoc(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return '';
  const csp = `<meta http-equiv="Content-Security-Policy" content="${FREE_PAGE_CSP}">`;
  return htmlWithHoverRuntime(
    `<!doctype html><html><head><meta charset="utf-8">${csp}</head><body>${neutralizeWrapperBreakout(trimmed)}</body></html>`,
  );
}

function ProductFolderTree({ items, selectedId, expanded, panel, onOpen, onToggle }: {
  items: CockpitProduct[];
  selectedId: string | null;
  expanded: Record<string, boolean>;
  panel: 'pages' | 'board';
  onOpen(item: CockpitProduct): void;
  onToggle(key: string): void;
}) {
  const visible = items.filter(item => treeBucket(item));
  const groups = TREE_GROUPS.filter(group => group.key !== 'sheet' || visible.some(item => treeBucket(item) === 'sheet'));
  return (
    <div className="sm-library-products" data-testid="library-products">
      <p className="sm-library-products-hint">本会话 · HTML / 看板 / CSV</p>
      <div className="sm-library-rail-section">
        <span>产物</span>
      </div>
      {visible.length === 0
        ? <p data-testid="library-products-empty">还没有产物。</p>
        : (
          <div data-testid="library-products-list">
            {groups.map(group => {
              const kids = visible.filter(item => treeBucket(item) === group.key);
              const open = Boolean(expanded[group.key]);
              const testId = groupTestId(group.key);
              const pressed = groupPressed(group.key, panel);
              return (
                <div key={group.key} className="sm-library-tree-group">
                  <button type="button" className="sm-library-tree-toggle" data-testid={testId}
                    aria-expanded={open} aria-pressed={pressed} onClick={() => onToggle(group.key)}>
                    <span aria-hidden="true">{open ? '▼' : '▶'}</span>
                    <span>{group.label}</span>
                    <span className="sm-library-tree-count">{kids.length}</span>
                  </button>
                  <ul hidden={!open}>
                    {kids.map(item => (
                      <li key={item.id} data-kind={item.kind} data-selected={selectedId === item.id ? '1' : '0'}>
                        <button type="button" data-testid="library-product-open" aria-current={selectedId === item.id}
                          onClick={() => onOpen(item)}>
                          <span>{item.title}</span>
                          <span data-testid="library-product-kind">{KIND_LABEL[item.kind as keyof typeof KIND_LABEL] ?? item.kind}</span>
                          {item.subtitle ? <span>{item.subtitle}</span> : null}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
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
  const [panel, setPanel] = useState<'pages' | 'board'>(() => initialLibraryPanel(library, initialSurface));
  const [workspaceFiles, setWorkspaceFiles] = useState<Array<Record<string, unknown>>>([]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState('');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ html: true, board: true, csv: false, sheet: false });
  const [editMode, setEditMode] = useState(false);
  const previewSeq = useRef(0);
  const htmlIframeRef = useRef<HTMLIFrameElement>(null);
  const pageList = useSyncExternalStore(
    pageStore ? pageStore.subscribe : emptyPageSnap.subscribe,
    () => (pageStore ? pageStore.getSnapshot().pages : EMPTY_PAGES),
  );
  useEffect(() => { void library.refresh(); }, [library]);
  const refreshProducts = () => {
    if (typeof listWorkspaceFiles !== 'function') { setWorkspaceFiles([]); return; }
    void listWorkspaceFiles().then(items => setWorkspaceFiles(Array.isArray(items) ? items : [])).catch(() => setWorkspaceFiles([]));
  };
  useEffect(() => { refreshProducts(); }, [listWorkspaceFiles]);
  useEffect(() => {
    if (!editMode) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (state.layoutDraft || state.preview) return;
      setEditMode(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [editMode, state.layoutDraft, state.preview]);
  useEffect(() => { heading.current?.focus(); }, [state.preview?.preview_id, state.saved?.spec.board_id]);
  useEffect(() => {
    if (!state.layoutDraft) return;
    const canvas = heading.current?.ownerDocument?.querySelector('.sm-layout-scroll');
    if (canvas instanceof HTMLElement) canvas.focus();
  }, [Boolean(state.layoutDraft)]);
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
  const boardChrome = panel !== 'pages';
  const products = mergeCockpitProducts({ files: workspaceFiles, boards: state.boards, pages: pageList });
  const selected = products.find(item => item.id === selectedId) ?? null;
  const openProduct = (item: CockpitProduct) => {
    setSelectedId(item.id);
    setFilePreview('');
    if (item.kind === 'board' && item.board_id) {
      void library.openBoard(item.board_id);
      setPanel('board');
      setExpanded(current => ({ ...current, board: true }));
      return;
    }
    setPanel('pages');
    const bucket = treeBucket(item);
    setExpanded(current => ({ ...current, html: bucket === 'html' ? true : current.html, csv: bucket === 'csv' ? true : current.csv, sheet: bucket === 'sheet' ? true : current.sheet }));
    if (item.page_id && pageStore) {
      void pageStore.openPage(item.page_id);
      return;
    }
    if (item.kind === 'html') {
      const seq = ++previewSeq.current;
      if (readWorkspaceFile) {
        void readWorkspaceFile(item).then(text => {
          if (seq !== previewSeq.current) return;
          setFilePreview(typeof text === 'string' ? text : '');
        }).catch(() => {
          if (seq !== previewSeq.current) return;
          setFilePreview('');
        });
      }
      return;
    }
    openWorkspaceFile?.(item);
  };
  useEffect(() => {
    if (selectedId) return;
    if (shown) {
      setPanel('board');
      return;
    }
    const firstHtml = products.find(item => treeBucket(item) === 'html');
    if (firstHtml) openProduct(firstHtml);
  }, [selectedId, shown, workspaceFiles, state.boards, pageList]);
  const path = pathbarCopy(selected, panel, shown);
  return <ThemeProvider colorScheme={colorScheme} className="sm-library-theme">
    <style>{css}</style>
    <main className="sm-library-workspace" data-testid="library-workspace" aria-busy={state.busy}
      onFocusCapture={event => { lastFocused.current = event.target; }}>
      <header className="sm-library-pagehead cockpit-header" data-testid="sm-library-pagehead">
        <button type="button" className="cockpit-back-btn" data-testid="sm-cockpit-back" onClick={goConversation}>
          <span aria-hidden="true">←</span>
          返回对话
        </button>
        <h1 tabIndex={-1} ref={heading} className="cockpit-header-title">驾驶舱</h1>
        <button
          type="button"
          className={editMode ? 'cockpit-edit-btn active' : 'cockpit-edit-btn'}
          data-testid="cockpit-edit-btn"
          aria-pressed={editMode}
          onClick={() => setEditMode(open => !open)}
        >
          {editMode ? '退出编辑' : '编辑'}
        </button>
      </header>
      <aside className="sm-library-rail">
        <p className="sm-library-rail-title">产物文件夹</p>
        <ProductFolderTree items={products} selectedId={selectedId} expanded={expanded} panel={panel}
          onOpen={openProduct} onToggle={key => {
            setExpanded(current => ({ ...current, [key]: !current[key] }));
            if (key === 'board') setPanel('board');
            if (key === 'html') setPanel('pages');
          }} />
      </aside>
      <div className="sm-library-canvas">
      {state.message ? <p role="status" aria-live="polite" data-testid="library-message">{state.message}</p> : null}
      {boardChrome && state.incoming ? <div className="sm-library-banner" role="group" aria-label="处理未确认草稿">
        <p>{state.confirmationUncertain ? '保存结果待核对。可留下检查，或取消未应用草稿。' : '有未确认草稿。留下检查，或取消后切换。'}</p>
        <div className="sm-library-actions">
          <button type="button" disabled={state.busy} onClick={() => library.keepDraft()}>留下</button>
          <button type="button" disabled={state.busy} onClick={() => { void library.discardAndNavigate(); }}>{state.confirmationUncertain ? '尝试取消并切换' : '取消并切换'}</button>
        </div>
      </div> : null}
      {boardChrome && state.preview ? <div className="sm-library-banner" data-testid="library-preview-banner" ref={previewBanner}>
        <p>{previewStatusLine(state.preview, state.confirmationUncertain)}</p>
        <EditDiff state={state} />
        <div className="sm-library-actions">
          {state.confirmationUncertain ? <button type="button" disabled={state.busy} data-testid="library-inspect-confirmation" ref={recovery}
            onClick={() => { void library.inspectConfirmation(); }}>核对保存结果</button> : null}
          <button type="button" disabled={state.busy} data-testid="library-cancel" onClick={() => { void library.cancel(); }}>{previewCancelLabel(state.preview, state.confirmationUncertain)}</button>
          <button type="button" className="sm-library-confirm" disabled={state.busy} data-testid="library-confirm"
            onClick={() => { void library.confirm(); }}>{previewConfirmLabel(state.busy, state.confirmationUncertain, state.preview.operation)}</button>
        </div>
      </div> : null}
      {boardChrome && state.layoutDraft ? <div className="sm-library-banner" aria-label="布局编辑" data-testid="library-layout-banner">
        <p>布局编辑中 · 只改位置和尺寸，不改数字</p>
        <div className="sm-library-actions">
          <button type="button" disabled={state.busy} data-testid="layout-cancel" onClick={() => { void library.cancel(); }}>取消</button>
          <button type="button" className="sm-library-confirm" disabled={state.busy} data-testid="layout-preview" onClick={() => { void library.previewLayout(); }}>检查布局</button>
        </div>
      </div> : null}
      <div className="sm-library-pathbar" data-testid="library-pathbar">
        <span>{path.title ? <><strong>{path.title}</strong> {path.trail}</> : path.trail}</span>
      </div>
      <div className="library-cockpit-main">
      <div
        className="library-content-area"
        data-testid="library-content-area"
        style={{
          flex: 1,
          minWidth: 0,
          minHeight: 0,
          transition: 'width 300ms ease-out',
          width: editMode ? 'calc(100% - 320px)' : '100%',
        }}
      >
      <section hidden={panel !== 'pages'} data-testid="library-pages-view" className="sm-library-document">
        {panel === 'pages' && selected?.kind === 'html' && selected.page_id
          ? <FreeHtmlLibraryApp goConversation={goConversation} themeSource={themeSource}
            store={pageStore} hostOwnsConversationLeave={Boolean(pageStore)} editMode={editMode} />
          : null}
        {panel === 'pages' && selected?.kind === 'html' && !selected.page_id && filePreview
          ? <div className="library-html-container">
            <iframe ref={htmlIframeRef} title={selected.title} data-testid="library-html-preview" className="library-html-iframe"
              srcDoc={asSrcDoc(filePreview)} sandbox={FREE_PAGE_SANDBOX} referrerPolicy={FREE_PAGE_REFERRER_POLICY} />
            {editMode ? <HtmlHoverLayer iframeRef={htmlIframeRef} editMode={editMode} /> : null}
          </div>
          : null}
        {panel === 'pages' && selected && selected.kind !== 'html'
          ? <p className="sm-library-empty">表格和 PDF 在官方预览中打开，不改上游壳。</p>
          : null}
        {panel === 'pages' && !(selected?.kind === 'html' && (selected.page_id || filePreview)) && (!selected || selected.kind === 'html')
          ? <p className="sm-library-empty" data-testid="library-canvas-empty">还没有页面。</p>
          : null}
      </section>
      <section hidden={panel !== 'board'} data-testid="library-board-view" className="sm-library-document">
      {shown ? <LibraryLayoutCanvas key={shown.spec.board_id} snapshot={shown} editing={Boolean(state.layoutDraft)} disabled={state.busy}
        updateLayout={library.updateLayout} />
        : <p className="sm-library-empty" data-testid="library-board-empty">还没有看板。</p>}
      </section>
      </div>
      <CockpitSidebar visible={editMode} onClose={() => setEditMode(false)} busy={state.busy}
        showBoardTools={panel === 'board' && Boolean(state.saved) && !state.preview && !state.layoutDraft}
        onLayout={() => library.beginLayout()} onRollback={() => { void library.rollbackPrevious(); }} />
      </div>
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
