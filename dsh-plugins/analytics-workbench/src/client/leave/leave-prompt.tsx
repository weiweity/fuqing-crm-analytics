/**
 * N14 leave prompt — the three explicit choices (D40/T21, D44/T25).
 *
 * Lane F owns the leave transaction, so the prompt lives here rather than in
 * Lane E's workspace components. It renders whatever the coordinator reports:
 * `save_and_leave` / `discard` / `stay`, the reason the page is considered
 * dirty, and the failure message when a save or discard did not settle.
 *
 * Esc and the visible cancel both mean "stay" — never save, never discard.
 * The dialog is a labelled group with a keyboard-reachable default action, and
 * it never covers the page's own controls while a choice is pending.
 */
import { useEffect, useRef, useSyncExternalStore } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import type { LeaveCoordinator } from './leave-coordinator.mjs';
import { createHostLeaveAdapter, type HostLeaveAdapter } from './host-leave-adapter.mjs';
import type { LibraryBoardClient } from '../library-board-client.mjs';

const css = `
.sm-leave-prompt { position:absolute; inset:auto 0 0; z-index:40; display:flex; flex-direction:column; gap:12px;
  padding:16px; background:var(--dsw-alias-bg-base, #fff); color:var(--dsw-alias-label-primary, #111);
  border-top:1px solid var(--dsw-alias-border-l3, #d9d9d9); font:14px/1.5 var(--ds-font-family-base, sans-serif); }
.sm-leave-prompt h2 { margin:0; font-size:15px; font-weight:600; }
.sm-leave-prompt p { margin:0; }
.sm-leave-prompt-note { color:var(--dsw-alias-label-secondary, #555); }
.sm-leave-prompt-reasons { margin:0; padding-left:20px; color:var(--dsw-alias-label-secondary, #555); }
.sm-leave-prompt-actions { display:flex; gap:8px; flex-wrap:wrap; }
.sm-leave-prompt button { font:inherit; color:inherit; min-height:32px; padding:6px 12px; cursor:pointer;
  background:var(--dsw-alias-bg-base, #fff); border:1px solid var(--dsw-alias-border-l3, #d9d9d9); border-radius:6px; }
.sm-leave-prompt button[data-primary] { background:var(--sm-purple, #5b4ce0); color:#fff; border-color:transparent; }
.sm-leave-prompt button:focus-visible { outline:2px solid var(--sm-purple, #5b4ce0); outline-offset:2px; }
.sm-leave-prompt button:disabled { opacity:.6; cursor:progress; }
.sm-leave-prompt [role=alert] { color:var(--dsw-alias-label-error, #b42318); }
`;

/** Plain-language reasons, matching the predicate's own vocabulary. */
const REASON_TEXT = {
  layout_changed: '布局有尚未保存的调整。',
  pending_patch_preview: '有一份尚未确认的修改草稿。',
  confirmationUncertain: '上一次保存的结果还没有核对清楚。',
  html_unsaved: '自由页面有尚未保存的修改。',
};

