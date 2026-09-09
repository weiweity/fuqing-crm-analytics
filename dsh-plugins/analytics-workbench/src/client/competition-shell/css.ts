import { BRAND_ASSET_URLS, competitionCssVars } from './tokens.ts';

const vars = Object.entries(competitionCssVars).map(([name, value]) => `${name}:${value};`).join('');

export const competitionShellCss = `
@font-face {
  font-family: 'Outfit';
  src: url('${BRAND_ASSET_URLS.outfit}') format('truetype');
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}
.sm-competition-root { ${vars}
  box-sizing: border-box; min-height: 100%;
  color: var(--sm-ink);
  background: linear-gradient(180deg, var(--sm-bg-top) 0%, var(--sm-bg) 100%);
  font-family: var(--sm-font-body);
  font-size: 16px; line-height: 24px;
}
.sm-competition-root *, .sm-competition-root *::before, .sm-competition-root *::after { box-sizing: border-box; }
.sm-competition-root.sm-overlay-theme { display: contents; }
.sm-brand-mark { display: inline-flex; align-items: center; gap: 12px; padding: var(--sm-logo-pad); color: var(--sm-ink); }
.sm-brand-mark img {
  display: block; width: var(--sm-logo-width); height: auto; aspect-ratio: var(--sm-logo-ratio);
  object-fit: contain; filter: var(--sm-filter-brand-inverse);
}
.sm-brand-mark.compact img { width: var(--sm-logo-width-compact); }
.sm-brand-mark .sm-brand-copy { display: flex; flex-direction: column; gap: 2px; }
.sm-brand-mark small { color: var(--sm-muted); font-size: 11px; line-height: 1.2; }
.sm-brand-nav {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  padding: 12px 20px; background: var(--sm-nav); border-bottom: 1px solid var(--sm-line);
  backdrop-filter: blur(24px) saturate(130%);
}
.sm-brand-nav-tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.sm-brand-nav a, .sm-brand-nav button, .sm-shell-dialog button, .sm-welcome button, .sm-error-state button {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: var(--sm-touch); min-width: var(--sm-touch); padding: 0 16px;
  border: 1px solid var(--sm-line-strong); border-radius: 12px;
  background: transparent; color: var(--sm-ink); font: 500 14px/22px var(--sm-font-body); cursor: pointer;
}
.sm-brand-nav a[aria-current="page"], .sm-brand-nav button[aria-current="page"] {
  background: var(--sm-nav-active); box-shadow: inset 0 1px 0 rgba(211, 195, 232, 0.16);
}
.sm-brand-nav a:focus-visible, .sm-brand-nav button:focus-visible,
.sm-shell-dialog button:focus-visible, .sm-welcome button:focus-visible,
.sm-error-state button:focus-visible, .sm-page-title a:focus-visible {
  outline: 2px solid var(--sm-purple); outline-offset: 2px;
}
.sm-settings-hint { color: var(--sm-muted); font-size: 12px; line-height: 18px; max-width: 28ch; }
.sm-page-title { padding: 20px 20px 8px; }
.sm-page-title p { margin: 0 0 8px; color: var(--sm-lilac); font-size: 13px; letter-spacing: 0.04em; }
.sm-page-title h1 {
  margin: 0; color: var(--sm-ink); font: 600 28px/36px var(--sm-font-display);
}
.sm-welcome { padding: 12px 20px 24px; }
.sm-welcome h2 { margin: 0 0 8px; color: var(--sm-ink); font: 600 22px/30px var(--sm-font-display); }
.sm-welcome p { margin: 0 0 16px; color: var(--sm-copy); max-width: 52ch; }
.sm-welcome-suggestions { display: flex; flex-direction: column; gap: 8px; margin: 0; padding: 0; list-style: none; }
.sm-error-state, .sm-status-banner, .sm-evidence, .sm-condition-chips {
  margin: 12px 20px; padding: 16px; border: 1px solid var(--sm-line-strong); border-radius: 12px;
  background: var(--sm-glass);
}
.sm-error-state[data-kind="auth"], .sm-error-state[data-kind="forbidden"], .sm-error-state[data-kind="failed"] {
  border-color: var(--sm-danger); background: rgba(255, 125, 145, 0.08);
}
.sm-error-state h2, .sm-evidence h3 { margin: 0 0 8px; font: 600 16px/24px var(--sm-font-body); }
.sm-error-state p, .sm-status-banner p, .sm-evidence p { margin: 0 0 8px; color: var(--sm-copy); }
.sm-status-banner { color: var(--sm-lilac); font-size: 13px; }
.sm-status-banner[data-kind="synthetic"] { border-style: dashed; }
.sm-condition-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.sm-condition-chips span {
  display: inline-flex; align-items: center; min-height: 32px; padding: 0 10px; border-radius: 999px;
  border: 1px solid var(--sm-line); color: var(--sm-lilac); font-size: 12px;
}
.sm-layout-slot { min-width: 0; }
.sm-shell-dialog {
  pointer-events: auto; width: min(760px, calc(100vw - 48px)); max-height: calc(100dvh - 48px);
  overflow: auto; margin: auto; padding: 0 24px 24px; border: 0; border-radius: 18px;
  color: var(--sm-ink); background: var(--sm-bg-top);
  box-shadow: inset 0 1px 0 rgba(211, 195, 232, 0.18), 0 20px 50px rgba(0, 0, 0, 0.50);
  font: 16px/24px var(--sm-font-body);
}
.sm-shell-dialog::backdrop { background: var(--sm-overlay); backdrop-filter: blur(16px); }
.sm-shell-dialog header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 22px 0 12px; }
.sm-shell-dialog h2 { margin: 0; font: 600 18px/26px var(--sm-font-display); color: var(--sm-ink); }
.sm-competition-main { display: flex; flex-direction: column; min-width: 0; }
@media (max-width: 768px) {
  .sm-brand-nav { padding: 12px; }
  .sm-page-title h1 { font-size: 22px; line-height: 30px; }
}
@media (max-width: 390px) {
  .sm-brand-mark small { display: none; }
  .sm-shell-dialog { width: min(100vw - 24px, 760px); padding: 0 16px 16px; }
  .sm-competition-main { display: flex; flex-direction: column; }
}
@media (prefers-reduced-motion: reduce) {
  .sm-competition-root, .sm-brand-nav, .sm-shell-dialog, .sm-welcome button { transition: none; animation: none; }
}
`;
