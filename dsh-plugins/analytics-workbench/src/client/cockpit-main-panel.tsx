import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import { ThemeProvider } from './competition-shell/index.ts';
import { type CompetitionColorScheme } from './competition-shell/tokens.ts';
import { BoardSpecCanvas } from './board-spec-canvas.tsx';
import { summarizeGenerate } from '../board-spec/generate.mjs';
import { catalogFromGsvItems } from '../board-spec/facts-from-result.mjs';

export const COCKPIT_PANEL_ID = 'cockpit';

type BoardStoreSlice = {
  boardSpec?: object | null;
  boardFacts?: object | null;
  boardError?: string;
  pendingGenerate?: { spec: object; facts: object | null } | null;
  boardEpoch?: number;
};

export type BoardLive = {
  subscribe(listener: () => void): () => void;
  getSnapshot(): BoardStoreSlice;
  actions: {
    confirmGenerate?(): void;
    cancelGenerate?(): void;
    refreshBoard?(): void;
    setFactsCatalog?(catalog: object | null): void;
    proposeGenerate?(payload?: { spec?: object; facts?: object | null }): void;
  };
};

export type CockpitMainPanelProps = PropsRuntime<'main'> & {
  goConversation(): void;
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
  useStore?(selector: (state: BoardStoreSlice) => unknown): unknown;
  actions?: BoardLive['actions'];
  board?: BoardLive;
  askTransport?: { fetchImpl: typeof fetch; path?: string; resultsPath?: string };
};

const emptySlice: BoardStoreSlice = {
  boardSpec: null, boardFacts: null, boardError: '', pendingGenerate: null, boardEpoch: 0,
};

const chromeCss = `
.sm-cockpit-main { display:flex; flex-direction:column; min-height:100%; min-width:0; }
.sm-cockpit-main > .sm-spec-shell { flex:1; min-height:0; }
.sm-cockpit-empty { padding:16px 24px; color:var(--sm-ink); }
.sm-cockpit-empty h1 { margin:12px 0 8px; font:400 18px/25px var(--sm-font-body); }
.sm-cockpit-empty p { margin:0; color:var(--sm-muted); font:400 13px/20px var(--sm-font-body); }
.sm-cockpit-empty button {
  border:1px solid var(--sm-purple); background:transparent; color:var(--sm-purple);
  border-radius:4px; min-height:24px; padding:0 8px; font:400 14px/22px var(--sm-font-body); cursor:pointer;
}
.sm-cockpit-main { position:relative; }
.sm-generate-dim {
  position:absolute; inset:0; background:rgba(9,5,13,.4); display:flex; align-items:center; justify-content:center; z-index:2;
}
.sm-generate-modal {
  width:min(520px, 92%); background:var(--sm-bg); border:1px solid var(--sm-line); border-radius:12px;
  padding:20px 24px; display:flex; flex-direction:column; gap:12px; color:var(--sm-ink);
}
.sm-generate-modal h2 { margin:0; font:500 16px/19px var(--sm-font-body); }
.sm-generate-modal p { margin:0; color:var(--sm-muted); font:400 12px/16px var(--sm-font-body); }
.sm-generate-actions { display:flex; justify-content:flex-end; gap:8px; }
.sm-generate-cancel {
  border:1px solid var(--sm-line); background:transparent; color:var(--sm-muted);
  border-radius:6px; padding:6px 12px; cursor:pointer; font:400 12px/14px var(--sm-font-body);
}
.sm-generate-write {
  border:0; background:var(--sm-purple); color:var(--sm-bg);
  border-radius:6px; padding:6px 12px; cursor:pointer; font:500 12px/14px var(--sm-font-body);
}
`;

export function CockpitPanelIcon({ size, active }: PropsRuntime<'sidebar.panellist'>) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" data-testid="sm-cockpit-panel-icon" data-active={active ? '1' : '0'}>
      <rect x="1.5" y="1.5" width="6" height="6" rx="1" fill="none" stroke="currentColor" strokeWidth="1.25" />
      <rect x="8.5" y="1.5" width="6" height="4" rx="1" fill="none" stroke="currentColor" strokeWidth="1.25" />
      <rect x="1.5" y="8.5" width="6" height="6" rx="1" fill="none" stroke="currentColor" strokeWidth="1.25" />
      <rect x="8.5" y="6.5" width="6" height="8" rx="1" fill="none" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

