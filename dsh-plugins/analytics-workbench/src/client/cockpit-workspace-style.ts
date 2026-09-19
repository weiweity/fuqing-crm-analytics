export const cockpitCss = `
.sm-library-theme { height:100%; min-height:0; }
.sm-library-workspace { --sm-bg:#fff; --sm-surface:#fff; --sm-ink:#171717; --sm-muted:#737373; --sm-line:#e7e7e7; --sm-purple:#ff6b35; --sm-danger:#b42318; --lib-rail:#f7f7f7;
  container:cockpit / inline-size; color:#171717; background:#f7f7f7; height:100%; min-height:560px; min-width:0; display:flex; flex-direction:column;
  font:14px/1.55 var(--sm-font-body,'PingFang SC',sans-serif); position:relative; }
.sm-library-workspace * { box-sizing:border-box; }
.sm-library-workspace button,.sm-library-workspace input,.sm-library-workspace select,.sm-library-workspace textarea { font:inherit; color:inherit; }
.sm-library-workspace button { min-height:34px; padding:6px 12px; border:1px solid #e4e4e4; border-radius:7px; background:#fff; cursor:pointer; }
.sm-library-workspace button:hover:not(:disabled) { background:#f5f5f5; border-color:#ccc; }
.sm-library-workspace button:disabled { opacity:.45; cursor:not-allowed; }
.sm-library-workspace :is(button,input,select,textarea,a):focus-visible { outline:2px solid #ff6b35; outline-offset:3px; }
.sm-library-workspace button.cockpit-primary { background:#f2642e; color:#fff; border-color:#f2642e; font-weight:500; }
.sm-library-workspace button.cockpit-primary:hover:not(:disabled) { background:#dd5523; border-color:#dd5523; }
.sm-library-workspace h1,.sm-library-workspace h2,.sm-library-workspace h3,.sm-library-workspace p { margin:0; }
.sm-library-pagehead { flex-shrink:0; min-height:68px; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:12px 24px; background:#fff; border-bottom:1px solid #e7e7e7; }
.cockpit-heading { display:flex; align-items:center; gap:14px; min-width:0; }
.cockpit-heading h1 { font-size:18px; font-weight:600; letter-spacing:.02em; }
.cockpit-heading small { display:block; font-size:11px; color:#737373; letter-spacing:.06em; }
.cockpit-head-actions { display:flex; gap:8px; align-items:center; }
.cockpit-shell-body { flex:1; display:flex; min-height:0; min-width:0; position:relative; }
.sm-library-rail { width:248px; flex:0 0 248px; padding:20px 14px; border-right:1px solid #e7e7e7; display:flex; flex-direction:column; gap:16px; overflow:auto; background:#f7f7f7; }
.sm-library-rail[hidden] { display:none; }
.cockpit-rail-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.cockpit-rail-heading h2 { font-size:14px; font-weight:600; }
.cockpit-rail-heading button { padding:2px 8px; min-height:28px; }
.cockpit-muted { color:#737373; font-size:12px; line-height:1.7; overflow-wrap:anywhere; }
.cockpit-eyebrow { color:#8c8c8c; font-size:11px; letter-spacing:.08em; }
.cockpit-rail-status { padding:12px; border:1px solid #e7e7e7; border-radius:8px; background:#fff; }
.cockpit-rail-status p + button { margin-top:8px; }
.sm-library-products ul { padding:0; margin:6px 0 14px; list-style:none; }
.sm-library-products .cockpit-group { display:flex; align-items:center; width:100%; background:transparent; border:0; text-align:left; padding:5px 8px; color:#777; font-size:12px; }
.cockpit-group span:last-child { margin-left:auto; }
.sm-library-products .cockpit-product { display:flex; width:100%; gap:10px; text-align:left; padding:11px 10px; background:transparent; border:1px solid transparent; margin:3px 0; }
.sm-library-products li[data-selected="1"] .cockpit-product { background:#fff; border-color:#e5e5e5; box-shadow:0 1px 3px #00000006; }
.cockpit-file-icon { font:600 10px/30px monospace; width:30px; height:32px; text-align:center; flex-shrink:0; background:#eee; border-radius:5px; color:#777; }
li[data-selected="1"] .cockpit-file-icon { color:#d65625; background:#fff0e9; }
.cockpit-product-copy { min-width:0; flex:1; }
.cockpit-product-copy strong { display:block; font-size:13px; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cockpit-product-copy small { display:block; font-size:11px; color:#888; margin-top:3px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cockpit-rail-footer { margin-top:auto; border-top:1px solid #e7e7e7; padding:12px 8px 0; }
.sm-library-canvas { display:flex; flex-direction:column; flex:1; min-width:0; min-height:0; background:#fff; }
.sm-library-pathbar { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; padding:16px 24px; border-bottom:1px solid #eee; }
.sm-library-pathbar h2 { font-size:16px; font-weight:550; overflow-wrap:anywhere; }
.cockpit-badge { display:inline-block; border:1px solid #e5e5e5; border-radius:5px; padding:2px 7px; font-size:11px; color:#777; white-space:nowrap; }
.cockpit-badge.pending { color:#b34b21; background:#fff4ed; border-color:#ffd8c4; }
.cockpit-content { flex:1; min-height:0; min-width:0; display:flex; flex-direction:column; }
.cockpit-editor-layout { display:flex; flex:1; min-width:0; min-height:0; position:relative; }
.cockpit-editor-canvas { display:flex; flex-direction:column; flex:1; min-width:0; min-height:0; }
.cockpit-document-tools { display:flex; flex-wrap:wrap; align-items:center; gap:8px; min-height:48px; padding:10px 20px; border-bottom:1px solid #eee; }
.cockpit-document-tools button { font-size:12px; min-height:28px; padding:3px 8px; border-color:transparent; background:transparent; color:#626262; }
.cockpit-tool-actions { margin-left:auto; display:flex; gap:6px; flex-wrap:wrap; }
.cockpit-frame-wrap { flex:1; min-height:360px; display:flex; min-width:0; background:#f7f7f7; }
.cockpit-html-frame { display:block; border:0; width:100%; height:100%; min-height:440px; flex:1; background:white; }
.cockpit-sidebar { width:308px; flex:0 0 308px; background:#fafafa; border-left:1px solid #e7e7e7; display:flex; flex-direction:column; min-height:0; }
.cockpit-sidebar-header { display:flex; justify-content:space-between; align-items:center; padding:16px 18px; border-bottom:1px solid #e7e7e7; }
.cockpit-sidebar-header h2 { font-size:14px; font-weight:600; }
.cockpit-sidebar-header button { border:0; background:transparent; font-size:22px; padding:0 6px; line-height:1; }
.cockpit-sidebar-body { display:flex; flex-direction:column; gap:14px; padding:20px; overflow:auto; }
.cockpit-sidebar-body h3 { font-size:15px; font-weight:500; overflow-wrap:anywhere; }
.cockpit-sidebar-tools { display:flex; flex-direction:column; gap:8px; border-top:1px solid #e7e7e7; padding-top:18px; margin-top:10px; }
.cockpit-selection-hint { color:#ff6b35; font-size:32px; line-height:1; padding-top:20px; }
.cockpit-field { display:flex; flex-direction:column; align-items:stretch; gap:7px; font-size:12px; color:#626262; }
.cockpit-field input:not([type=checkbox]),.cockpit-field select,.cockpit-field textarea { width:100%; min-width:0; border:1px solid #ddd; background:#fff; border-radius:6px; padding:8px 10px; color:#171717; font-size:13px; }
.cockpit-field textarea { resize:vertical; min-height:62px; }
.cockpit-field input[type=checkbox] { align-self:flex-start; accent-color:#f2642e; }
.cockpit-board-form { display:flex; flex-direction:column; gap:14px; }
.cockpit-board-form hr { width:100%; border:0; border-top:1px solid #e7e7e7; }
.cockpit-notice { display:flex; flex-wrap:wrap; align-items:center; gap:10px; padding:14px 20px; background:#fff7f1; border-bottom:1px solid #f0ded2; font-size:13px; }
.cockpit-notice > div:first-child { flex:1; min-width:180px; }
.cockpit-notice p { color:#7b675a; font-size:12px; }
.cockpit-change { overflow-wrap:anywhere; }
.cockpit-error { color:#a12e21; background:#fff4f2; padding:10px 20px; border-bottom:1px solid #f4ddd8; font-size:12px; }
.cockpit-live { font-size:12px; color:#626262; padding:7px 20px; background:#fafafa; border-bottom:1px solid #eee; }
.cockpit-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; margin:auto; padding:48px 24px; gap:12px; max-width:480px; min-height:320px; }
.cockpit-empty-mark { font-size:36px; color:#b5b5b5; border:1px solid #ddd; border-radius:14px; width:64px; height:64px; display:grid; place-items:center; margin-bottom:10px; }
.cockpit-empty h2 { font-size:20px; font-weight:500; }
.cockpit-empty p { font-size:13px; color:#777; }
.cockpit-board-wrap { flex:1; overflow:auto; padding:24px; min-width:0; }
.sm-library-workspace .sm-layout-scroll { max-height:none; }
.sm-library-workspace .sm-layout-block { border-radius:10px; background:#fff; }
.cockpit-source { font:11px/1.65 monospace; white-space:pre-wrap; overflow-wrap:anywhere; max-height:500px; overflow:auto; }
.cockpit-history-row { display:flex; align-items:center; justify-content:space-between; gap:12px; font-size:12px; padding:8px 0; border-bottom:1px solid #eee; }
.cockpit-modal-backdrop { position:absolute; inset:0; z-index:50; background:#17171744; display:grid; place-items:center; padding:20px; }
.cockpit-modal { width:min(440px,100%); background:#fff; border:1px solid #e7e7e7; border-radius:14px; padding:24px; box-shadow:0 20px 80px #0002; display:flex; flex-direction:column; gap:16px; }
.cockpit-modal h2 { font-size:18px; }
.cockpit-modal-actions { display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }
@container cockpit (max-width:760px) {
  .sm-library-pagehead { padding:12px 16px; gap:8px; }
  .cockpit-heading small,.cockpit-back-label { display:none; }
  .cockpit-heading { gap:8px; }
  .cockpit-head-actions { gap:5px; }
  .sm-library-workspace button { padding:6px 9px; }
  .sm-library-rail { position:absolute; inset:0; z-index:30; width:100%; border:0; }
  .sm-library-workspace[data-mobile-inspector=true] .cockpit-editor-layout:has(.cockpit-sidebar) > .cockpit-editor-canvas { display:none; }
  .sm-library-workspace[data-mobile-inspector=false] .cockpit-sidebar { display:none; }
  .cockpit-mobile-context { display:flex; gap:8px; padding:10px 16px; border-bottom:1px solid #eee; }
  .cockpit-mobile-context button[aria-pressed=true] { color:#b34b21; background:#fff4ed; border-color:#ffd8c4; }
  .cockpit-sidebar { width:100%; flex:1; border:0; }
  .sm-library-pathbar { padding:12px 16px; }
  .cockpit-document-tools { padding:10px 14px; }
  .cockpit-board-wrap { padding:14px; }
}
@media (prefers-reduced-motion:reduce) { .sm-library-workspace * { scroll-behavior:auto!important; transition:none!important; } }
`;
