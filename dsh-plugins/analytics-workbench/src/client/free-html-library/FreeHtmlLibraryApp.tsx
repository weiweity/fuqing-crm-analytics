import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from 'react';
import { ThemeProvider } from '../competition-shell/index.ts';
import type { CompetitionColorScheme } from '../competition-shell/tokens.ts';
import { HtmlHoverLayer } from '../HtmlHoverLayer.tsx';
import { SAMPLE_PROMPTS } from './generate-context.mjs';
import { bindingLabel, estimateIframeContentWidth, widthBand } from './host-visual.mjs';
import { createFreeHtmlLibraryStore } from './store.mjs';
import { mountPreviewHost } from '../../free-page/preview/preview-host.mjs';
import { FREE_PAGE_REFERRER_POLICY, FREE_PAGE_SANDBOX } from '../../free-page/runtime/isolation-policy.mjs';

type ThemeSource = { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
type Store = ReturnType<typeof createFreeHtmlLibraryStore>;

function saveStateText(state: ReturnType<Store['getSnapshot']>, page: ReturnType<Store['getSnapshot']>['current']) {
  if (state.confirmationUncertain) return '保存冲突 · 结果待核对';
  if (page?.dirty || state.preview?.status === 'PENDING') return '待保存';
  if (page) return `已保存 v${page.version}`;
  return '无页面';
}

function isPartialBinding(page: ReturnType<Store['getSnapshot']>['current']) {
  if (page?.binding_state !== 'BOUND_VERIFIED') return false;
  const bindings = page.binding_manifest?.bindings ?? [];
  return bindings.some(item => typeof item === 'object' && item !== null && 'status' in item && item.status !== 'verified');
}

function contextTitle(panel: string) {
  if (panel === 'ai') return '原生 AI 编辑';
  if (panel === 'history') return '版本历史';
  return '来源与检查';
}

const extraCss = `
.sm-fhl > header.sm-fhl-toolbar { padding:8px 16px; border-bottom:1px solid var(--sm-line); background:var(--sm-nav); }
.sm-fhl-rail { display:flex; gap:8px; padding:4px 16px; font-size:12px; }
.sm-fhl-rail button { min-height:28px; border:0; padding:0 4px; color:var(--sm-muted); }
.sm-fhl main { flex:1; min-height:0; display:flex; flex-direction:column; }
.sm-fhl[data-view="home"] main { padding:32px 20px 40px; }
.sm-fhl[data-view="workspace"] main { padding:0; }
.sm-fhl-home { display:flex; flex-direction:column; gap:16px; width:min(520px, 100%); margin:0 auto; }
.sm-fhl-home h1 { margin:0; font:500 22px/28px var(--sm-font-display); }
.sm-fhl-home p { margin:0; color:var(--sm-muted); font-size:13px; }
.sm-fhl-anchor { display:flex; flex-direction:column; gap:10px; }
.sm-fhl-anchor textarea { min-height:72px; resize:vertical; }
.sm-fhl-examples { display:flex; flex-wrap:wrap; gap:8px; }
.sm-fhl-examples button { min-height:28px; min-width:unset; padding:4px 12px; border-radius:999px; font-size:12px; background:var(--sm-glass); }
.sm-fhl-quiet { border:0 !important; min-height:28px !important; min-width:unset; padding:0 4px !important; color:var(--sm-lilac); background:transparent !important; }
.sm-fhl-recent { display:flex; flex-direction:column; gap:8px; }
.sm-fhl-recent h2 { margin:0; font:500 13px/18px var(--sm-font-body); color:var(--sm-muted); }
.sm-fhl-recent li { display:flex; flex-wrap:wrap; gap:8px; align-items:center; list-style:none; font-size:13px; }
.sm-fhl-recent ul { margin:0; padding:0; }
.sm-fhl-recent li button { min-height:28px; }
.sm-fhl-workspace-heading { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
.sm-fhl-workspace { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,280px); grid-template-rows:auto minmax(520px,1fr) auto; gap:0; min-height:0; flex:1; }
.sm-fhl[data-panel="closed"] .sm-fhl-workspace { grid-template-columns:minmax(0,1fr); }
.sm-fhl-workspace > .sm-fhl-toolbar { grid-column:1 / -1; padding:8px 12px; border-bottom:1px solid var(--sm-line); background:var(--sm-nav); }
.sm-fhl-preview { min-width:0; min-height:520px; position:relative; background:#0a0711; display:flex; flex-direction:column; }
.library-html-container { position:relative; min-height:0; flex:1; display:flex; flex-direction:column; }
.library-html-iframe { display:block; width:100%; flex:1; min-height:520px; border:0; background:#fff; }
.sm-fhl-preview iframe, .sm-fhl-preview [data-testid="fhl-live-preview"] { display:block; width:100%; flex:1; min-height:520px; border:0; background:#fff; }
.sm-fhl-preview [data-testid="fhl-live-preview"] { height:100%; }
.sm-fhl-hit { position:absolute; inset:0; display:flex; flex-wrap:wrap; gap:6px; align-content:flex-start; padding:8px; }
.sm-fhl-hit button { min-height:28px; font-size:12px; background:rgba(9,5,13,.72); }
.sm-fhl-float { position:absolute; bottom:12px; left:12px; display:flex; flex-wrap:wrap; gap:6px; background:rgba(15,11,23,.92); padding:8px; border:1px solid var(--sm-line); border-radius:12px; max-width:min(720px, calc(100% - 24px)); }
.sm-fhl-float button, .sm-fhl-float select { min-height:28px; font-size:12px; }
.sm-fhl-toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.sm-fhl-assets { margin-top:8px; font-size:13px; color:var(--sm-muted); }
.sm-fhl-assets summary { min-height:28px; border:0; padding:0; }
.sm-fhl-context { border-left:1px solid var(--sm-line); padding:12px; background:var(--sm-nav); overflow:auto; }
.sm-fhl-context h2 { margin:0 0 8px; font:500 14px/20px var(--sm-font-body); }
.sm-fhl-patch { border-top:1px solid var(--sm-line); padding:10px 12px; background:var(--sm-nav); grid-column:1 / -1; }
.sm-leave-prompt { margin:12px 16px; display:flex; flex-direction:column; gap:8px; padding:12px 16px; border:1px solid var(--sm-line-strong); border-radius:12px; background:var(--sm-nav); }
.sm-leave-prompt h2 { margin:0; font:500 16px/24px var(--sm-font-body); }
.sm-leave-prompt p { margin:0; color:var(--sm-muted); }
.sm-leave-prompt-actions { display:flex; flex-wrap:wrap; gap:8px; }
.sm-fhl [data-testid="fhl-message"], .sm-fhl [data-testid="fhl-live"] { margin:0; padding:6px 16px; font-size:12px; color:var(--sm-muted); }
@media (max-width: 1280px) {
  .sm-fhl-workspace { grid-template-columns:minmax(0,1fr); }
}
`;

function StatusSpine({ store }: { store: Store }) {
  const state = store.getSnapshot();
  const page = state.current;
  const binding = page ? bindingLabel(page.binding_state, { partial: isPartialBinding(page) }) : '尚未打开页面';
  const save = saveStateText(state, page);
  return (
    <div className="sm-fhl-status" data-testid="fhl-status-spine" data-binding={page?.binding_state ?? 'none'} data-save={state.confirmationUncertain ? 'conflict' : page?.dirty ? 'dirty' : 'clean'} role="status">
      <strong data-testid="fhl-title">{page?.title ?? '从资料库开始工作'}</strong>
      <span data-testid="fhl-binding">{binding}</span>
      <span data-testid="fhl-save-state">{save}</span>
      <span data-testid="fhl-mode">{state.mode === 'edit' ? '编辑中' : '浏览中'}</span>
      {page ? <button type="button" data-testid="fhl-save" disabled={state.busy} onClick={() => { void store.saveDraft(); }}>保存</button> : null}
    </div>
  );
}

function LibraryHome({ store }: { store: Store }) {
  const state = store.getSnapshot();
  return (
    <section className="sm-fhl-home" data-testid="fhl-home" aria-labelledby="fhl-home-title">
      <h1 id="fhl-home-title">从资料库开始工作</h1>
      <form className="sm-fhl-anchor" data-testid="fhl-generate-anchor" onSubmit={event => { event.preventDefault(); void store.generate(); }}>
        <label htmlFor="fhl-prompt">描述想生成的页面</label>
        <textarea id="fhl-prompt" data-testid="fhl-prompt" value={state.prompt} onChange={event => store.setPrompt(event.target.value)} placeholder="描述想生成的页面……" />
        <div className="sm-fhl-toolbar">
          <button type="submit" className="sm-fhl-generate" data-testid="fhl-generate" disabled={state.busy}>{state.busy ? '生成中…' : '生成页面'}</button>
          <button type="button" className="sm-fhl-quiet" data-testid="fhl-add-data" onClick={() => store.setDataContext({ attached: true, label: '可选数据未绑定，仍可生成' })}>添加数据</button>
          <button type="button" className="sm-fhl-quiet" data-testid="fhl-add-design" onClick={() => {
            store.setDesignGuide({ kind: 'design.md', loaded: false, error: '未读到 DESIGN.md 文件' });
            store.setSkill({ loaded: false, error: '未读到 skill' });
          }}>DESIGN.md / skill</button>
        </div>
        <p data-testid="fhl-optional-hint">{state.dataContext?.label || '在对话里说要什么页也可以。没有数据或设计指导也能生成。'}{state.designGuide?.loaded ? ' 已附加设计指导。' : state.designGuide?.error ? ` ${state.designGuide.error}` : ''}{state.skill?.loaded ? ' 已附加 skill。' : ''}</p>
      </form>
      <div className="sm-fhl-examples" data-testid="fhl-examples">
        {SAMPLE_PROMPTS.map(text => <button type="button" key={text} onClick={() => store.applyExample(text)}>{text}</button>)}
      </div>
      <section className="sm-fhl-recent" aria-labelledby="fhl-recent-title">
        <h2 id="fhl-recent-title">最近继续工作</h2>
        {state.pages.length === 0
          ? <p data-testid="fhl-empty">生成后页面会保存在这里。空库不铺卡片墙。</p>
          : <ul data-testid="fhl-recent-list">{state.pages.map(page => (
            <li key={page.page_id}>
              <span>{page.title}</span>
              <span>{bindingLabel(page.binding_state)}</span>
              <span>v{page.version}</span>
              <button type="button" onClick={() => store.openPage(page.page_id)}>打开</button>
            </li>
          ))}</ul>}
      </section>
      <details className="sm-fhl-assets" data-testid="fhl-assets" open={state.assetsExpanded} onToggle={event => { if (event.currentTarget.open !== state.assetsExpanded) store.toggleAssets(); }}>
        <summary>资料与数据（按需展开）</summary>
        <p>CSV / Markdown / 图片是生成上下文，不是首页主锚点。当前夹具无上传。</p>
      </details>
    </section>
  );
}

function LivePreviewSlot({
  pageId, version, pkg, pointerEvents,
}: {
  pageId: string;
  version: number;
  pkg: { html?: string; css?: string; js?: string; resources?: unknown[] };
  pointerEvents: NonNullable<CSSProperties['pointerEvents']>;
}) {
  const slot = useRef<HTMLDivElement>(null);
  const hostRef = useRef<ReturnType<typeof mountPreviewHost> | null>(null);
  const sourceKey = `${pageId}\0${version}\0${pkg?.html ?? ''}\0${pkg?.css ?? ''}\0${pkg?.js ?? ''}`;
  useEffect(() => {
    if (!slot.current) return;
    const host = mountPreviewHost(slot.current, {
      pageId,
      version,
      savedPackage: pkg,
      savedVersion: version,
      chrome: false,
      frameTestId: 'fhl-iframe',
    });
    hostRef.current = host;
    void host.loadPackage(pkg, version);
    return () => {
      host.dispose();
      hostRef.current = null;
    };
  }, [sourceKey, pageId, version, pkg]);
  useEffect(() => {
    const iframe = slot.current?.querySelector('iframe');
    if (iframe) iframe.style.pointerEvents = pointerEvents;
  });
  return <div ref={slot} data-testid="fhl-live-preview" />;
}

function WorkspacePreview({ srcdoc, live, pageId, version, pkg, pointerEvents }: {
  srcdoc?: string;
  live: boolean;
  pageId?: string;
  version?: number;
  pkg?: { html?: string; css?: string; js?: string; resources?: unknown[] };
  pointerEvents: NonNullable<CSSProperties['pointerEvents']>;
}) {
  if (srcdoc && live && pageId != null && version != null && pkg) {
    return <LivePreviewSlot pageId={pageId} version={version} pkg={pkg} pointerEvents={pointerEvents} />;
  }
  if (srcdoc) {
    return <iframe title="自由 HTML 页面预览" data-testid="fhl-iframe" className="library-html-iframe" srcDoc={srcdoc} sandbox={FREE_PAGE_SANDBOX} referrerPolicy={FREE_PAGE_REFERRER_POLICY} style={{ pointerEvents }} />;
  }
  return <p data-testid="fhl-preview-stopped">预览已停止。宿主入口仍可用。</p>;
}

function Workspace({ store, goConversation, editMode = false, previewRef }: {
  store: Store;
  goConversation(): void;
  editMode?: boolean;
  previewRef: { current: HTMLDivElement | null };
}) {
  const state = store.getSnapshot();
  const layout = store.layout();
  const locatable = state.current?.package.node_map ?? [];
  const livePkg = state.preview?.snapshot ?? state.current?.package;
  const iframePointerEvents: NonNullable<CSSProperties['pointerEvents']> = editMode ? 'auto' : layout.pointerEvents;
  const srcdoc = layout.srcdoc;
  return (
    <section data-testid="fhl-workspace" aria-labelledby="fhl-workspace-title">
      <h2 id="fhl-workspace-title" className="sm-fhl-workspace-heading">页面工作区</h2>
      <div className="sm-fhl-toolbar">
        <button type="button" data-testid="fhl-back-home" onClick={() => store.requestLeave('home')}>返回资料库</button>
        <button type="button" data-testid="fhl-toggle-mode" onClick={() => state.mode === 'edit' ? store.exitEdit() : store.enterEdit()}>
          {state.mode === 'edit' ? '退出编辑' : '进入编辑'}
        </button>
        <button type="button" data-testid="fhl-open-source" aria-pressed={state.contextPanel === 'source'} onClick={() => store.openContext('source')}>来源</button>
        <button type="button" data-testid="fhl-open-history" aria-pressed={state.contextPanel === 'history'} onClick={() => store.openContext('history')}>历史</button>
        <button type="button" data-testid="fhl-open-ai" aria-pressed={state.contextPanel === 'ai'} onClick={() => store.openContext('ai')}>AI 编辑</button>
        <button type="button" data-testid="fhl-stop" onClick={() => store.stopPreview()}>停止预览</button>
        <button type="button" data-testid="fhl-restart" onClick={() => store.restartPreview()}>重启预览</button>
        <button type="button" data-testid="fhl-inspect" onClick={() => store.inspectCurrent()}>页面检查</button>
      </div>
      <div className="sm-fhl-workspace">
        <div ref={previewRef} className="sm-fhl-preview library-html-container" data-testid="fhl-preview" data-mode={state.mode} data-edit-mode={editMode ? '1' : '0'} style={{ position: 'relative' }}>
          <WorkspacePreview srcdoc={srcdoc} live={state.adapterKind === 'p12-live' && Boolean(livePkg && state.current)}
            pageId={state.current?.page_id} version={state.current?.version} pkg={livePkg} pointerEvents={iframePointerEvents} />
          {editMode ? <HtmlHoverLayer iframeRef={previewRef} editMode={editMode} /> : null}
          {state.mode === 'edit' && !editMode ? <div className="sm-fhl-hit" data-testid="fhl-hit-layer">
            {locatable.map(node => (
              <button type="button" key={node.node_id} data-testid={`fhl-hit-${node.node_id}`}
                onClick={() => store.selectLocatable({
                  kind: node.kind === 'dynamic_region' ? 'dynamic_region' : 'static_element',
                  node_id: node.node_id, mapping: 'valid',
                })}>
                {node.kind === 'dynamic_region' ? '动态区域' : '元素'} · {node.node_id}
              </button>
            ))}
          </div> : null}
        </div>
        {state.contextPanel ? <aside className="sm-fhl-context" data-testid="fhl-context" data-panel={state.contextPanel} aria-labelledby="fhl-context-title">
          <div className="sm-fhl-toolbar">
            <h2 id="fhl-context-title">{contextTitle(state.contextPanel ?? 'source')}</h2>
            <button type="button" data-testid="fhl-context-back" onClick={() => store.closeContext()}>返回</button>
          </div>
          {state.contextPanel === 'ai' ? <>
            <p>使用当前原生对话继续修改，不新建 Agent。</p>
            <p data-testid="fhl-ai-scope">{state.selection?.ok ? state.selection.label : '未选择范围时只描述意图，不会静默改整页'}</p>
            <button type="button" data-testid="fhl-native-edit" onClick={() => goConversation()}>在原生对话继续</button>
            <button type="button" data-testid="fhl-patch-preview" disabled={!state.selection?.ok || state.busy} onClick={() => { void store.previewPatch('把标题改得更清楚'); }}>预览补丁</button>
            <button type="button" data-testid="fhl-patch-shared" disabled={!state.selection?.ok || state.busy} onClick={() => { void store.previewPatch('调整共享样式', { affectsShared: true }); }}>预览含共享 CSS</button>
          </> : null}
          {state.contextPanel === 'history' ? <ul data-testid="fhl-history">{(state.current?.history ?? []).map(item => (
            <li key={item.version}><button type="button" disabled={state.busy} onClick={() => { void store.rollback(item.version); }}>回退到 v{item.version}</button></li>
          ))}</ul> : null}
          {state.contextPanel === 'source' ? <>
            <p data-testid="fhl-source-binding">{state.current ? bindingLabel(state.current.binding_state) : '无页面'}</p>
            <p>启发式不改写不确定数字。来源验证不认证全部叙述。</p>
            {state.inspector ? <pre data-testid="fhl-inspector">{JSON.stringify(state.inspector, null, 2)}</pre> : null}
          </> : null}
        </aside> : null}
      </div>
      {state.preview ? <div className="sm-fhl-patch" data-testid="fhl-patch" role="region" aria-label="补丁预览">
        <p>D6 补丁预览 · {state.preview.expanded_scope}{state.preview.shared_impact ? ` · ${state.preview.shared_impact}` : ''}</p>
        {state.preview.expanded_scope === 'preview_expanded_range' ? <button type="button" data-testid="fhl-confirm-scope" onClick={() => store.confirmExpandedPatch()}>确认扩大范围</button> : null}
        <button type="button" data-testid="fhl-confirm-patch" disabled={state.busy} onClick={() => { void store.confirmPatch(); }}>确认提交补丁</button>
        <button type="button" data-testid="fhl-cancel-patch" disabled={state.busy} onClick={() => { void store.cancelPreview(); }}>取消补丁</button>
      </div> : null}
    </section>
  );
}

export function FreeHtmlLibraryApp({
  goConversation, themeSource, store: provided, viewportWidth = 1440,
  hostOwnsConversationLeave = false, editMode = false,
}: {
  goConversation(): void;
  themeSource: ThemeSource;
  store?: Store;
  viewportWidth?: number;
  hostOwnsConversationLeave?: boolean;
  editMode?: boolean;
}) {
  const store = useMemo(
    () => provided ?? createFreeHtmlLibraryStore({ viewportWidth }),
    [provided, viewportWidth],
  );
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot);
  const colorScheme = useSyncExternalStore(themeSource.subscribe, themeSource.getSnapshot);
  const heading = useRef<HTMLHeadingElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const previewRef = useRef<HTMLDivElement>(null);
  const [restore, setRestore] = useState('');
  useEffect(() => { store.setViewport(viewportWidth); }, [store, viewportWidth]);
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (!root.contains(event.target as Node)) return;
      store.closeOverlay();
      setRestore('esc-closed');
    };
    root.addEventListener('keydown', onKey);
    return () => root.removeEventListener('keydown', onKey);
  }, [store]);
  const width = estimateIframeContentWidth({
    viewportWidth: state.viewportWidth,
    railOpen: !state.railCollapsed,
    panelOpen: Boolean(state.contextPanel),
  });
  return (
    <ThemeProvider colorScheme={colorScheme} className="sm-library-theme">
      <style>{extraCss}</style>
      <div ref={rootRef} className="sm-fhl" data-testid="fhl-root" data-view={state.view} data-rail={state.railCollapsed ? 'collapsed' : 'open'}
        data-panel={state.contextPanel ? 'open' : 'closed'} data-band={widthBand(state.viewportWidth)} data-adapter={state.adapterKind}>
        <a className="sm-fhl-skip" href="#fhl-main" data-testid="fhl-skip-iframe">跳过预览，回到宿主</a>
        <header className="sm-fhl-toolbar">
          <button type="button" data-testid="fhl-native-chat" onClick={() => {
            if (hostOwnsConversationLeave) {
              goConversation();
              return;
            }
            const leave = store.requestLeave('conversation');
            if (!leave.blocked) goConversation();
          }}>返回原生对话</button>
          <button type="button" data-testid="fhl-toggle-rail" onClick={() => store.toggleRail()}>{state.railCollapsed ? '展开资料导轨' : '折叠资料导轨'}</button>
          <span data-testid="fhl-width">{width.iframeContentWidth}</span>
        </header>
        {state.railCollapsed ? null : <nav className="sm-fhl-rail" data-testid="fhl-rail" aria-label="资料库导轨">
          <button type="button" onClick={() => store.requestLeave('home')}>最近</button>
        </nav>}
        <StatusSpine store={store} />
        {state.message ? <p role="status" aria-live="polite" data-testid="fhl-message">{state.message}</p> : null}
        {state.liveStatus ? <p role="status" aria-live="polite" data-testid="fhl-live">{state.liveStatus}</p> : null}
        {state.hostError ? <p role="alert" data-testid="fhl-host-error">{state.hostError}</p> : null}
        {state.pendingLeaveIntent ? <div className="sm-leave-prompt" data-testid="fhl-leave-prompt" role="group" aria-label="未保存的离开保护">
          <h2>离开前，先处理未保存的修改</h2>
          <p data-testid="fhl-leave-seam">这份页面有未保存的修改。请选择如何处理，再继续原来的操作。</p>
          <div className="sm-leave-prompt-actions">
            <button type="button" data-testid="fhl-leave-save" disabled={state.busy} onClick={() => {
              void store.saveAndLeave().then(result => {
                if (result.navigated && result.intent === 'conversation') goConversation();
              });
            }}>{state.busy ? '正在保存…' : '保存并离开'}</button>
            <button type="button" data-testid="fhl-leave-discard" disabled={state.busy} onClick={() => {
              void store.discardAndLeave().then(result => {
                if (result.navigated && result.intent === 'conversation') goConversation();
              });
            }}>放弃修改</button>
            <button type="button" data-testid="fhl-leave-stay" disabled={state.busy} onClick={() => store.stayLeave()}>留在当前页</button>
          </div>
        </div> : null}
        <main id="fhl-main" tabIndex={-1} ref={heading}>
          {state.view === 'home' ? <LibraryHome store={store} /> : <Workspace store={store} goConversation={goConversation} editMode={editMode} previewRef={previewRef} />}
        </main>
        <span hidden data-testid="fhl-restore">{restore}</span>
      </div>
    </ThemeProvider>
  );
}

export function createLibraryStoreForTests(options?: Parameters<typeof createFreeHtmlLibraryStore>[0]) {
  return createFreeHtmlLibraryStore(options);
}
