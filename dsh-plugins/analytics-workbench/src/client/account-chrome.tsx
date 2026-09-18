import { useEffect, useState, useSyncExternalStore } from 'react';
import { defineStore, type PropsStore } from '@deepseek-ai/dsh-client-store';
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots';
import {
  accountSourceLabel,
  clearAccountIdentity,
  getServerAccountIdentity,
  readAccountIdentity,
  subscribeAccountIdentity,
  writeAccountIdentity,
} from './account-identity.mjs';

export { clearAccountIdentity, readAccountIdentity, writeAccountIdentity } from './account-identity.mjs';

const LEGACY_BOARD_URL = 'http://127.0.0.1:15173/';
const THEME_OPTIONS = [
  { id: 'light', label: '日间' },
  { id: 'dark', label: '夜晚' },
  { id: 'system', label: '跟随系统' },
] as const;

export function createAccountStore() {
  return defineStore({
    init: () => ({ menuOpen: false, themeOpen: false }),
    actions: {
      openMenu: draft => { draft.menuOpen = true; draft.themeOpen = false; },
      closeMenu: draft => { draft.menuOpen = false; },
      toggleMenu: draft => { draft.menuOpen = !draft.menuOpen; draft.themeOpen = false; },
      closeTheme: draft => { draft.themeOpen = false; },
      toggleTheme: draft => { draft.themeOpen = !draft.themeOpen; draft.menuOpen = false; },
      closeAll: draft => { draft.menuOpen = false; draft.themeOpen = false; },
    },
  });
}

type AccountStore = ReturnType<typeof createAccountStore>;
type AccountStoreProps = PropsStore<AccountStore>;
type LoginProps = PropsRuntime<'sidebar.footer.action'> & AccountStoreProps;
type ThemeProps = PropsRuntime<'sidebar.footer.action'> & AccountStoreProps & {
  setTheme(id: string): void;
  themeSource: { subscribe(listener: () => void): () => void; getSnapshot(): string };
};
type MenuProps = PropsRuntime<'shell.overlay'> & AccountStoreProps & {
  setTheme?(id: string): void;
  themeSource?: { subscribe(listener: () => void): () => void; getSnapshot(): string };
};

