import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { Context } from '@deepseek-ai/cordis';
import { defineStore, type PropsStore } from '@deepseek-ai/dsh-client-store';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client';
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client';
import type { MainPanelId } from '@deepseek-ai/dsh-client-ui-layout/client';
import type {} from '@deepseek-ai/dsh-client-ui-settings/client';
import type {} from '@deepseek-ai/dsh-client-ui-theme/client';
import type {} from '@deepseek-ai/dsh-api-session-controller/client';
import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import {
  TOOL_NAME, TITLE_STORAGE_KEY, FIXTURE, createEditor, changeDraft, previewTitle,
  applyTitle, serializeTitle, restoreTitle, decodeFixture,
} from '../model.mjs';
import { css, markCss } from './styles.ts';
import { trapDialogTab } from './focus.ts';
import { B0_PRIMARY_SESSION_ID, QUERY_SESSION_IDS, bindInitialSession } from '../initial-session.mjs';
import { QUERY_TOOL_NAME } from '../query-model.mjs';
import { FIRST_PURCHASE_TOOL_NAME } from '../first-purchase-query-model.mjs';
import { QueryToolCard } from './query-card.tsx';
import { FirstPurchaseQueryCard } from './first-purchase-query-card.tsx';
import { RunStatus } from './run-status.tsx';
import { HttpAssetOverlay } from './asset-overlay.tsx';
import { OverlayErrorBoundary } from './overlay-error-boundary.mjs';
import { probeAssetHttp } from '../asset-http.mjs';
import { competitionHttpOptions } from './competition-http.mjs';
import { ThemeProvider } from './competition-shell/index.ts';
import { nativeBrandTokens, type CompetitionColorScheme } from './competition-shell/tokens.ts';
import { PRODUCT_NAME, watchCompetitionBrandSurface } from './brand-surface.mjs';
import { COCKPIT_PANEL_ID, CockpitMainPanel, CockpitPanelIcon } from './cockpit-main-panel.tsx';
import { STAFF_PANEL_ID, StaffMainPanel, StaffPanelIcon } from './staff-main-panel.tsx';
import { applyGenerate, generateBoard, specFromGsvFacts, specWithLink } from '../board-spec/generate.mjs';
import { catalogFromGsvItems } from '../board-spec/facts-from-result.mjs';
import { refreshFacts } from '../board-spec/refresh.mjs';

import { BOARD_SPEC_FACTS, BOARD_SPEC_FIXTURE } from '../board-spec/fixture.mjs';
import { DEMO_BOARD } from '../board-spec/demo-board.mjs';

function initialState() {
  try {
    const restored = restoreTitle(window.localStorage.getItem(TITLE_STORAGE_KEY));
    return {
      open: false,
      openTick: 0,
      intent: 'view' as 'view' | 'generate',
      confirmClose: false,
      boardSpec: null as object | null,
      boardFacts: null as object | null,
      boardError: '',
      pendingGenerate: null as { spec: object; facts: object | null } | null,
      boardEpoch: 0,
      factsCatalog: null as object | null,
      editor: createEditor(restored.title),
      message: restored.invalid ? '本地 UI 偏好格式无效，已使用默认标题。'
        : restored.restored ? '已恢复本浏览器的 UI 标题；不是业务后端持久化。' : '',
    };
  } catch {
    return {
      open: false, openTick: 0, intent: 'view' as const, confirmClose: false,
      boardSpec: null, boardFacts: null, boardError: '', pendingGenerate: null, boardEpoch: 0, factsCatalog: null,
      editor: createEditor(), message: '浏览器存储不可用；本次 UI 修改仅在当前页面有效。',
    };
  }
}

