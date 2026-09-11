import { useState, useSyncExternalStore } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import Button from 'antd/es/button';
import { ThemeProvider } from './competition-shell/index.ts';
import { type CompetitionColorScheme } from './competition-shell/tokens.ts';
import { BoardWorkbench } from './competition-board/index.ts';
import { createHttpBoardTransport } from './competition-board/transport.mjs';
import { competitionHttpOptions } from './competition-http.mjs';
import { PRODUCT_NAME } from './brand-surface.mjs';

export const COCKPIT_PANEL_ID = 'cockpit';

export type CockpitMainPanelProps = PropsRuntime<'main'> & {
  goConversation(): void;
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
};

const chromeCss = `
.sm-cockpit-main { display:flex; flex-direction:column; min-height:100%; min-width:0; }
.sm-cockpit-toolbar {
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  padding:12px 16px; border-bottom:1px solid var(--sm-line); background: var(--sm-nav);
}
.sm-cockpit-toolbar h1 { margin:0; font:600 16px/24px var(--sm-font-body); color:var(--sm-ink); }
.sm-cockpit-body { flex:1; min-height:0; overflow:auto; }
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
  const competitionHttp = competitionHttpOptions();
  return (
    <ThemeProvider className="sm-cockpit-theme" colorScheme={colorScheme} popupRoot={root}>
      <style>{chromeCss}</style>
      <div
        ref={setRoot}
        className="sm-cockpit-main"
        data-testid="sm-cockpit-main"
        data-panel={COCKPIT_PANEL_ID}
      >
        <header className="sm-cockpit-toolbar">
          <Button type="default" data-testid="sm-cockpit-back" onClick={() => props.goConversation()}>返回对话</Button>
          <h1>{PRODUCT_NAME}</h1>
        </header>
        <div className="sm-cockpit-body">
          <BoardWorkbench
            initialPanel={competitionHttp ? 'board' : undefined}
            modelAvailable={false}
            transport={competitionHttp ? createHttpBoardTransport(competitionHttp) : undefined}
          />
        </div>
      </div>
    </ThemeProvider>
  );
}
