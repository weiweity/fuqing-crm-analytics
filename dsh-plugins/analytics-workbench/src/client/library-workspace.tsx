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

const css = `
.sm-library-workspace { min-width:0; display:flex; flex-direction:column; gap:16px; padding:20px; background:var(--sm-bg); color:var(--sm-ink); font-family:var(--sm-font-body); }
.sm-library-toolbar,.sm-library-actions,.sm-library-nav { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.sm-library-toolbar h1 { margin:0 auto 0 0; font-size:20px; font-weight:500; }
.sm-library-nav button[aria-pressed="true"] { background:var(--sm-purple); color:var(--sm-bg); }
.sm-library-workspace p { margin:0; }
[data-testid="library-board-view"] p { color:var(--sm-muted); }
.sm-library-workspace button:not(.ant-btn),.sm-library-workspace select { font:inherit; color:inherit; background:var(--sm-bg); border:1px solid var(--sm-line); border-radius:6px; padding:8px 12px; cursor:pointer; }
.sm-library-workspace button:not(.ant-btn):disabled { opacity:.5; cursor:not-allowed; }
.sm-library-workspace button:not(.ant-btn):focus-visible,.sm-library-workspace select:focus-visible,.sm-library-workspace [tabindex]:focus-visible { outline:2px solid var(--sm-purple); outline-offset:3px; }
.sm-library-workspace .sm-library-confirm { background:var(--sm-purple); color:var(--sm-bg); }
.sm-library-banner { padding:12px; border:1px solid var(--sm-purple); border-radius:8px; display:flex; flex-direction:column; gap:12px; }
.sm-library-diff { overflow:auto; max-height:260px; }
.sm-library-diff table { width:100%; border-collapse:collapse; font-size:12px; table-layout:fixed; }
.sm-library-diff th,.sm-library-diff td { text-align:left; vertical-align:top; border-bottom:1px solid var(--sm-line); padding:8px; overflow-wrap:anywhere; white-space:pre-wrap; }
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

export function LibraryCockpitPanel({ library, goConversation, themeSource, initialSurface = 'board', pageStore }: {
  library: LibraryBoardClient; goConversation(): void;
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
  initialSurface?: 'pages' | 'board';
  pageStore?: ReturnType<typeof import('./free-html-library/store.mjs').createFreeHtmlLibraryStore>;
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
  useEffect(() => { void library.refresh(); }, [library]);
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
  let headingText = shown?.spec.title ?? '我的驾驶舱';
  if (panel === 'pages') headingText = '从资料库开始工作';
  if (actionsEnabled && panel === 'actions') headingText = '人群行动';
  return <ThemeProvider colorScheme={colorScheme} className="sm-library-theme">
    <style>{css}</style>
    <main className="sm-library-workspace" data-testid="library-workspace" aria-busy={state.busy}
      onFocusCapture={event => { lastFocused.current = event.target; }}>
      <div className="sm-library-toolbar">
        <h1 tabIndex={-1} ref={heading}>{headingText}</h1>
        <button type="button" onClick={goConversation}>返回原生对话</button>
      </div>
      <nav className="sm-library-nav" aria-label="驾驶舱页面">
        <button type="button" aria-pressed={panel === 'pages'} data-testid="library-panel-pages"
          onClick={() => setPanel('pages')}>自由页面</button>
        <button type="button" aria-pressed={panel === 'board'} data-testid="library-panel-board"
          onClick={() => setPanel('board')}>我的驾驶舱</button>
        {actionsEnabled ? <button type="button" aria-pressed={panel === 'actions'} data-testid="analytics-competition-actions"
          onClick={() => { setVisitedActions(true); setPanel('actions'); }}>人群行动</button> : null}
      </nav>
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
      <section hidden={panel !== 'pages'} data-testid="library-pages-view">
        {panel === 'pages' ? <FreeHtmlLibraryApp goConversation={goConversation} themeSource={themeSource}
          store={pageStore} hostOwnsConversationLeave={Boolean(pageStore)} /> : null}
      </section>
      <section hidden={panel !== 'board'} data-testid="library-board-view">
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