const accountCss = `
[class*="settingsArea"] button[aria-haspopup="dialog"] {
  position:absolute !important; width:1px !important; height:1px !important; padding:0 !important; margin:0 !important;
  overflow:hidden !important; clip:rect(0,0,0,0) !important;
}
[class*="footerActions"] { display:flex; flex-direction:row; align-items:center; gap:8px; }
[class*="footerActions"]:has(.sm-login[data-wide="0"]) {
  flex-direction:column; align-items:center; justify-content:center; gap:6px; width:auto;
}
html, body { min-height: 100%; background: #DCDCE1; }
:has(> [class*="sidebarCol"]) {
  background: rgba(255, 255, 255, 0.28) !important;
  backdrop-filter: blur(40px) saturate(1.15);
  -webkit-backdrop-filter: blur(40px) saturate(1.15);
}
[class*="centerCol"] {
  background: #fff !important;
  --dsw-alias-bg-base: #fff;
}
[class*="centerCol"] [data-conversation-scroll],
[class*="centerCol"] [data-composer-seat] { background: #fff; }
[class*="sidebarCol"] {
  background: rgba(255, 255, 255, 0.10) !important;
  color: #111111;
  -webkit-font-smoothing: antialiased;
  border-right: 0.5px solid rgba(0, 0, 0, 0.06) !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.45);
}
button[aria-label="发送消息"],
button[aria-label="排队发送"],
button[aria-label="插话发送"],
button[aria-label="停止生成"],
button[aria-label="停止对话"],
button[aria-label="Send message"],
button[aria-label="Queue message"],
button[aria-label="Steer message"],
button[aria-label="Stop generating"],
button[aria-label="Stop conversation"] {
  background: var(--dsw-alias-brand-primary, CanvasText) !important;
  color: #fff !important;
}
button[aria-label="发送消息"]:hover:not(:disabled),
button[aria-label="排队发送"]:hover:not(:disabled),
button[aria-label="插话发送"]:hover:not(:disabled),
button[aria-label="停止生成"]:hover:not(:disabled),
button[aria-label="停止对话"]:hover:not(:disabled),
button[aria-label="Send message"]:hover:not(:disabled),
button[aria-label="Queue message"]:hover:not(:disabled),
button[aria-label="Steer message"]:hover:not(:disabled),
button[aria-label="Stop generating"]:hover:not(:disabled),
button[aria-label="Stop conversation"]:hover:not(:disabled) {
  filter: brightness(1.08);
}
[class*="sidebarCol"] { font-weight: 500; }
html[data-ds-dark-theme], html[data-ds-dark-theme] body,
body[data-ds-dark-theme] { background: #2C2C2E; }
html[data-ds-dark-theme] :has(> [class*="sidebarCol"]),
body[data-ds-dark-theme] :has(> [class*="sidebarCol"]) { background: rgba(255, 255, 255, 0.06) !important; }
html[data-ds-dark-theme] [class*="centerCol"],
body[data-ds-dark-theme] [class*="centerCol"] {
  background: #120D1D !important;
  --dsw-alias-bg-base: #120D1D;
}
html[data-ds-dark-theme] [class*="centerCol"] [data-conversation-scroll],
html[data-ds-dark-theme] [class*="centerCol"] [data-composer-seat],
body[data-ds-dark-theme] [class*="centerCol"] [data-conversation-scroll],
body[data-ds-dark-theme] [class*="centerCol"] [data-composer-seat] { background: #120D1D; }
html[data-ds-dark-theme] [class*="sidebarCol"],
body[data-ds-dark-theme] [class*="sidebarCol"] {
  background: rgba(16, 14, 22, 0.18) !important;
  color: #F6F3F8;
  border-right-color: rgba(255, 255, 255, 0.12) !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.sm-login {
  display:flex; align-items:center; justify-content:flex-start; gap:8px; box-sizing:border-box;
  flex:1; width:auto; height:36px; min-height:36px; padding:0 10px; border:0; border-radius:10px;
  background:color-mix(in srgb, Canvas 22%, transparent);
  color:var(--dsw-alias-label-primary,CanvasText);
  box-shadow:inset 0 0 0 0.75px color-mix(in srgb, Canvas 40%, transparent);
  font:var(--dsw-font-s-14,14px/22px inherit); cursor:pointer;
}
.sm-login[data-wide="0"] {
  width:36px; min-width:36px; flex:none; padding:0; justify-content:center; border-radius:18px; gap:0;
}
.sm-login-text { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.sm-login[data-wide="0"] .sm-login-text { display:none; }
.sm-theme {
  display:flex; align-items:center; justify-content:center; box-sizing:border-box;
  width:36px; height:36px; min-width:36px; padding:0; border:0; border-radius:18px;
  background:color-mix(in srgb, Canvas 28%, transparent);
  color:var(--dsw-alias-label-primary,CanvasText); cursor:pointer;
  box-shadow:inset 0 0 0 0.75px color-mix(in srgb, Canvas 45%, transparent);
}
.sm-theme[data-wide="0"] { width:36px; min-width:36px; }
.sm-glass {
  pointer-events:auto; position:fixed; z-index:40; box-sizing:border-box;
  background:color-mix(in srgb, Canvas 86%, transparent);
  border:0.75px solid color-mix(in srgb, CanvasText 12%, transparent);
  box-shadow:0 10px 28px rgb(0 0 0 / 16%);
  backdrop-filter:blur(20px) saturate(1.2);
  color:var(--dsw-alias-label-primary,CanvasText);
  font:var(--dsw-font-s-14,14px/22px inherit);
}
.sm-account-menu { padding:12px 8px 8px; border-radius:16px; }
.sm-theme-menu { display:flex; gap:6px; padding:8px; border-radius:16px; }
.sm-account-user { display:flex; align-items:center; gap:10px; padding:4px 8px 10px; }
.sm-account-avatar {
  display:flex; align-items:center; justify-content:center;
  width:28px; height:28px; border-radius:14px; flex:none;
  background:var(--dsw-alias-brand-primary,CanvasText); color:#fff;
}
.sm-account-user strong { display:block; font:var(--dsw-font-base-strong-14,600 14px/20px inherit); }
.sm-account-user span { color:var(--dsw-alias-label-secondary,GrayText); font:var(--dsw-font-s-12,12px/18px inherit); }
.sm-account-rule {
  height:1px; margin:2px 8px 6px;
  background:color-mix(in srgb, currentColor 12%, transparent);
}
.sm-account-row {
  display:flex; align-items:center; gap:10px; width:100%; box-sizing:border-box;
  padding:9px 8px; border:0; border-radius:10px;
  background:transparent; color:inherit; text-align:left; text-decoration:none;
  font:inherit; cursor:pointer;
}
.sm-account-row svg { flex:none; opacity:.88; }
.sm-account-row:hover { background:var(--dsw-alias-interactive-bg-hover,rgb(0 0 0 / 6%)); }
.sm-theme-choice {
  display:flex; flex-direction:column; align-items:center; gap:4px; width:64px; padding:8px 4px;
  border:0; border-radius:12px; background:transparent; color:inherit; cursor:pointer;
  font:var(--dsw-font-s-12,12px/16px inherit);
}
.sm-theme-choice[aria-pressed="true"] {
  background:var(--dsw-alias-brand-primary,CanvasText); color:#fff;
}
.sm-account-signin { display:flex; gap:6px; align-items:center; padding:4px 8px 8px; }
.sm-account-signin input {
  flex:1; min-width:0; height:32px; box-sizing:border-box; padding:0 8px; border:0; border-radius:8px;
  background:color-mix(in srgb, CanvasText 8%, transparent); color:inherit; font:inherit;
}
.sm-account-signin button {
  flex:none; height:32px; padding:0 10px; border:0; border-radius:8px; cursor:pointer;
  background:var(--dsw-alias-brand-primary,CanvasText); color:#fff; font:inherit;
}
.sm-account-signin button:disabled { opacity:.4; cursor:default; }
`;

