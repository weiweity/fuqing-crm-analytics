import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import type { LibraryBoardClient } from './library-board-client.mjs';
import type { CompetitionColorScheme } from './competition-shell/tokens.ts';
import { LibraryCockpitPanel } from './library-workspace.tsx';
import { CHAT_MIN, compositionGeometry, nativeCompositionTarget, leaseNativeComposition, leaseCompactNavigation, type CockpitComposition } from './cockpit-composition.mjs';

const css = `
[data-sm-cockpit-native="v1"] { width:var(--sm-cockpit-chat-width); flex:none; align-self:flex-end; height:calc(100% - 44px); margin-top:44px; visibility:var(--sm-cockpit-chat-hidden); }
.sm-cockpit-composition { position:absolute; inset:0; pointer-events:none !important; }
.sm-cockpit-composition-region { position:absolute; pointer-events:none; color:var(--dsw-alias-label-primary); font:14px/1.5 var(--ds-font-family-base, sans-serif); }
.sm-cockpit-composition-toolbar { position:absolute; inset:0 0 auto; height:44px; box-sizing:border-box; display:flex; align-items:center; gap:8px; padding:4px 12px; background:var(--dsw-alias-bg-base); border-bottom:1px solid var(--dsw-alias-border-l3); pointer-events:auto; }
.sm-cockpit-composition-toolbar span { flex:1; min-width:0; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.sm-cockpit-composition button { font:inherit; color:inherit; border:1px solid var(--dsw-alias-border-l3); background:var(--dsw-alias-bg-base); border-radius:6px; min-height:32px; padding:4px 8px; cursor:pointer; }
.sm-cockpit-composition button:focus-visible,.sm-cockpit-divider:focus-visible { outline:2px solid var(--dsw-alias-border-l1, currentColor); outline-offset:-2px; }
.sm-cockpit-composition-canvas { position:absolute; top:44px; bottom:0; left:0; overflow:auto; pointer-events:auto; background:var(--dsw-alias-bg-base); }
.sm-cockpit-divider { position:absolute; top:44px; bottom:0; width:8px; cursor:col-resize; touch-action:none; pointer-events:auto; border-inline:1px solid var(--dsw-alias-border-l3); box-sizing:border-box; background:var(--dsw-alias-bg-base); }
.sm-cockpit-composition-fault { position:absolute; top:16px; left:15%; right:15%; padding:16px; background:var(--dsw-alias-bg-base); border:1px solid var(--dsw-alias-border-l3); pointer-events:auto; }
[data-sm-cockpit-compact] { grid-template-columns:56px minmax(0,1fr) 0px !important; transition:none !important; }
[data-sm-cockpit-compact] > [data-sm-cockpit-sidebar] { z-index:21; }
[data-sm-cockpit-compact] > [data-sm-cockpit-sidebar] + * { grid-column:2; grid-row:1; }
[data-sm-cockpit-compact] > [data-rightbar-col] { grid-column:3; grid-row:1; }
[data-sm-cockpit-compact]:not([data-sidebar-collapsed]) > [data-sm-cockpit-sidebar] { position:absolute; inset:0 auto 0 0; width:min(var(--sm-cockpit-sidebar-width), calc(100% - 56px)); }
[data-sm-cockpit-compact] > [data-sm-cockpit-sidebar] > * { width:100% !important; }
[data-sm-cockpit-compact] > [data-side="sidebar"] { display:none; }
.sm-cockpit-composition .sm-cockpit-navigation-backdrop { position:absolute; inset:0; border:0; border-radius:0; background:transparent; pointer-events:auto; }
.sm-cockpit-composition-region[inert] .sm-cockpit-composition-toolbar,.sm-cockpit-composition-region[inert] .sm-cockpit-composition-canvas { pointer-events:none; }
`;
type Box = { left: number; top: number; width: number; height: number };
type ThemeSource = { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };

/** main/cockpit is a navigation entry only; native main/conversation retains render ownership. */
export function ActivateCockpitComposition({ composition, library, themeSource, goConversation, pageStore,
  listWorkspaceFiles, openWorkspaceFile, readWorkspaceFile }: {
  composition: CockpitComposition; library: LibraryBoardClient; themeSource: ThemeSource; goConversation(): void;
  pageStore?: ReturnType<typeof import('./free-html-library/store.mjs').createFreeHtmlLibraryStore>;
  listWorkspaceFiles?: () => Promise<Array<Record<string, unknown>>>;
  openWorkspaceFile?: (product: Record<string, unknown>) => void;
  readWorkspaceFile?: (product: Record<string, unknown>) => Promise<string | null>;
}) {
  const state = useSyncExternalStore(composition.subscribe, composition.getSnapshot);
  useLayoutEffect(() => {
    if (state.fallback) return;
    const board = library.getSnapshot();
    composition.open((board.preview?.snapshot ?? board.saved)?.spec.session_id);
  }, [composition, library, state.fallback]);
  return state.fallback ? <LibraryCockpitPanel library={library} themeSource={themeSource} goConversation={goConversation} initialSurface="pages" pageStore={pageStore}
    listWorkspaceFiles={listWorkspaceFiles} openWorkspaceFile={openWorkspaceFile} readWorkspaceFile={readWorkspaceFile} />
    : <p role="status">正在打开驾驶舱与原生对话…</p>;
}