/** A seeded store opens the cockpit on a board; the dock still replaces it. */
function createWorkbenchStore(seedBoard: { spec: object; facts: object | null } | null = null) {
  return defineStore({
    init: () => {
      const state = initialState();
      if (seedBoard) {
        state.boardSpec = seedBoard.spec;
        state.boardFacts = seedBoard.facts;
      }
      return state;
    },
    actions: {
      open: draft => { draft.open = true; draft.intent = 'view'; draft.confirmClose = false; draft.openTick = (draft.openTick || 0) + 1; },
      openGenerate: draft => { draft.open = true; draft.intent = 'generate'; draft.confirmClose = false; draft.openTick = (draft.openTick || 0) + 1; },
      generateBoard: (draft, payload?: { spec?: object; facts?: object | null }) => {
        if (!payload?.spec) {
          draft.boardError = '这场对话没有可绑定的核验结果，未写入。';
          return;
        }
        applyGenerate(draft, payload.spec, payload.facts ?? null);
        draft.pendingGenerate = null;
      },
      proposeGenerate: (draft, payload?: { spec?: object; facts?: object | null }) => {
        if (!payload?.spec) {
          draft.pendingGenerate = null;
          draft.boardError = '这场对话没有可绑定的核验结果，未写入。';
          return;
        }
        const got = generateBoard(payload.spec, payload.facts ?? null);
        if (!got.ok) {
          draft.boardError = got.error.message;
          draft.pendingGenerate = null;
          return;
        }
        draft.boardError = '';
        draft.pendingGenerate = got.value;
      },
      confirmGenerate: (draft) => {
        if (!draft.pendingGenerate) return;
        applyGenerate(draft, draft.pendingGenerate.spec, draft.pendingGenerate.facts);
        draft.pendingGenerate = null;
        draft.boardEpoch = (draft.boardEpoch || 0) + 1;
      },
      setFactsCatalog: (draft, catalog: object | null) => { draft.factsCatalog = catalog; },
      refreshBoard: (draft) => {
        if (!draft.boardSpec) return;
        const catalog = draft.factsCatalog ?? draft.boardFacts;
        const got = refreshFacts(draft.boardSpec, catalog);
        if (!got.ok) {
          draft.boardError = got.error.message;
          return;
        }
        draft.boardFacts = got.value;
      },
      cancelGenerate: (draft) => { draft.pendingGenerate = null; },
      close: draft => { draft.open = false; draft.intent = 'view'; draft.confirmClose = false; },
      requestClose: draft => {
        if (draft.editor.draft !== draft.editor.title || draft.editor.preview) draft.confirmClose = true;
        else draft.open = false;
      },
      keepEditing: draft => { draft.confirmClose = false; },
      discardAndClose: draft => {
        draft.editor = changeDraft(draft.editor, draft.editor.title);
        draft.open = false; draft.intent = 'view'; draft.confirmClose = false;
      },
      edit: (draft, title: string) => { draft.editor = changeDraft(draft.editor, title); draft.message = ''; },
      preview: draft => {
        try { draft.editor = previewTitle(draft.editor); draft.message = '仅预览标题；合成数据与条件未变。'; }
        catch (error) { draft.message = error instanceof Error ? error.message : '无法预览。'; }
      },
      commit: (draft, message: string) => { draft.editor = applyTitle(draft.editor); draft.message = message; },
      discard: draft => { draft.editor = changeDraft(draft.editor, draft.editor.title); draft.message = '已撤销未应用的标题草稿。'; },
      notify: (draft, message: string) => { draft.message = message; },
    },
  });
}

type StoreProps = PropsStore<ReturnType<typeof createWorkbenchStore>>;
type FooterProps = PropsRuntime<'sidebar.footer.action'> & StoreProps & {
  openCockpit?(): boolean;
};
type OverlayProps = PropsRuntime<'shell.overlay'> & StoreProps & {
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
  detachSelection(): void;
  restoreSelection(): void;
};

function RoutedOverlay(props: OverlayProps) {
  const colorScheme = useSyncExternalStore(props.themeSource.subscribe, props.themeSource.getSnapshot);
  const [assets, setAssets] = useState(false);
  const competitionHttp = competitionHttpOptions();
  const openTick = props.useStore(state => state.openTick ?? 0);
  const open = props.useStore(state => state.open);
  useEffect(() => {
    if (!open) return;
    void probeAssetHttp().then(setAssets);
  }, [open]);
  return (
    <ThemeProvider className="sm-overlay-theme" colorScheme={colorScheme}>
      <OverlayErrorBoundary resetKey={openTick}>
        {assets || competitionHttp
          ? <HttpAssetOverlay key={openTick} {...props} />
          : <AssetOverlay key={openTick} {...props} />}
      </OverlayErrorBoundary>
    </ThemeProvider>
  );
}

