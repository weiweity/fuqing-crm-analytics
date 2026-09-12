import { useMemo, useState, useSyncExternalStore } from 'react';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import { ThemeProvider } from './competition-shell/index.ts';
import { type CompetitionColorScheme } from './competition-shell/tokens.ts';
import { STAFF_FIXTURE } from '../staff/fixture.mjs';

export const STAFF_PANEL_ID = 'staff';

export type StaffMainPanelProps = PropsRuntime<'main'> & {
  goConversation(): void;
  openPlazaRole?(): void;
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): CompetitionColorScheme };
};

const TABS = [
  { id: 'all' as const, label: '所有员工' },
  { id: 'mine' as const, label: '我的数字员工' },
  { id: 'team' as const, label: '团队对话' },
  { id: 'plaza' as const, label: '数字员工广场' },
];

const css = `
.sm-staff { display:flex; flex-direction:column; min-height:100%; min-width:0; background:var(--sm-bg); color:var(--sm-ink); }
.sm-staff-chrome { padding:16px 24px 12px; display:flex; flex-direction:column; gap:12px; }
.sm-staff-title { display:flex; align-items:center; gap:12px; }
.sm-staff-back {
  border:1px solid var(--sm-purple); background:transparent; color:var(--sm-purple);
  border-radius:4px; min-height:24px; padding:0 8px; font:400 14px/22px var(--sm-font-body); cursor:pointer;
}
.sm-staff-title h1 { margin:0; font:400 18px/25px var(--sm-font-body); }
.sm-staff-search {
  width:100%; min-height:32px; border:1px solid var(--sm-line); border-radius:6px; padding:4px 11px;
  background:transparent; color:var(--sm-ink); font:400 14px/22px var(--sm-font-body);
}
.sm-staff-tabs { display:flex; gap:20px; }
.sm-staff-tabs button {
  border:0; background:transparent; color:var(--sm-muted); font:400 14px/20px var(--sm-font-body);
  padding:0 0 6px; cursor:pointer;
}
.sm-staff-tabs button[data-on="1"] { color:var(--sm-ink); font-weight:500; box-shadow:inset 0 -2px 0 var(--sm-ink); }
.sm-staff-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:12px; padding:8px 24px 24px; }
.sm-staff-card {
  text-align:left; border:1px solid var(--sm-line); border-radius:16px; padding:16px 14px 12px;
  background:var(--sm-bg); color:inherit; cursor:pointer; display:flex; flex-direction:column; gap:8px;
}
.sm-staff-head { display:flex; gap:10px; align-items:center; }
.sm-staff-avatar { width:44px; height:44px; border-radius:22px; background:var(--sm-purple); flex-shrink:0; }
.sm-staff-head h2 { margin:0; font:700 14px/20px var(--sm-font-body); }
.sm-staff-head p { margin:0; color:var(--sm-muted); font:400 12px/17px var(--sm-font-body); }
.sm-staff-on { color:var(--sm-muted); font:400 11px/15px var(--sm-font-body); }
.sm-staff-desc { margin:0; color:var(--sm-muted); font:400 12px/17px var(--sm-font-body); }
.sm-staff-tags { display:flex; gap:6px; flex-wrap:wrap; }
.sm-staff-tags span { background:var(--sm-bg-top); color:var(--sm-purple); border-radius:10px; padding:2px 8px; font:400 11px/15px var(--sm-font-body); }
.sm-staff-stats { display:flex; border:1px solid var(--sm-line); border-radius:10px; }
.sm-staff-stats div { flex:1; text-align:center; padding:8px 0; }
.sm-staff-stats strong { display:block; font:600 16px/22px var(--sm-font-display); }
.sm-staff-stats span { color:var(--sm-muted); font:400 11px/15px var(--sm-font-body); }
.sm-staff-empty { margin:24px; color:var(--sm-muted); font:400 13px/20px var(--sm-font-body); }
`;