export function CockpitCompositionOverlay({ composition, library, themeSource, usePanelInfo, pageStore,
  listWorkspaceFiles, openWorkspaceFile, readWorkspaceFile }: PropsRuntime<'shell.overlay'> & {
  composition: CockpitComposition; library: LibraryBoardClient; themeSource: ThemeSource;
  pageStore?: ReturnType<typeof import('./free-html-library/store.mjs').createFreeHtmlLibraryStore>;
  listWorkspaceFiles?: () => Promise<Array<Record<string, unknown>>>;
  openWorkspaceFile?: (product: Record<string, unknown>) => void;
  readWorkspaceFile?: (product: Record<string, unknown>) => Promise<string | null>;
}) {
  const state = useSyncExternalStore(composition.subscribe, composition.getSnapshot);
  const board = useSyncExternalStore(library.subscribe, library.getSnapshot);
  const panel = usePanelInfo(info => info.activePanelId);
  const anchor = useRef<HTMLDivElement>(null);
  const focusWithin = useRef(false);
  const lease = useRef<ReturnType<typeof leaseNativeComposition> | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const drag = useRef<{ target: HTMLElement; id: number; start: number; base: number; previous: number } | null>(null);
  const shown = board.preview?.snapshot ?? board.layoutDraft ?? board.saved;
  const geometry = compositionGeometry(box?.width ?? 0, state.width, state.showChat && state.sessionAvailable, state.narrowView);
  const cancelDrag = () => {
    const current = drag.current; if (!current) return;
    drag.current = null;
    composition.setWidth(current.previous);
    if (current.target.hasPointerCapture(current.id)) current.target.releasePointerCapture(current.id);
  };
  useEffect(() => {
    if (state.open && panel !== null && panel !== 'cockpit') composition.close();
  }, [panel, state.open, composition]);
  useEffect(() => {
    if (state.open && shown?.spec.session_id) composition.bindSession(shown.spec.session_id);
  }, [state.open, shown?.spec.session_id, composition]);
  useEffect(() => {
    if (geometry.mode !== 'split') cancelDrag();
  }, [geometry.mode]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && drag.current) { event.preventDefault(); cancelDrag(); } };
    window.addEventListener('keydown', escape); window.addEventListener('blur', cancelDrag);
    return () => { window.removeEventListener('keydown', escape); window.removeEventListener('blur', cancelDrag); cancelDrag(); };
  }, [composition]);
  useLayoutEffect(() => {
    if (!state.open || !anchor.current) return;
    const element = anchor.current;
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = element.closest('[data-shell-overlay]')?.parentElement;
    if (!frame) return;
    let native: HTMLElement | null = null, center: HTMLElement | null = null, raf: number | null = null;
    let navigation: ReturnType<typeof leaseCompactNavigation> | null = null;
    let disposed = false;
    const measure = () => {
      raf = null; if (disposed) return;
      const target = nativeCompositionTarget(element);
      if (!target) { lease.current?.dispose(); lease.current = null; navigation?.dispose(); navigation = null; native = null; setBox(null); setNavigationOpen(false); return; }
      const nativeChanged = target.native !== native;
      if (nativeChanged) {
        lease.current?.dispose(); lease.current = null;
        try { lease.current = leaseNativeComposition(target.native); native = target.native; }
        catch { setBox(null); return; }
      }
      if (center !== target.center || !navigation) {
        if (center) observer?.unobserve(center);
        navigation?.dispose(); center = target.center; observer?.observe(center);
        navigation = leaseCompactNavigation(target.frame, center);
      }
      const f = target.frame.getBoundingClientRect();
      setNavigationOpen(navigation.update(f.width));
      const c = target.center.getBoundingClientRect();
      const next = { left: c.left - f.left, top: c.top - f.top, width: c.width, height: c.height };
      setBox(previous => !nativeChanged && previous && Object.keys(next).every(key => previous[key as keyof Box] === next[key as keyof Box]) ? previous : next);
    };
    const schedule = () => { if (!disposed && raf === null) raf = requestAnimationFrame(measure); };
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(schedule);
    observer?.observe(frame);
    const mutation = new MutationObserver(schedule);
    mutation.observe(frame, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-sidebar-collapsed', 'style'] });
    window.addEventListener('resize', schedule);
    measure();
    return () => {
      disposed = true; observer?.disconnect(); mutation.disconnect(); window.removeEventListener('resize', schedule);
      if (raf !== null) cancelAnimationFrame(raf);
      lease.current?.dispose(); lease.current = null;
      navigation?.dispose();
      // Closing a focused overlay must not strand keyboard focus in body.
      if (element.contains(document.activeElement) || (focusWithin.current && document.activeElement === document.body)) {
        if (returnFocus?.isConnected && !returnFocus.closest('[inert]')) returnFocus.focus();
        else native?.querySelector<HTMLElement>('[contenteditable="true"],textarea')?.focus();
      }
      focusWithin.current = false;
    };
  }, [state.open]);
  useLayoutEffect(() => {
    const native = anchor.current && nativeCompositionTarget(anchor.current)?.native;
    const active = document.activeElement;
    const hidingFocusedChat = geometry.chat === 0 && native?.contains(active);
    const hidingFocusedCanvas = geometry.canvas === 0 && anchor.current?.querySelector('.sm-cockpit-composition-canvas')?.contains(active);
    if (hidingFocusedChat || hidingFocusedCanvas) anchor.current?.querySelector<HTMLElement>('[data-testid="composition-toggle-chat"]')?.focus();
    lease.current?.update(geometry.chat, geometry.chat === 0 || navigationOpen);
  }, [box, geometry.chat, geometry.canvas, navigationOpen]);
  if (!state.open) return null;
  return <div ref={anchor} className="sm-cockpit-composition" data-testid="cockpit-composition"
    onFocusCapture={() => { focusWithin.current = true; }}
    onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) focusWithin.current = false; }}>
    <style>{css}</style>
    {navigationOpen ? <button type="button" className="sm-cockpit-navigation-backdrop" aria-label="收起导航，查看驾驶舱"
      onClick={() => composition.toggleSidebar()} /> : null}
    {!box || box.width <= 0 ? <div className="sm-cockpit-composition-fault" role="status">
      <p>正在检查原生页面结构。若无法并排，可使用独立驾驶舱；不会替换原生聊天。</p>
      <button type="button" onClick={() => composition.fallback()}>打开独立驾驶舱</button>
      <button type="button" onClick={() => composition.close()}>返回对话</button>
    </div> : <section className="sm-cockpit-composition-region" style={box} aria-label="驾驶舱与原生对话" data-composition-mode={geometry.mode}
      {...(navigationOpen ? { inert: '' } : {})} aria-hidden={navigationOpen || undefined}>
      <header className="sm-cockpit-composition-toolbar">
        <span>{state.sessionAvailable ? '驾驶舱 · 同一原生会话' : '关联会话不可用 · 已保存看板仍可查看'}</span>
        {geometry.mode === 'chat' ? <button type="button" onClick={() => composition.showCanvas()}>查看画布</button> : null}
        <button type="button" onClick={() => composition.close()}>仅看对话</button>
        <button type="button" data-testid="composition-toggle-chat" disabled={!state.sessionAvailable}
          aria-expanded={geometry.chat > 0} onClick={() => geometry.mode === 'canvas' ? composition.revealChat() : composition.toggleChat()}>
          {geometry.chat > 0 ? '收起原生对话' : '展开原生对话'}</button>
      </header>
      <div className="sm-cockpit-composition-canvas" style={{ width: geometry.canvas, display: geometry.canvas > 0 ? undefined : 'none' }}>
        <LibraryCockpitPanel library={library} themeSource={themeSource} goConversation={() => composition.close()} initialSurface="pages" pageStore={pageStore}
          listWorkspaceFiles={listWorkspaceFiles} openWorkspaceFile={openWorkspaceFile} readWorkspaceFile={readWorkspaceFile} />
      </div>
      {geometry.mode === 'split' ? <div className="sm-cockpit-divider" role="separator" aria-label="调整原生对话宽度" aria-orientation="vertical"
        tabIndex={0} aria-valuemin={CHAT_MIN} aria-valuemax={Math.max(CHAT_MIN, box.width - 568)} aria-valuenow={geometry.chat} style={{ left: geometry.canvas }}
        onPointerDown={event => {
          if (event.button !== 0 || drag.current) return;
          event.preventDefault(); event.currentTarget.focus(); event.currentTarget.setPointerCapture(event.pointerId);
          drag.current = { target: event.currentTarget, id: event.pointerId, start: event.clientX, base: geometry.chat, previous: state.width };
        }}
        onPointerMove={event => {
          const current = drag.current; if (!current || current.id !== event.pointerId) return;
          if (event.buttons === 0) { cancelDrag(); return; }
          composition.setWidth(current.base + current.start - event.clientX);
        }}
        onPointerUp={event => {
          const current = drag.current; if (!current || current.id !== event.pointerId) return;
          composition.setWidth(current.base + current.start - event.clientX); drag.current = null;
          if (current.target.hasPointerCapture(current.id)) current.target.releasePointerCapture(current.id);
        }}
        onPointerCancel={cancelDrag} onLostPointerCapture={cancelDrag}
        onKeyDown={event => {
          const delta = event.shiftKey ? 64 : 16;
          if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault(); composition.setWidth(geometry.chat + (event.key === 'ArrowLeft' ? delta : -delta));
          } else if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault(); composition.setWidth(event.key === 'Home' ? CHAT_MIN : box.width - 568);
          }
        }} /> : null}
    </section>}
  </div>;
}