function BrandMark({ size, className }: { size?: number; className?: string }) {
  return <><style>{markCss}</style><span className={['analytics-b0-mark', className].filter(Boolean).join(' ')}
    role="img" aria-label="伸美原帽子标识" style={{ width: size, height: size }} /></>;
}

type BoardLive = ReturnType<ReturnType<typeof createWorkbenchStore>['create']>;

type DockProps = PropsRuntime<'conversation.input.dock'> & {
  openCockpit?(): boolean;
  board: BoardLive;
  fetchResults?(): Promise<unknown[]>;
};

function GenerateCockpitDock(props: DockProps) {
  const id = props.session.sessionId;
  if (id !== B0_PRIMARY_SESSION_ID && !QUERY_SESSION_IDS.some(value => value === id)) return null;
  const proposeBoard = () => {
    void (async () => {
      const items = props.fetchResults ? await props.fetchResults() : [];
      const catalog = catalogFromGsvItems(items);
      const spec = specFromGsvFacts(catalog, { session_id: props.session.sessionId });
      if (!spec.ok) props.board.actions.proposeGenerate();
      else props.board.actions.proposeGenerate({ spec: spec.value, facts: catalog });
      props.openCockpit?.();
    })();
  };
  const proposeLink = (blockId: string) => {
    const link = BOARD_SPEC_FIXTURE.blocks.find((block: { block_id?: string }) => block.block_id === blockId);
    if (!link) return;
    const snap = props.board.getSnapshot();
    const next = specWithLink(snap.boardSpec, link);
    if (!next.ok) return;
    props.board.actions.proposeGenerate({ spec: next.value, facts: snap.boardFacts });
    props.openCockpit?.();
  };
  return <><style>{css}</style>
    <div className="analytics-b0-artifacts" data-testid="analytics-b0-artifacts">
      <span>聊完后生成产物，进入驾驶舱：</span>
      <button type="button" className="analytics-b0-generate-dock" data-testid="analytics-b0-generate-cockpit"
        title="用这次认可的分析结果生成驾驶舱"
        aria-label="生成驾驶舱"
        onClick={proposeBoard}>生成驾驶舱</button>
      <button type="button" className="analytics-b0-generate-dock" data-testid="analytics-b0-generate-feishu"
        title="写入飞书文档链接，不接飞书 token"
        aria-label="生成飞书文档"
        onClick={() => proposeLink('b7')}>生成飞书文档</button>
      <button type="button" className="analytics-b0-generate-dock" data-testid="analytics-b0-generate-bitable"
        title="写入多维表链接，不接飞书 token"
        aria-label="生成多维表"
        onClick={() => proposeLink('b8')}>生成多维表</button>
    </div></>;
}

function Footer(props: FooterProps) {
  const live = Boolean(competitionHttpOptions());
  return <><style>{css}</style><button className="analytics-b0-trigger" type="button"
    title={live ? '我的驾驶舱' : '我的驾驶舱 · 合成样例'}
    aria-label={live ? '打开我的驾驶舱' : '打开我的驾驶舱，合成样例'}
    data-testid="analytics-b0-open" onClick={() => {
      const opened = props.openCockpit?.();
      if (opened) props.actions.close();
      if (!opened) props.actions.open();
    }}>
    {props.wide ? '我的驾驶舱' : '驾驶舱'}
  </button></>;
}

