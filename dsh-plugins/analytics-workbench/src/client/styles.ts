/** Selectors stay inside the plugin; upstream DSH theme tokens remain authoritative. */
export const css = `
.analytics-b0-logo, .analytics-b0-mark { display:block; background:currentColor; mask-repeat:no-repeat; mask-size:contain; mask-position:center; }
.analytics-b0-logo { width:177px; aspect-ratio:249 / 45; margin:8px 0; mask-image:url('/b0/brand/logo.png'); }
.analytics-b0-mark { mask-image:url('/favicon.svg'); }
.analytics-b0-trigger { min-height:44px; width:100%; background:transparent; color:inherit; border:0; border-radius:8px; padding:8px; font:inherit; cursor:pointer; }
.analytics-b0-trigger:hover { background:var(--dsw-alias-interactive-bg-hover); }
.analytics-b0-dialog { pointer-events:auto; box-sizing:border-box; width:min(760px,calc(100vw - 32px)); max-height:calc(100dvh - 32px); overflow:auto; margin:auto; padding:24px; border:1px solid var(--dsw-alias-line-primary,currentColor); border-radius:16px; color:var(--dsw-alias-label-primary,CanvasText); background:var(--dsw-specific-sidebar-fill,Canvas); font:inherit; }
.analytics-b0-dialog::backdrop { background:rgb(0 0 0 / 40%); }
.analytics-b0-dialog header, .analytics-b0-actions { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.analytics-b0-dialog h2 { margin:0; font-size:20px; }
.analytics-b0-dialog h3 { margin:16px 0 8px; font-size:18px; overflow-wrap:anywhere; }
.analytics-b0-dialog p, .analytics-b0-card p { margin:8px 0; line-height:1.6; }
.analytics-b0-dialog button, .analytics-b0-dialog input { box-sizing:border-box; min-height:44px; border:1px solid var(--dsw-alias-line-primary,currentColor); border-radius:8px; padding:8px 12px; font:inherit; color:inherit; background:transparent; }
.analytics-b0-dialog button { cursor:pointer; }
.analytics-b0-dialog button:disabled { opacity:.5; cursor:not-allowed; }
.analytics-b0-dialog a { color:inherit; display:inline-block; min-height:44px; padding:8px 0; box-sizing:border-box; }
.analytics-b0-dialog input { width:100%; margin:8px 0; }
.analytics-b0-dialog table { width:100%; border-collapse:collapse; margin:12px 0; }
.analytics-b0-dialog th, .analytics-b0-dialog td { padding:10px 4px; text-align:left; border-bottom:1px solid var(--dsw-alias-line-primary,currentColor); }
.analytics-b0-dialog small, .analytics-b0-card small { color:var(--dsw-alias-label-secondary,inherit); }
.analytics-b0-dialog :focus-visible, .analytics-b0-trigger:focus-visible { outline:2px solid currentColor; outline-offset:3px; }
.analytics-b0-preview { border:1px dashed currentColor; padding:12px; margin:12px 0; overflow-wrap:anywhere; }
.analytics-b0-card { padding:12px; border:1px solid var(--dsw-alias-line-primary,currentColor); border-radius:8px; overflow-wrap:anywhere; }
.analytics-b0-runs { box-sizing:border-box; flex:none; pointer-events:auto; width:calc(100% - 2 * var(--dsh-composer-side-clearance,16px) - 4 * var(--dsh-composer-dock-inset,8px)); max-width:calc(var(--dsh-composer-card-max-width,780px) - 4 * var(--dsh-composer-dock-inset,8px)); margin:0 auto; padding:8px 12px; border:.5px solid var(--dsw-alias-border-l1,currentColor); border-radius:12px; background:var(--dsw-specific-tip,var(--dsw-alias-bg-base,Canvas)); font:inherit; font-size:12px; line-height:1.6; color:var(--dsw-alias-label-secondary,inherit); overflow-wrap:anywhere; }
.analytics-b0-runs abbr { text-decoration:none; font-variant-numeric:tabular-nums; }
@media (max-width:480px) { .analytics-b0-dialog { padding:16px; } .analytics-b0-dialog th, .analytics-b0-dialog td { font-size:13px; } }
`;