export function LeavePrompt({ coordinator, pageName }: {
  coordinator: LeaveCoordinator; pageName?: string | null;
}) {
  const state = useSyncExternalStore(coordinator.subscribe, coordinator.getSnapshot);
  const primary = useRef<HTMLButtonElement>(null);
  const open = state.status === 'prompting' || state.status === 'saving' || state.status === 'discarding';
  useEffect(() => {
    if (state.status === 'prompting') primary.current?.focus();
  }, [state.status, state.intent?.epoch]);
  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      // Esc is "stay": it must never save or discard.
      coordinator.stay();
    };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [open, coordinator]);
  if (!open) return null;
  const busy = state.status !== 'prompting';
  const title = pageName ? `离开「${pageName}」前，先处理未保存的修改` : '离开前，先处理未保存的修改';
  return <div className="sm-leave-prompt" data-testid="leave-prompt" role="group" aria-label="未保存的离开保护">
    <style>{css}</style>
    <h2>{title}</h2>
    <p>这份页面有未保存的修改。请选择如何处理，再继续原来的操作。</p>
    <p className="sm-leave-prompt-note" data-testid="leave-sidebar-note">
      侧栏的原生面板行由宿主直接切换，不会询问未保存的自由页面；请从页面内入口离开。</p>
    {state.reasons.length ? <ul className="sm-leave-prompt-reasons" data-testid="leave-reasons">
      {state.reasons.map(reason => <li key={reason}>{REASON_TEXT[reason] ?? reason}</li>)}
    </ul> : null}
    {state.message ? <p role={state.status === 'prompting' && state.message ? 'alert' : 'status'}
      data-testid="leave-message">{state.message}</p> : null}
    <div className="sm-leave-prompt-actions">
      <button type="button" data-primary data-testid="leave-save" ref={primary} disabled={busy}
        onClick={() => { void coordinator.choose('save_and_leave'); }}>
        {state.status === 'saving' ? '正在保存…' : '保存并离开'}</button>
      <button type="button" data-testid="leave-discard" disabled={busy}
        onClick={() => { void coordinator.choose('discard'); }}>
        {state.status === 'discarding' ? '正在放弃…' : '放弃修改'}</button>
      <button type="button" data-testid="leave-stay" disabled={busy}
        onClick={() => coordinator.stay()}>留在当前页</button>
    </div>
  </div>;
}

/**
 * Overlay seat for the prompt. It reads the page name from the library snapshot
 * so the confirmation names what is about to be left (D40); a dirty free-HTML
 * page names that page instead, since it is what the user would lose.
 *
 * It also watches the host panel selection. The pinned `ui-sidebar` panel row
 * calls `ctx.layout.selectPanel` straight from its own onClick, so a plugin
 * cannot veto that write — but observing it lets the adapter advance the
 * navigation epoch, which is what stops a read issued for the old panel from
 * committing over the new one (D43). That limitation is recorded for P12 and
 * surfaced in the prompt's own copy.
 */
export function LeavePromptOverlay({ coordinator, library, usePanelInfo, pageStore }: PropsRuntime<'shell.overlay'> & {
  coordinator: LeaveCoordinator; library: LibraryBoardClient;
  pageStore?: ReturnType<typeof import('../free-html-library/store.mjs').createFreeHtmlLibraryStore>;
}) {
  const state = useSyncExternalStore(coordinator.subscribe, coordinator.getSnapshot);
  const pageState = useSyncExternalStore(
    pageStore?.subscribe ?? (() => () => {}), pageStore?.getSnapshot ?? (() => null));
  const panel = (usePanelInfo?.(info => info.activePanelId) ?? null) as string | null;
  const adapter = useRef<HostLeaveAdapter | null>(null);
  const seenPanel = useRef<string | null>(null);
  if (!adapter.current) adapter.current = createHostLeaveAdapter({ coordinator, readPanelId: () => seenPanel.current });
  useEffect(() => () => adapter.current?.dispose(), []);
  useEffect(() => {
    if (seenPanel.current === panel) return;
    const previous = seenPanel.current;
    seenPanel.current = panel;
    // The plugin's own entries already advanced the epoch; this covers a switch
    // the host performed without asking (the un-vetoable sidebar row).
    if (previous === null && panel === null) return;
    adapter.current?.observe(panel, previous);
  }, [panel]);
  if (state.status === 'idle') return null;
  const board = library.getSnapshot();
  const htmlDirty = pageStore?.hasUnsavedChanges() === true;
  const pageName = htmlDirty && pageState?.current?.title ? pageState.current.title
    : (board.preview?.snapshot ?? board.layoutDraft ?? board.saved)?.spec?.title ?? null;
  return <LeavePrompt coordinator={coordinator} pageName={pageName} />;
}