function AssetOverlay(props: OverlayProps) {
  const open = props.useStore(state => state.open);
  const openTick = props.useStore(state => state.openTick ?? 0);
  const editor = props.useStore(state => state.editor);
  const message = props.useStore(state => state.message);
  const confirmClose = props.useStore(state => state.confirmClose);
  const selectedSession = props.useSessions(state => state.current);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const focusFrame = useRef<number | undefined>(undefined);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open, openTick]);
  useEffect(() => () => {
    if (focusFrame.current !== undefined) cancelAnimationFrame(focusFrame.current);
    dialogRef.current?.close();
  }, []);

  function afterClose() {
    props.actions.close(); props.restoreSelection();
    // Native InputBar intentionally focuses its editor on a session switch.
    // Let that React commit paint, then return to our own fixed entry. No
    // upstream focus listener, component or stylesheet is replaced.
    if (focusFrame.current !== undefined) cancelAnimationFrame(focusFrame.current);
    focusFrame.current = requestAnimationFrame(() => {
      focusFrame.current = requestAnimationFrame(() => {
        focusFrame.current = undefined;
        if (!dialogRef.current?.open) document.querySelector<HTMLButtonElement>('[data-testid="analytics-b0-open"]')?.focus({ preventScroll: true });
      });
    });
  }

  function applyPreview() {
    try {
      const next = applyTitle(editor);
      let status = '已应用并保存本浏览器 UI 标题；刷新页面后可恢复。不是业务后端持久化。';
      try { window.localStorage.setItem(TITLE_STORAGE_KEY, serializeTitle(next.title)); }
      catch { status = '已应用到当前页面，但浏览器存储失败；刷新将丢失此次标题修改。'; }
      props.actions.commit(status);
    } catch (error) {
      props.actions.notify(error instanceof Error ? error.message : '无法应用预览。');
    }
  }

  return <><style>{css}</style><dialog ref={dialogRef} className="analytics-b0-dialog"
    aria-labelledby="analytics-b0-heading" aria-describedby="analytics-b0-boundary"
    data-testid="analytics-b0-dialog" data-dsh-native-chrome="1"
    onKeyDown={trapDialogTab}
    onCancel={event => { event.preventDefault(); props.actions.requestClose(); }}
    onClose={afterClose}>
    <header><div><span className="analytics-b0-logo" role="img" aria-label="SHINE MAGE 原始 Logo" data-testid="analytics-b0-logo" />
      <h2 id="analytics-b0-heading">{PRODUCT_NAME}</h2></div>
      <button type="button" data-testid="analytics-b0-close" onClick={() => props.actions.requestClose()}>返回聊天</button></header>
    {confirmClose && <section className="analytics-b0-preview" role="alert" data-testid="analytics-b0-close-confirm">
      <p>标题草稿尚未应用，是否放弃本次修改？</p>
      <div className="analytics-b0-actions"><button type="button" onClick={() => props.actions.keepEditing()}>继续编辑</button>
        <button type="button" onClick={() => props.actions.discardAndClose()}>放弃草稿并返回</button></div>
    </section>}
    <p id="analytics-b0-boundary"><strong>B0 / STUB / SYNTHETIC</strong> · 独立静态资产，无需模型或活动会话。</p>
    <p><small>本页只验证 DSH 承载和局部标题编辑。未接真实数据库、业务资产库、AI 编辑或审批接口。</small></p>
    <p data-testid="analytics-b0-selection">{selectedSession ? '原会话仍保留；此资产不依赖会话。' : '当前无活动会话；固定资产仍可读。'}</p>
    <button type="button" data-testid="analytics-b0-detach" disabled={!selectedSession}
      onClick={() => props.detachSelection()}>脱离会话阅读（B0 验证）</button>
    <section aria-labelledby="analytics-b0-asset-title">
      <h3 id="analytics-b0-asset-title" data-testid="analytics-b0-title">{editor.title}</h3>
      <small>固定样例日期 {FIXTURE.data_as_of} · {FIXTURE.fixture_id} · 非最新经营数据</small>
      <table><caption>固定合成资产 · 复购率 = 复购人数 / 客户数</caption>
        <thead><tr><th scope="col">渠道</th><th scope="col">客户</th><th scope="col">复购</th><th scope="col">复购率</th></tr></thead>
        <tbody><tr><th scope="row">{FIXTURE.channel}</th><td>{FIXTURE.customers}</td><td>{FIXTURE.repeat_customers}</td><td>{FIXTURE.repeat_rate * 100}%</td></tr></tbody>
      </table>
      <label htmlFor="analytics-b0-draft">只编辑这个板块的标题（最多 40 字）</label>
      <input id="analytics-b0-draft" data-testid="analytics-b0-title-input" value={editor.draft}
        maxLength={80} onChange={event => props.actions.edit(event.currentTarget.value)} />
      <div className="analytics-b0-actions">
        <button type="button" data-testid="analytics-b0-preview" onClick={() => props.actions.preview()}>预览标题</button>
        <button type="button" data-testid="analytics-b0-apply" disabled={!editor.preview} onClick={applyPreview}>应用预览（仅本浏览器）</button>
        <button type="button" onClick={() => props.actions.discard()}>撤销草稿</button>
      </div>
      {editor.preview && <div className="analytics-b0-preview" data-testid="analytics-b0-preview-panel">
        <strong>预览，尚未应用</strong><p>{editor.preview.title}</p><small>数据、日期、渠道与指标均未改变。</small>
      </div>}
      <p role="status" aria-live="polite" data-testid="analytics-b0-status">{message}</p>
    </section>
    <p><small>localStorage 仅保存标题这一项 UI 偏好，不保存数据、会话、授权或业务资产。刷新页面不会刷新合成指标。</small></p>
    <p><a data-testid="analytics-b0-board-sample" href="/b0/board-sample?ref=b0-condition-specimen-v1">查看 B0 完整条件往返样例</a>
      <br /><small>独立合成接缝，未执行查询。不是本页指标的同条件 BI；旧私有 BI 仍不开放。</small></p>
  </dialog></>;
}