export function CockpitMainPanel(props: CockpitMainPanelProps) {
  const colorScheme = useSyncExternalStore(props.themeSource.subscribe, props.themeSource.getSnapshot);
  const [root, setRoot] = useState<HTMLDivElement | null>(null);
  const cachedSlice = useRef(emptySlice);
  const slice = useSyncExternalStore(
    (onChange) => (props.board ? props.board.subscribe(onChange) : () => {}),
    () => {
      if (props.board) return props.board.getSnapshot();
      const next = typeof props.useStore === 'function' ? {
        boardSpec: props.useStore((state) => state.boardSpec ?? null) as object | null,
        boardFacts: props.useStore((state) => state.boardFacts ?? null) as object | null,
        boardError: String(props.useStore((state) => state.boardError ?? '') ?? ''),
        pendingGenerate: props.useStore((state) => state.pendingGenerate ?? null) as BoardStoreSlice['pendingGenerate'],
        boardEpoch: Number(props.useStore((state) => state.boardEpoch ?? 0) ?? 0),
      } : emptySlice;
      const prev = cachedSlice.current;
      if (prev.boardSpec === next.boardSpec && prev.boardFacts === next.boardFacts
        && prev.boardError === next.boardError && prev.pendingGenerate === next.pendingGenerate
        && prev.boardEpoch === next.boardEpoch) return prev;
      cachedSlice.current = next;
      return next;
    },
  );
  const spec = slice.boardSpec ?? null;
  const facts = slice.boardFacts ?? null;
  const error = String(slice.boardError ?? '');
  const pending = slice.pendingGenerate ?? null;
  const epoch = Number(slice.boardEpoch ?? 0);
  const actions = props.board?.actions ?? props.actions;
  useEffect(() => {
    if (!spec) return;
    actions?.refreshBoard?.();
    const http = props.askTransport;
    const resultsPath = http?.resultsPath;
    if (!http?.fetchImpl || !resultsPath || !actions?.setFactsCatalog) return;
    void (async () => {
      try {
        const res = await http.fetchImpl(resultsPath);
        if (!res || !res.ok) return;
        const body = await res.json();
        const items = Array.isArray(body.items) ? body.items : [];
        const catalog = catalogFromGsvItems(items);
        if (Object.keys(catalog).length === 0) return;
        actions.setFactsCatalog?.(catalog);
        actions.refreshBoard?.();
      } catch { /* keep generate-time facts */ }
    })();
  }, [spec, epoch, actions, props.askTransport]);
  return (
    <ThemeProvider className="sm-cockpit-theme" colorScheme={colorScheme} popupRoot={root}>
      <style>{chromeCss}</style>
      <div
        ref={setRoot}
        className="sm-cockpit-main"
        data-testid="sm-cockpit-main"
        data-panel={COCKPIT_PANEL_ID}
      >
        {spec ? (
          <BoardSpecCanvas key={epoch} spec={spec} facts={facts} goConversation={() => props.goConversation()}
            askTransport={props.askTransport} />
        ) : (
          <div className="sm-cockpit-empty" data-testid="sm-cockpit-empty">
            <button type="button" data-testid="sm-cockpit-back" onClick={() => props.goConversation()}>返回对话</button>
            <h1>驾驶舱</h1>
            <p>{error || '还没有看板。回对话点「生成驾驶舱」。产物进入驾驶舱，不改 DSH 壳。'}</p>
          </div>
        )}
        {pending ? (
          <div className="sm-generate-dim" data-testid="sm-generate-modal">
            <div className="sm-generate-modal" role="dialog" aria-labelledby="sm-generate-title">
              <h2 id="sm-generate-title">GENERATE_BOARD · 写入 BoardSpec v1</h2>
              <p>{summarizeGenerate(pending.spec)}</p>
              <div className="sm-generate-actions">
                <button type="button" className="sm-generate-cancel" data-testid="sm-generate-cancel"
                  onClick={() => actions?.cancelGenerate?.()}>取消</button>
                <button type="button" className="sm-generate-write" data-testid="sm-generate-confirm"
                  onClick={() => actions?.confirmGenerate?.()}>确认生成这份驾驶舱</button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </ThemeProvider>
  );
}