function UserIcon({ size = 16 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="8" cy="5.2" r="2.4" stroke="currentColor" strokeWidth="1.4" />
    <path d="M3.2 13.2c.6-2.4 2.3-3.6 4.8-3.6s4.2 1.2 4.8 3.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>;
}

function SunIcon() {
  return <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="8" cy="8" r="3.1" stroke="currentColor" strokeWidth="1.4" />
    <path d="M8 1.6v1.5M8 12.9v1.5M1.6 8h1.5M12.9 8h1.5M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M11.5 4.5l1.1-1.1M3.4 12.6l1.1-1.1"
      stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>;
}

function MoonIcon() {
  return <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M13 10.2A5.2 5.2 0 1 1 7.1 3.1 4.2 4.2 0 0 0 13 10.2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
  </svg>;
}

function SystemIcon() {
  return <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <rect x="2.5" y="3.5" width="11" height="8" rx="1.4" stroke="currentColor" strokeWidth="1.4" />
    <path d="M6 13.2h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>;
}

function nativeSettingsButton(): HTMLButtonElement | null {
  const doc = typeof document === 'undefined' ? undefined : document;
  if (!doc) return null;
  const node = doc.querySelector('[class*="settingsArea"] button[aria-haspopup="dialog"]')
    ?? doc.querySelector('[class*="footArea"] button[aria-haspopup="dialog"]');
  return node instanceof HTMLButtonElement ? node : null;
}

function useAnchorBox(open: boolean, testId: string) {
  const [box, setBox] = useState(null as null | { left: number; width: number; bottom: number });
  useEffect(() => {
    if (!open || typeof document === 'undefined') return;
    const view = typeof window === 'undefined' ? undefined : window;
    const trigger = document.querySelector(`[data-testid="${testId}"]`);
    if (!(trigger instanceof HTMLElement)) return;
    const rail = trigger.closest('[class*="footArea"]') ?? trigger.parentElement;
    const update = () => {
      const t = trigger.getBoundingClientRect();
      const r = rail instanceof HTMLElement ? rail.getBoundingClientRect() : t;
      const narrow = r.width < 80;
      setBox({
        left: r.left,
        width: narrow ? Math.max(r.width, 220) : r.width,
        bottom: Math.max(8, (view?.innerHeight ?? 0) - t.top + 6),
      });
    };
    update();
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(update) : null;
    ro?.observe(trigger);
    if (rail instanceof HTMLElement) ro?.observe(rail);
    view?.addEventListener?.('resize', update);
    return () => { ro?.disconnect(); view?.removeEventListener?.('resize', update); };
  }, [open, testId]);
  return box;
}

function BoardIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <rect x="2.5" y="3" width="11" height="10" rx="1.6" stroke="currentColor" strokeWidth="1.4" />
    <path d="M2.5 6.5h11M7 6.5v6.5" stroke="currentColor" strokeWidth="1.4" />
  </svg>;
}

function GearIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.4" />
    <path d="M8 2.2v1.3M8 12.5v1.3M2.2 8h1.3M12.5 8h1.3M4.1 4.1l.9.9M11 11l.9.9M11.9 4.1l-.9.9M5 11l-.9.9"
      stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>;
}

export function LoginFooter(props: LoginProps) {
  const open = props.useStore(state => state.menuOpen);
  const identity = useSyncExternalStore(subscribeAccountIdentity, readAccountIdentity, getServerAccountIdentity);
  const label = identity?.name ?? '未登录';
  return <><style>{accountCss}</style>
    <button type="button" className="sm-login" data-testid="shine-account-login"
      data-wide={props.wide ? '1' : '0'}
      aria-haspopup="menu" aria-expanded={open}
      aria-label={label} title={label} onClick={() => props.actions.toggleMenu()}>
      <UserIcon size={props.wide ? 16 : 18} />
      <span className="sm-login-text">{label}</span>
    </button></>;
}

export function ThemeFooter(props: ThemeProps) {
  const preference = useSyncExternalStore(
    props.themeSource.subscribe, props.themeSource.getSnapshot, props.themeSource.getSnapshot,
  );
  const open = props.useStore(state => state.themeOpen);
  const label = preference === 'light' ? '日间' : preference === 'dark' ? '夜晚' : '跟随系统';
  return <><style>{accountCss}</style>
    <button type="button" className="sm-theme" data-testid="shine-account-theme"
      data-wide={props.wide ? '1' : '0'}
      aria-haspopup="menu" aria-expanded={open}
      aria-label={`外观：${label}`} title={`外观：${label}`} onClick={() => props.actions.toggleTheme()}>
      {preference === 'dark' ? <MoonIcon /> : preference === 'light' ? <SunIcon /> : <SystemIcon />}
    </button></>;
}