function AnalyticsToolCard({ block }: ToolCallViewProps) {
  if (!('kind' in block) || block.kind !== 'tool-result') {
    return <div className="analytics-b0-card" role="status">B0 合成工具运行中…</div>;
  }
  if (block.isError) return <div className="analytics-b0-card" role="status">B0 工具失败；没有可用结果。未执行业务动作。</div>;
  const value = decodeFixture(block.meta);
  if (!value) return <div className="analytics-b0-card" role="status">结果格式无法识别或版本不支持；不推断分析成功。</div>;
  return <div className="analytics-b0-card" data-testid="analytics-b0-tool-result">
    <strong>B0 / STUB / SYNTHETIC · 合成工具结果</strong>
    <p>{value.channel}：{value.customers} 位客户中 {value.repeat_customers} 位复购，复购率 {value.repeat_rate * 100}%。</p>
    <small>固定样例日期 {value.data_as_of} · {value.fixture_id}。这是工具步骤结果；任务终态以输入框上方的内核状态为准。不含真实数据或审批动作。</small>
  </div>;
}

export const name = 'analytics-workbench-b0-client';
export const inject = ['slots', 'sessions', 'theme', 'layout'];

export function apply(ctx: Context): void {
  ctx.effect(() => bindInitialSession(ctx.sessions, () => {
    console.warn('analytics-b0: the configured primary session could not be selected; no fallback attempted');
  }), 'analytics-b0: select exact Host-listed primary once');
  const chromeStore = createWorkbenchStore();
  const boardLive = createWorkbenchStore(DEMO_BOARD).create();
  ctx.effect(() => ctx.theme.overrideTokens('shine-mage.brand', nativeBrandTokens), 'competition-native-theme');
  ctx.effect(() => watchCompetitionBrandSurface(), 'competition-brand-surface');
  ctx.slots.inject('sidebar.brand.mark', () => ctx.slots.register({ name: 'sidebar.brand.mark', priority: -10 }, BrandMark));
  ctx.slots.inject('sidebar.brand.name', () => ctx.slots.register({ name: 'sidebar.brand.name', priority: -10 }, () => <>{PRODUCT_NAME}</>));
  ctx.slots.inject('conversation.hero.brand.mark', () => ctx.slots.register({
    name: 'conversation.hero.brand.mark', priority: -10,
  }, BrandMark));
  const openCockpitPanel = (): boolean => {
    try {
      const layout = ctx.layout;
      if (layout == null || typeof layout.selectPanel !== 'function') return false;
      layout.selectPanel(COCKPIT_PANEL_ID as MainPanelId);
      return true;
    } catch {
      return false;
    }
  };
  const goConversation = (): void => {
    try { ctx.layout?.selectPanel(null); } catch { /* stay on the current panel */ }
  };
  const themeSource = {
    subscribe: (listener: () => void) => {
      try {
        const dispose = ctx.on('theme/change', listener);
        return () => { dispose(); };
      } catch { return () => {}; }
    },
    getSnapshot: (): CompetitionColorScheme => {
      try { return ctx.theme.getTheme().active.colorScheme; }
      catch { return 'dark'; }
    },
  };
  ctx.slots.inject('sidebar.footer.action', () => ctx.slots.register({
    name: 'sidebar.footer.action', id: 'shine-mage.analytics-b0.footer', order: 10, store: chromeStore,
    inject: () => ({ openCockpit: openCockpitPanel }),
  }, Footer));
  ctx.slots.inject('shell.overlay', () => ctx.slots.register({
    name: 'shell.overlay', id: 'shine-mage.analytics-b0.overlay', store: chromeStore,
    inject: () => {
      let prior: ReturnType<typeof ctx.sessions.list.getSnapshot>['current'];
      return {
        themeSource,
        detachSelection() { prior = ctx.sessions.list.getSnapshot().current; ctx.sessions.clear(); },
        restoreSelection() {
          const list = ctx.sessions.list.getSnapshot();
          if (prior !== undefined && list.current === undefined && list.ids.includes(prior)) ctx.sessions.open(prior);
          prior = undefined;
        },
      };
    },
  }, RoutedOverlay));
  ctx.slots.inject('tool.call.toolview', () => ctx.slots.register({
    name: 'tool.call.toolview', key: TOOL_NAME,
  }, AnalyticsToolCard));
  ctx.slots.inject('tool.call.toolview', () => ctx.slots.register({
    name: 'tool.call.toolview', key: QUERY_TOOL_NAME,
  }, QueryToolCard));
  ctx.slots.inject('tool.call.toolview', () => ctx.slots.register({
    name: 'tool.call.toolview', key: FIRST_PURCHASE_TOOL_NAME,
  }, FirstPurchaseQueryCard));
  ctx.slots.inject('conversation.input.dock', () => ctx.slots.register({
    name: 'conversation.input.dock', id: 'shine-mage.analytics-b0.run-status', order: 10,
  }, RunStatus));
  ctx.slots.inject('conversation.input.dock', () => ctx.slots.register({
    name: 'conversation.input.dock', id: 'shine-mage.analytics-b0.generate-cockpit', order: 20,
    inject: () => ({
      openCockpit: openCockpitPanel,
      board: boardLive,
      async fetchResults() {
        const http = competitionHttpOptions();
        if (!http) return [];
        try {
          const res = await http.fetchImpl(`${http.basePath}/results`);
          if (!res || !res.ok) return [];
          const body = await res.json();
          return Array.isArray(body.items) ? body.items : [];
        } catch {
          return [];
        }
      },
    }),
  }, GenerateCockpitDock));
  ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
    name: 'sidebar.panellist', id: COCKPIT_PANEL_ID, order: 20, label: '驾驶舱',
  }, CockpitPanelIcon));
  ctx.slots.inject('main', () => ctx.slots.register({
    name: 'main', key: COCKPIT_PANEL_ID,
    inject: () => {
      const http = competitionHttpOptions();
      return {
        goConversation,
        themeSource,
        board: boardLive,
        askTransport: http
          ? {
            fetchImpl: http.fetchImpl,
            path: '/api/v1/analytics/board-spec/ask',
            resultsPath: `${http.basePath}/results`,
          }
          : undefined,
      };
    },
  }, CockpitMainPanel));
  ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
    name: 'sidebar.panellist', id: STAFF_PANEL_ID, order: 21, label: '数据员工',
  }, StaffPanelIcon));
  ctx.slots.inject('main', () => ctx.slots.register({
    name: 'main', key: STAFF_PANEL_ID,
    inject: () => ({
      goConversation,
      themeSource,
      openPlazaRole() {
        void (async () => {
          try {
            const created = await ctx.sessions.create();
            ctx.sessions.open(created);
            ctx.layout?.selectPanel(null);
          } catch {
            goConversation();
          }
        })();
      },
    }),
  }, StaffMainPanel));
}