export function StaffPanelIcon({ size, active }: PropsRuntime<'sidebar.panellist'>) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" data-testid="sm-staff-panel-icon" data-active={active ? '1' : '0'}>
      <circle cx="6" cy="6" r="2.25" fill="none" stroke="currentColor" strokeWidth="1.25" />
      <circle cx="11" cy="7" r="1.75" fill="none" stroke="currentColor" strokeWidth="1.25" />
      <path d="M2.5 13c.4-2 1.8-3.2 3.5-3.2S9.1 11 9.5 13" fill="none" stroke="currentColor" strokeWidth="1.25" />
      <path d="M9.2 10.2c.5-.3 1.1-.5 1.8-.5 1.4 0 2.5.9 2.8 2.3" fill="none" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

function visibleStaff(tab: typeof TABS[number]['id'], query: string) {
  const q = query.trim();
  const rows = tab === 'mine' ? STAFF_FIXTURE.filter((row) => row.mine) : STAFF_FIXTURE;
  if (!q) return rows;
  return rows.filter((row) => `${row.name}${row.role}${row.desc}`.includes(q));
}

export function StaffMainPanel(props: StaffMainPanelProps) {
  const colorScheme = useSyncExternalStore(props.themeSource.subscribe, props.themeSource.getSnapshot);
  const [root, setRoot] = useState<HTMLDivElement | null>(null);
  const [tab, setTab] = useState<typeof TABS[number]['id']>('mine');
  const [query, setQuery] = useState('');
  const cards = useMemo(() => visibleStaff(tab, query), [tab, query]);
  return (
    <ThemeProvider className="sm-staff-theme" colorScheme={colorScheme} popupRoot={root}>
      <style>{css}</style>
      <div ref={setRoot} className="sm-staff" data-testid="sm-staff-main" data-panel={STAFF_PANEL_ID}>
        <div className="sm-staff-chrome">
          <div className="sm-staff-title">
            <button type="button" className="sm-staff-back" data-testid="sm-staff-back" onClick={() => props.goConversation()}>返回对话</button>
            <h1>数据员工</h1>
          </div>
          <input className="sm-staff-search" data-testid="sm-staff-search" value={query}
            placeholder="搜索员工、职责或 SOP"
            onChange={(event) => setQuery(event.target.value)} />
          <div className="sm-staff-tabs" role="tablist">
            {TABS.map((item) => (
              <button key={item.id} type="button" role="tab" data-on={tab === item.id ? '1' : '0'}
                data-testid={`sm-staff-tab-${item.id}`} onClick={() => setTab(item.id)}>
                {item.label}
              </button>
            ))}
          </div>
        </div>
        {tab === 'team' ? (
          <div className="sm-staff-empty" data-testid="sm-staff-team">
            <p>还没有团队对话</p>
            <p>企业 SOP 仍在飞书。点右侧对话或选一个员工开始。</p>
          </div>
        ) : (
          <div className="sm-staff-grid">
            {cards.map((card) => (
              <button key={card.id} type="button" className="sm-staff-card"
                data-testid={`sm-staff-card-${card.id}`}
                onClick={() => {
                  if (tab === 'plaza') (props.openPlazaRole ?? props.goConversation)();
                  else props.goConversation();
                }}>
                <div className="sm-staff-head">
                  <span className="sm-staff-avatar" aria-hidden="true" />
                  <div>
                    <h2>{card.name}</h2>
                    <p>{card.role}</p>
                    <span className="sm-staff-on">在线</span>
                  </div>
                </div>
                <p className="sm-staff-desc">{card.desc}</p>
                <div className="sm-staff-tags">{card.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
                <div className="sm-staff-stats">
                  <div><strong>{card.docs}</strong><span>资料</span></div>
                  <div><strong>{card.skills}</strong><span>技能</span></div>
                  <div><strong>{card.sops}</strong><span>SOP</span></div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </ThemeProvider>
  );
}