export function AccountMenu(props: MenuProps) {
  const menuOpen = props.useStore(state => state.menuOpen);
  const themeOpen = props.useStore(state => state.themeOpen);
  const readTheme = props.themeSource?.getSnapshot ?? (() => 'system');
  const preference = useSyncExternalStore(
    props.themeSource?.subscribe ?? (() => () => {}),
    readTheme,
    readTheme,
  );
  useEffect(() => {
    if (!menuOpen && !themeOpen) return;
    const view = typeof window === 'undefined' ? undefined : window;
    const doc = typeof document === 'undefined' ? undefined : document;
    if (typeof view?.addEventListener !== 'function' || !doc) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') props.actions.closeAll(); };
    const onPointer = (event: Event) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      const inside = doc.querySelector('[data-testid="shine-account-menu"], [data-testid="shine-theme-menu"]');
      const login = doc.querySelector('[data-testid="shine-account-login"]');
      const theme = doc.querySelector('[data-testid="shine-account-theme"]');
      if (inside?.contains(target) || login?.contains(target) || theme?.contains(target)) return;
      props.actions.closeAll();
    };
    view.addEventListener('keydown', onKey);
    view.addEventListener('pointerdown', onPointer);
    return () => {
      view.removeEventListener('keydown', onKey);
      view.removeEventListener('pointerdown', onPointer);
    };
  }, [menuOpen, themeOpen, props.actions]);
  const accountBox = useAnchorBox(menuOpen, 'shine-account-login');
  const themeBox = useAnchorBox(themeOpen, 'shine-account-theme');
  const openSettings = () => {
    props.actions.closeAll();
    const trigger = nativeSettingsButton();
    if (!trigger) return;
    const later = typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function'
      ? window.requestAnimationFrame.bind(window)
      : (fn: () => void) => { setTimeout(fn, 0); };
    later(() => { trigger.click(); });
  };
  const identity = useSyncExternalStore(subscribeAccountIdentity, readAccountIdentity, getServerAccountIdentity);
  const accountStyle = accountBox
    ? { left: accountBox.left, width: accountBox.width, bottom: accountBox.bottom }
    : undefined;
  const themeStyle = themeBox
    ? { left: themeBox.left, width: themeBox.width, bottom: themeBox.bottom }
    : undefined;
  return <><style>{accountCss}</style>
    {menuOpen ? <div className="sm-glass sm-account-menu" role="dialog" aria-label="账户"
      data-testid="shine-account-menu" style={accountStyle}>
      <div className="sm-account-user">
        <span className="sm-account-avatar" aria-hidden="true"><UserIcon size={16} /></span>
        <div>
          <strong>{identity?.name ?? '未登录'}</strong>
          <span>{accountSourceLabel(identity)}</span>
        </div>
      </div>
      <div className="sm-account-rule" />
      {identity ? (
        <button type="button" className="sm-account-row" data-testid="shine-account-signout"
          onClick={() => clearAccountIdentity()}>
          退出</button>
      ) : (
        <form className="sm-account-signin" onSubmit={event => {
          event.preventDefault();
          const form = event.currentTarget;
          writeAccountIdentity({ name: String(new FormData(form).get('name') ?? ''), source: 'feishu' });
          form.reset();
        }}>
          <input name="name" data-testid="shine-account-name-input" placeholder="显示名称" aria-label="显示名称" />
          <button type="submit" data-testid="shine-account-signin">登录</button>
        </form>
      )}
      <a className="sm-account-row" href={LEGACY_BOARD_URL} target="_blank" rel="noopener noreferrer"
        data-testid="legacy-board-open" onClick={() => props.actions.closeMenu()}>
        <BoardIcon />比赛看板</a>
      <button type="button" className="sm-account-row" data-testid="shine-account-settings" onClick={openSettings}>
        <GearIcon />设置</button>
    </div> : null}
    {themeOpen ? <div className="sm-glass sm-theme-menu" role="menu" aria-label="外观"
      data-testid="shine-theme-menu" style={themeStyle}>
      {THEME_OPTIONS.map(option => (
        <button key={option.id} type="button" role="menuitemradio" className="sm-theme-choice"
          data-testid={`shine-theme-${option.id}`} aria-pressed={preference === option.id}
          aria-label={option.label} onClick={() => { props.setTheme?.(option.id); props.actions.closeTheme(); }}>
          {option.id === 'light' ? <SunIcon /> : option.id === 'dark' ? <MoonIcon /> : <SystemIcon />}
          {option.label}
        </button>
      ))}
    </div> : null}
  </>;
}
