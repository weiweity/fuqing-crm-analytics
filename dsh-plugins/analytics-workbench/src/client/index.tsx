import { useEffect, useRef } from 'react';
import type { Context } from '@deepseek-ai/cordis';
import { defineStore, type PropsStore } from '@deepseek-ai/dsh-client-store';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client';
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client';
import type {} from '@deepseek-ai/dsh-client-ui-layout/client';
import type {} from '@deepseek-ai/dsh-client-ui-settings/client';
import type {} from '@deepseek-ai/dsh-api-session-controller/client';
import type { ToolCallViewProps } from '@deepseek-ai/dsh-client-ui-tool/client';
import {
  TOOL_NAME, TITLE_STORAGE_KEY, FIXTURE, createEditor, changeDraft, previewTitle,
  applyTitle, serializeTitle, restoreTitle, decodeFixture,
} from '../model.mjs';
import { css } from './styles.ts';
import { bindInitialSession } from '../initial-session.mjs';
import { QUERY_TOOL_NAME } from '../query-model.mjs';
import { QueryToolCard } from './query-card.tsx';
import { RunStatus } from './run-status.tsx';

function initialState() {
  try {
    const restored = restoreTitle(window.localStorage.getItem(TITLE_STORAGE_KEY));
    return {
      open: false,
      confirmClose: false,
      editor: createEditor(restored.title),
      message: restored.invalid ? '本地 UI 偏好格式无效，已使用默认标题。'
        : restored.restored ? '已恢复本浏览器的 UI 标题；不是业务后端持久化。' : '',
    };
  } catch {
    return { open: false, confirmClose: false, editor: createEditor(), message: '浏览器存储不可用；本次 UI 修改仅在当前页面有效。' };
  }
}

function createWorkbenchStore() {
  return defineStore({
    init: initialState,
    actions: {
      open: draft => { draft.open = true; draft.confirmClose = false; },
      close: draft => { draft.open = false; draft.confirmClose = false; },
      requestClose: draft => {
        if (draft.editor.draft !== draft.editor.title || draft.editor.preview) draft.confirmClose = true;
        else draft.open = false;
      },
      keepEditing: draft => { draft.confirmClose = false; },
      discardAndClose: draft => {
        draft.editor = changeDraft(draft.editor, draft.editor.title);
        draft.open = false; draft.confirmClose = false;
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
type FooterProps = PropsRuntime<'sidebar.footer.action'> & StoreProps;
type OverlayProps = PropsRuntime<'shell.overlay'> & StoreProps & {
  detachSelection(): void;
  restoreSelection(): void;
};

function BrandMark({ size }: PropsRuntime<'sidebar.brand.mark'>) {
  return <><style>{css}</style><span className="analytics-b0-mark" role="img" aria-label="伸美原帽子标识"
    style={{ width: size, height: size }} /></>;
}

function Footer(props: FooterProps) {
  return <><style>{css}</style><button className="analytics-b0-trigger" type="button"
    title="我的驾驶舱 · B0 合成样例" aria-label="打开我的驾驶舱，B0 合成样例"
    data-testid="analytics-b0-open" onClick={() => props.actions.open()}>
    {props.wide ? '我的驾驶舱 · B0' : 'B0'}
  </button></>;
}

function AssetOverlay(props: OverlayProps) {
  const open = props.useStore(state => state.open);
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
  }, [open]);
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
    data-testid="analytics-b0-dialog"
    onKeyDown={event => {
      if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) return;
      const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),a[href]')]
        .filter(element => element.getClientRects().length > 0);
      const target = event.shiftKey && document.activeElement === controls[0] ? controls.at(-1)
        : !event.shiftKey && document.activeElement === controls.at(-1) ? controls[0] : undefined;
      if (target) { event.preventDefault(); target.focus(); }
    }}
    onCancel={event => { event.preventDefault(); props.actions.requestClose(); }}
    onClose={afterClose}>
    <header><div><span className="analytics-b0-logo" role="img" aria-label="SHINE MAGE 原始 Logo" data-testid="analytics-b0-logo" />
      <h2 id="analytics-b0-heading">伸美 · 我的驾驶舱</h2></div>
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
export const inject = ['slots', 'sessions'];

export function apply(ctx: Context): void {
  ctx.effect(() => bindInitialSession(ctx.sessions, () => {
    console.warn('analytics-b0: the configured primary session could not be selected; no fallback attempted');
  }), 'analytics-b0: select exact Host-listed primary once');
  // Same handle + same root scope = one shared open/editor state across entries.
  const store = createWorkbenchStore();
  ctx.slots.inject('sidebar.brand.mark', () => ctx.slots.register({ name: 'sidebar.brand.mark', priority: -10 }, BrandMark));
  ctx.slots.inject('sidebar.brand.name', () => ctx.slots.register({ name: 'sidebar.brand.name', priority: -10 }, () => <>伸美 · B0</>));
  ctx.slots.inject('sidebar.footer.action', () => ctx.slots.register({
    name: 'sidebar.footer.action', id: 'shine-mage.analytics-b0.footer', order: 10, store,
  }, Footer));
  ctx.slots.inject('shell.overlay', () => ctx.slots.register({
    name: 'shell.overlay', id: 'shine-mage.analytics-b0.overlay', store,
    inject: () => {
      let prior: ReturnType<typeof ctx.sessions.list.getSnapshot>['current'];
      return {
        detachSelection() { prior = ctx.sessions.list.getSnapshot().current; ctx.sessions.clear(); },
        restoreSelection() {
          const list = ctx.sessions.list.getSnapshot();
          if (prior !== undefined && list.current === undefined && list.ids.includes(prior)) ctx.sessions.open(prior);
          prior = undefined;
        },
      };
    },
  }, AssetOverlay));
  ctx.slots.inject('tool.call.toolview', () => ctx.slots.register({
    name: 'tool.call.toolview', key: TOOL_NAME,
  }, AnalyticsToolCard));
  ctx.slots.inject('tool.call.toolview', () => ctx.slots.register({
    name: 'tool.call.toolview', key: QUERY_TOOL_NAME,
  }, QueryToolCard));
  ctx.slots.inject('conversation.input.dock', () => ctx.slots.register({
    name: 'conversation.input.dock', id: 'shine-mage.analytics-b0.run-status', order: 10,
  }, RunStatus));
}
