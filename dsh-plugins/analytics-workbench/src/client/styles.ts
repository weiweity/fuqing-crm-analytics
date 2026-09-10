/** Selectors stay inside the plugin; upstream DSH theme tokens remain authoritative.
 * Geometry follows ui-primitives Button (36×18) / Input (32×8) / Modal (r24, layer-2).
 * DESIGN.md Vue 44px touch and Outfit/Deep Plum are not applied to the DSH native chrome.
 * Competition brand tokens live in ./competition-shell/ and must not paint analytics-b0-* rules.
 */
export {
  competitionTokens, antdTheme, antdSeedToken, competitionCssVars, BRAND_ASSET_URLS,
} from './competition-shell/tokens.ts';
export { competitionShellCss } from './competition-shell/css.ts';

export const css = `
.analytics-b0-logo, .analytics-b0-mark { display:block; background:currentColor; mask-repeat:no-repeat; mask-size:contain; mask-position:center; }
.analytics-b0-logo { width:177px; aspect-ratio:249 / 45; margin:8px 0; mask-image:url('/b0/brand/logo.png'); }
.analytics-b0-mark { mask-image:url('/favicon.svg'); }
.analytics-b0-trigger {
  display:flex; align-items:center; justify-content:flex-start; box-sizing:border-box;
  width:100%; height:36px; min-height:36px; padding:0 10px 0 8px; border:0; border-radius:12px;
  background:transparent; color:var(--dsw-alias-label-primary,inherit);
  font:var(--dsw-font-s-14,14px/22px inherit); cursor:pointer;
}
.analytics-b0-trigger:hover { background:var(--dsw-alias-interactive-bg-hover); }
.analytics-b0-trigger:active { background:var(--dsw-alias-interactive-bg-active); }
.analytics-b0-dialog {
  pointer-events:auto; box-sizing:border-box; width:min(760px,calc(100vw - 48px));
  max-height:calc(100dvh - 48px); overflow:auto; margin:auto; padding:0 24px 24px; border:0;
  border-radius:24px; color:var(--dsw-alias-label-primary,CanvasText);
  background:var(--dsw-alias-bg-layer-2,var(--dsw-specific-sidebar-fill,Canvas));
  box-shadow:var(--dsw-elevation-prominent,0 12px 32px rgb(0 0 0 / 8%));
  font:var(--dsw-font-s-14,14px/22px inherit);
}
.analytics-b0-dialog.analytics-cockpit-http, .analytics-b0-dialog.analytics-cockpit, .analytics-b0-dialog.analytics-saved-analysis {
  width:min(1100px,calc(100vw - 48px));
}
.analytics-b0-dialog::backdrop {
  background:var(--dsw-alias-bg-mask-1,rgb(0 0 0 / 24%));
  backdrop-filter:var(--dsw-mask-blur,blur(2px));
}
.analytics-b0-dialog header, .analytics-b0-actions {
  display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap;
  padding:22px 0 12px;
}
.analytics-b0-dialog h2 { margin:0; font:var(--dsw-font-base-strong-16,500 16px/24px inherit); }
.analytics-b0-dialog h3 { margin:16px 0 8px; font:var(--dsw-font-s-strong-14,500 14px/22px inherit); overflow-wrap:anywhere; }
.analytics-b0-dialog p, .analytics-b0-card p { margin:8px 0; }
.analytics-b0-dialog button:not(.ant-btn), .analytics-query-card button, .analytics-dsh-btn {
  display:inline-flex; align-items:center; justify-content:center; gap:4px; box-sizing:border-box;
  height:36px; min-height:36px; border:.5px solid var(--dsw-alias-border-l3,var(--dsw-alias-line-primary,currentColor));
  border-radius:18px; padding:0 14px; font:var(--dsw-font-s-14,14px/22px inherit);
  color:var(--dsw-alias-label-primary,inherit); background:transparent; cursor:pointer;
}
.analytics-b0-dialog button:not(.ant-btn):hover:not(:disabled), .analytics-query-card button:hover:not(:disabled), .analytics-dsh-btn:hover:not(:disabled) {
  background:var(--dsw-alias-interactive-bg-hover);
}
.analytics-b0-dialog button:not(.ant-btn):active:not(:disabled), .analytics-query-card button:active:not(:disabled) {
  background:var(--dsw-alias-interactive-bg-active);
}
.analytics-b0-dialog button:not(.ant-btn):disabled, .analytics-query-card button:disabled, .analytics-dsh-btn:disabled { opacity:.4; cursor:not-allowed; }
.analytics-b0-dialog a { color:inherit; display:inline-flex; align-items:center; min-height:36px; padding:0; }
.analytics-b0-dialog input:not([type="radio"]):not([type="checkbox"]):not(.ant-input):not(.ant-select-selection-search-input) {
  box-sizing:border-box; width:100%; height:32px; min-height:32px; margin:8px 0; padding:0 8px;
  border:.5px solid var(--dsw-alias-border-l4,currentColor); border-radius:8px;
  background:var(--dsw-alias-bg-layer-1,transparent); color:inherit;
  font:var(--dsw-font-s-14,14px/22px inherit);
}
.analytics-b0-dialog input:not([type="radio"]):not([type="checkbox"]):not(.ant-input):not(.ant-select-selection-search-input):focus { outline:none; border-color:var(--dsw-alias-brand-primary,currentColor); }
.analytics-b0-dialog table { width:100%; border-collapse:collapse; margin:12px 0; }
.analytics-b0-dialog th, .analytics-b0-dialog td {
  padding:10px 4px; text-align:left;
  border-bottom:.5px solid var(--dsw-alias-border-l2,var(--dsw-alias-line-primary,currentColor));
}
.analytics-b0-dialog small, .analytics-b0-card small {
  color:var(--dsw-alias-label-secondary,inherit); font:var(--dsw-font-xxs-12,12px/18px inherit);
}
.analytics-b0-dialog :focus-visible, .analytics-b0-trigger:focus-visible, .analytics-query-card button:focus-visible {
  outline:2px solid var(--dsw-alias-brand-primary,currentColor); outline-offset:2px;
}
.analytics-b0-preview {
  border:.5px dashed var(--dsw-alias-border-l3,currentColor); border-radius:12px; padding:12px; margin:12px 0;
  overflow-wrap:anywhere; background:var(--dsw-specific-tip,transparent);
}
.analytics-b0-card {
  padding:12px 14px; border:.5px solid var(--dsw-alias-border-l2,var(--dsw-alias-line-primary,currentColor));
  border-radius:12px; background:var(--dsw-alias-bg-layer-1,transparent); overflow-wrap:anywhere;
}
.analytics-query-card { font:var(--dsw-font-base-16,16px/24px inherit); overflow-wrap:anywhere; word-break:break-word; max-width:100%; }
.analytics-query-card p, .analytics-query-card small { margin:6px 0; overflow-wrap:anywhere; word-break:break-word; font-variant-numeric:tabular-nums; }
.analytics-query-card button { margin:8px 8px 0 0; }
.analytics-query-card abbr { text-decoration:underline dotted; font-variant-numeric:tabular-nums; }
.analytics-b0-runs {
  box-sizing:border-box; flex:none; pointer-events:auto;
  width:calc(100% - 2 * var(--dsh-composer-side-clearance,16px) - 4 * var(--dsh-composer-dock-inset,8px));
  max-width:calc(var(--dsh-composer-card-max-width,780px) - 4 * var(--dsh-composer-dock-inset,8px));
  margin:0 auto; padding:8px 12px; border:.5px solid var(--dsw-alias-border-l1,currentColor); border-radius:12px;
  background:var(--dsw-specific-tip,var(--dsw-alias-bg-base,Canvas));
  font:var(--dsw-font-xxs-12,12px/18px inherit); color:var(--dsw-alias-label-secondary,inherit); overflow-wrap:anywhere;
}
.analytics-b0-runs abbr { text-decoration:none; font-variant-numeric:tabular-nums; }
.analytics-b0-dialog .analytics-cockpit-card { min-height:36px; }
.analytics-cockpit-toolbar { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
.analytics-cockpit-toolbar button[aria-pressed="true"] { background:var(--dsw-alias-interactive-bg-active); }
.analytics-asset-context { display:flex; flex-wrap:wrap; align-items:baseline; gap:0 16px; }
.analytics-asset-context details { flex:1; min-width:160px; }
.analytics-asset-context summary { cursor:pointer; min-height:36px; align-content:center; }
.analytics-asset-context details[open] { flex-basis:100%; }
.analytics-asset-context details p { overflow-wrap:anywhere; }
.analytics-b0-dialog .sm-competition-board, .analytics-b0-dialog .sm-competition-actions { padding-inline:0; }
.analytics-cockpit-card[data-card-error="1"] { border-style:dashed; color:var(--dsw-alias-state-error-primary,inherit); }
@media (max-width:480px) {
  .analytics-b0-dialog { padding:0 16px 16px; width:min(100vw - 24px, 760px); }
  .analytics-b0-dialog th, .analytics-b0-dialog td { font:var(--dsw-font-xs-13,13px/20px inherit); }
}
@media (prefers-reduced-motion: reduce) {
  .analytics-b0-dialog, .analytics-b0-card, .analytics-b0-trigger, .analytics-query-card button { transition:none; animation:none; }
}
`;
