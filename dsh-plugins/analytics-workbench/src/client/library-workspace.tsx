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

function groupTestId(key: string) {
  if (key === 'html') return 'library-panel-pages';
  if (key === 'board') return 'library-panel-board';
  return `library-panel-${key}`;
}

function groupPressed(key: string, panel: 'pages' | 'board' | 'actions') {
  if (key === 'html') return panel === 'pages';
  if (key === 'board') return panel === 'board';
  return false;
}

function pathbarCopy(
  selected: CockpitProduct | null,
  panel: 'pages' | 'board' | 'actions',
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
.sm-library-pagehead { grid-column:1 / -1; display:flex; align-items:center; gap:12px; padding:16px 24px 12px; background:#fff; }
.sm-library-pagehead h1 { margin:0; font:500 18px/25px var(--sm-font-body); }
.sm-library-back { min-height:24px; border:1px solid #1677ff; background:#fff; color:#1677ff; border-radius:4px; padding:0 7px; font:400 14px/22px var(--sm-font-body); cursor:pointer; }
.sm-library-rail { grid-column:1; grid-row:2; min-width:0; min-height:0; display:flex; flex-direction:column; gap:4px; padding:12px; border-right:1px solid var(--lib-line); background:var(--lib-rail); }
.sm-library-rail-title { margin:0 0 4px; font:500 16px/22px var(--sm-font-body); }
.sm-library-search { display:flex; flex-direction:column; gap:4px; margin:0 4px 8px; color:var(--lib-muted); font-size:12px; }
.sm-library-search input { width:100%; min-height:32px; border:0; border-radius:8px; padding:6px 10px; background:#ececee; color:var(--lib-ink); font:inherit; }
.sm-library-nav { display:flex; flex-direction:column; gap:2px; margin:0 0 8px; }
.sm-library-nav button { justify-content:flex-start; min-height:32px; border:0; background:transparent; color:var(--lib-ink); border-radius:8px; padding:6px 10px; font:400 13px/18px var(--sm-font-body); }
.sm-library-nav button[aria-pressed="true"], .sm-library-products li[data-selected="1"] button { background:var(--lib-active); }
.sm-library-rail-foot { margin-top:auto; padding:8px 4px 0; }
.sm-library-canvas { grid-column:2; grid-row:2; min-width:0; min-height:0; display:flex; flex-direction:column; background:var(--lib-canvas); }
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
.sm-library-workspace button:not(.ant-btn):focus-visible,.sm-library-workspace select:focus-visible,.sm-library-workspace [tabindex]:focus-visible,.sm-library-search input:focus-visible { outline:2px solid var(--lib-ink); outline-offset:2px; }
.sm-library-workspace button.sm-library-back { border-color:#1677ff; color:#1677ff; background:#fff; min-height:24px; padding:0 7px; border-radius:4px; font:400 14px/22px var(--sm-font-body); }
.sm-library-workspace .sm-library-confirm { background:var(--lib-ink); color:#fff; border-color:var(--lib-ink); }
.sm-library-banner { margin:0; padding:12px 24px; border:0; border-bottom:1px solid var(--lib-line); display:flex; flex-wrap:wrap; gap:12px; align-items:center; background:#fff; }
.sm-library-banner p { color:var(--lib-muted); font-size:12px; margin-right:auto; }
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
.sm-library-edit { position:relative; margin-left:auto; }
.sm-library-edit > button { min-height:32px; }
.sm-library-edit-menu { position:absolute; right:0; top:calc(100% + 6px); z-index:4; width:220px; padding:6px; background:#fff; border:1px solid var(--lib-line); border-radius:10px; box-shadow:0 4px 12px rgba(0,0,0,.12); }
.sm-library-edit-menu button { width:100%; display:flex; flex-direction:column; align-items:flex-start; gap:2px; border:0; background:transparent; border-radius:8px; padding:8px 10px; text-align:left; }
.sm-library-edit-menu button:hover { background:#f4f4f4; }
.sm-library-edit-menu small { color:var(--lib-muted); font-size:11px; font-weight:400; }
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

function ProductFolderTree({ items, busy, selectedId, expanded, panel, onRefresh, onOpen, onToggle }: {
  items: CockpitProduct[];
  busy: boolean;
  selectedId: string | null;
  expanded: Record<string, boolean>;
  panel: 'pages' | 'board' | 'actions';
  onRefresh(): void;
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
        <button type="button" data-testid="library-products-refresh" disabled={busy} onClick={onRefresh}>刷新</button>
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
  const [panel, setPanel] = useState<'pages' | 'board' | 'actions'>(() => initialLibraryPanel(library, initialSurface));
  const [visitedActions, setVisitedActions] = useState(false);
  const [workspaceFiles, setWorkspaceFiles] = useState<Array<Record<string, unknown>>>([]);
  const [editingHtml, setEditingHtml] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState('');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ html: true, board: true, csv: false, sheet: false });
  const [editMenuOpen, setEditMenuOpen] = useState(false);
  const editMenu = useRef<HTMLDivElement>(null);
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
    if (!editMenuOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setEditMenuOpen(false); };
    const onPointer = (event: PointerEvent) => {
      if (editMenu.current && !editMenu.current.contains(event.target as Node)) setEditMenuOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
    };
  }, [editMenuOpen]);
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
      setExpanded(current => ({ ...current, board: true }));
      setEditMenuOpen(false);
      return;
    }
    setPanel('pages');
    const bucket = treeBucket(item);
    setExpanded(current => ({ ...current, html: bucket === 'html' ? true : current.html, csv: bucket === 'csv' ? true : current.csv, sheet: bucket === 'sheet' ? true : current.sheet }));
    setEditMenuOpen(false);
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
      <header className="sm-library-pagehead" data-testid="sm-library-pagehead">
        <button type="button" className="sm-library-back" data-testid="sm-cockpit-back" onClick={goConversation}>返回对话</button>
        <h1 tabIndex={-1} ref={heading}>驾驶舱</h1>
      </header>
      <aside className="sm-library-rail">
        <p className="sm-library-rail-title">产物文件夹</p>
        <ProductFolderTree items={products} busy={state.busy} selectedId={selectedId} expanded={expanded} panel={panel}
          onRefresh={() => { refreshProducts(); void library.refresh(); }} onOpen={openProduct} onToggle={key => {
            setExpanded(current => ({ ...current, [key]: !current[key] }));
            if (key === 'board') setPanel('board');
            if (key === 'html') { setEditingHtml(false); setPanel('pages'); }
          }} />
        {actionsEnabled ? <div className="sm-library-rail-foot">
          <button type="button" aria-pressed={panel === 'actions'} data-testid="analytics-competition-actions"
            onClick={() => { setVisitedActions(true); setPanel('actions'); }}>人群行动</button>
        </div> : null}
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
        <p>{{ ROLLBACK: '回退预览', LAYOUT: '布局已通过检查', PATCH: '组件修改预览', GENERATE: '生成预览' }[state.preview.operation]} · v{state.preview.snapshot.spec.version} · {state.confirmationUncertain
          ? '保存结果待核对。可能已写入服务端；请核对状态，或重试同一次保存。取消草稿不会撤销已保存内容。'
          : '尚未保存。请检查下方内容和出处。'}</p>
        <EditDiff state={state} />
        <div className="sm-library-actions">
          {state.confirmationUncertain ? <button type="button" disabled={state.busy} data-testid="library-inspect-confirmation" ref={recovery}
            onClick={() => { void library.inspectConfirmation(); }}>核对保存结果</button> : null}
          <button type="button" disabled={state.busy} data-testid="library-cancel" onClick={() => { void library.cancel(); }}>{previewCancelLabel(state.preview, state.confirmationUncertain)}</button>
          <button type="button" className="sm-library-confirm" disabled={state.busy} data-testid="library-confirm"
            onClick={() => { void library.confirm(); }}>{previewConfirmLabel(state.busy, state.confirmationUncertain, state.preview.operation)}</button>
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
        <p>布局编辑中 · 只改位置和尺寸，不改数字</p>
        <div className="sm-library-actions">
          <button type="button" disabled={state.busy} data-testid="layout-cancel" onClick={() => { void library.cancel(); }}>取消</button>
          <button type="button" className="sm-library-confirm" disabled={state.busy} data-testid="layout-preview" onClick={() => { void library.previewLayout(); }}>检查布局</button>
        </div>
      </div> : null}
      <div className="sm-library-pathbar" data-testid="library-pathbar">
        <span>{path.title ? <><strong>{path.title}</strong> {path.trail}</> : path.trail}</span>
        {panel === 'board' && state.saved && !state.preview && !state.layoutDraft
          ? <div className="sm-library-edit" ref={editMenu}>
            <button type="button" aria-expanded={editMenuOpen} aria-haspopup="menu" onClick={() => setEditMenuOpen(open => !open)}>
              编辑 ▼
            </button>
            <div className="sm-library-edit-menu" role="menu" hidden={!editMenuOpen} data-testid="library-edit-menu">
              <button type="button" role="menuitem" onClick={() => { setEditMenuOpen(false); goConversation(); }}>
                AI 编辑<small>点板块后走 PATCH_BLOCK</small>
              </button>
              <button type="button" role="menuitem" data-testid="layout-start"
                onClick={() => { setEditMenuOpen(false); library.beginLayout(); }}>
                调整布局<small>网格拖拽，检查后再确认</small>
              </button>
              <button type="button" role="menuitem" data-testid="library-rollback-previous" disabled={state.busy}
                onClick={() => { setEditMenuOpen(false); void library.rollbackPrevious(); }}>回退这一版</button>
            </div>
          </div>
          : null}
        {editingHtml
          ? <button type="button" data-testid="library-products-back" onClick={() => { setEditingHtml(false); setSelectedId(null); setFilePreview(''); setPanel('pages'); setEditMenuOpen(false); }}>关闭</button>
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
          ? <p className="sm-library-empty" data-testid="library-canvas-empty">还没有页面。</p>
          : null}
      </section>
      <section hidden={panel !== 'board'} data-testid="library-board-view" className="sm-library-document">
      {shown ? <LibraryLayoutCanvas key={shown.spec.board_id} snapshot={shown} editing={Boolean(state.layoutDraft)} disabled={state.busy}
        updateLayout={library.updateLayout} selectedBlockId={state.editContext?.block_id}
        selectBlock={!state.preview && !state.layoutDraft ? blockId => { void library.beginEdit(blockId); } : undefined} />
        : <p className="sm-library-empty" data-testid="library-board-empty">还没有看板。</p>}
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
