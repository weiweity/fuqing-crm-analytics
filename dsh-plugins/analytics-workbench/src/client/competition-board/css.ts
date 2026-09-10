export const competitionBoardCss = `
.sm-competition-board, .sm-competition-actions {
  color: var(--sm-ink); font: 16px/24px var(--sm-font-body);
  padding: 0 20px 24px;
}
.sm-competition-board h2, .sm-competition-actions h2 {
  margin: 0 0 8px; color: var(--sm-ink); font: 600 22px/30px var(--sm-font-display);
}
.sm-competition-board h3, .sm-competition-actions h3 {
  margin: 16px 0 8px; color: var(--sm-ink); font: 600 16px/24px var(--sm-font-body);
}
.sm-competition-toolbar, .sm-layout-controls, .sm-scope-chat, .sm-diff, .sm-leave-restore {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 12px 0;
}
.sm-competition-board button, .sm-competition-actions button, .sm-scope-chat button,
.sm-layout-controls button, .sm-endorsement button {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: var(--sm-touch); min-width: var(--sm-touch); padding: 0 16px;
  border: 1px solid var(--sm-line-strong); border-radius: 12px;
  background: transparent; color: var(--sm-ink); font: 500 14px/22px var(--sm-font-body); cursor: pointer;
}
.sm-competition-board button:focus-visible, .sm-competition-actions button:focus-visible,
.sm-layout-controls button:focus-visible, .sm-scope-chat button:focus-visible,
.sm-endorsement button:focus-visible, .sm-competition-board input:focus-visible,
.sm-competition-actions input:focus-visible, .sm-competition-actions textarea:focus-visible,
.sm-scope-chat textarea:focus-visible {
  outline: 2px solid var(--sm-purple); outline-offset: 2px;
}
.sm-competition-board button[aria-pressed="true"], .sm-competition-board button[data-current="1"] {
  background: var(--sm-nav-active);
}
.sm-competition-board button:disabled, .sm-competition-actions button:disabled { opacity: .4; cursor: not-allowed; }
.sm-endorsement-list, .sm-receipt-list, .sm-candidate-list { margin: 0; padding: 0; list-style: none; }
.sm-endorsement-list li, .sm-block, .sm-candidate-card, .sm-draft-card, .sm-diff, .sm-leave-restore {
  margin: 8px 0; padding: 16px; border: 1px solid var(--sm-line-strong); border-radius: 12px;
  background: var(--sm-glass);
}
.sm-endorsement-list label {
  display: flex; gap: 12px; align-items: flex-start; min-height: var(--sm-touch); cursor: pointer;
}
.sm-board-grid {
  display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 12px; min-height: 120px;
}
.sm-block { min-height: var(--sm-touch); position: relative; }
.sm-block[data-selected="1"] { outline: 2px solid var(--sm-purple); outline-offset: 2px; }
.sm-block[data-affected="1"] { outline: 2px dashed var(--sm-signal); outline-offset: 2px; }
.sm-block[data-inflight="1"] { box-shadow: inset 0 0 0 1px var(--sm-signal); }
.sm-block-selected-label { color: var(--sm-signal); font-size: 12px; }
.sm-chart-table { width: 100%; border-collapse: collapse; }
.sm-chart-bar-track { height: 12px; background: var(--sm-glass); margin: 4px 0 12px; }
.sm-chart-bar-track > div { height: 100%; background: var(--sm-signal); }
[data-testid="sm-computed-line"] { margin: 0; }
[data-testid="sm-computed-line"] svg { width: 100%; max-height: 180px; }
[data-testid="sm-computed-line"] polyline { fill: none; stroke: var(--sm-signal); stroke-width: 2; }
[data-testid="sm-computed-line"] circle { fill: var(--sm-signal); }
.sm-chart-table th, .sm-chart-table td {
  text-align: left; padding: 8px 4px; border-bottom: 1px solid var(--sm-line); color: var(--sm-copy);
}
.sm-chart-bar { display: flex; flex-direction: column; gap: 6px; margin: 8px 0; }
.sm-chart-bar-track {
  display: block; height: 8px; border-radius: 999px; background: var(--sm-line);
}
.sm-chart-bar-track i {
  display: block; height: 8px; border-radius: 999px; background: var(--sm-lilac);
}
.sm-scope-chat {
  border: 1px solid var(--sm-line-strong); border-radius: 12px; padding: 12px; background: var(--sm-glass);
}
.sm-scope-chat textarea, .sm-competition-actions textarea, .sm-competition-actions input[type="text"] {
  width: 100%; min-height: var(--sm-touch); padding: 8px 12px; border-radius: 12px;
  border: 1px solid var(--sm-line-strong); background: transparent; color: var(--sm-ink);
  font: 14px/22px var(--sm-font-body);
}
.sm-drag-handle, .sm-resize-handle {
  min-height: var(--sm-touch); min-width: var(--sm-touch);
}
.sm-block-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.sm-competition-board .sm-status-banner { margin: 8px 0; padding: 8px 12px; }
.sm-competition-board .sm-status-banner p { margin: 0; }
.sm-board-details { margin: 8px 0; font: 13px/20px var(--sm-font-body); overflow-wrap: anywhere; }
.sm-board-details summary { cursor: pointer; min-height: var(--sm-touch); align-content: center; }
.sm-board-details summary:focus-visible { outline: 2px solid var(--sm-purple); outline-offset: 2px; }
.sm-block-controls label { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.sm-block-controls select {
  min-height: var(--sm-touch); padding: 0 12px; border-radius: 12px;
  border: 1px solid var(--sm-line-strong); background: var(--sm-bg-top); color: var(--sm-ink);
  font: 14px/22px var(--sm-font-body);
}
.sm-competition-board .ant-radio-wrapper, .sm-competition-actions .ant-radio-wrapper { min-height: var(--sm-touch); align-items: center; }
.sm-phone-only { display: none; }
@media (max-width: 1024px) {
  .sm-competition-board, .sm-competition-actions { padding: 0 12px 20px; }
}
@media (max-width: 768px) {
  .sm-board-grid { grid-template-columns: 1fr; }
  .sm-block { grid-column: 1 / -1 !important; grid-row: auto !important; }
}
@media (max-width: 390px) {
  .sm-phone-only { display: flex; }
  .sm-competition-board .sm-drag-handle, .sm-competition-board .sm-resize-handle { display: none; }
  .sm-competition-board h2 { font-size: 20px; line-height: 28px; }
}
@media (prefers-reduced-motion: reduce) {
  .sm-competition-board, .sm-competition-actions, .sm-block, .sm-chart-bar-track i {
    transition: none; animation: none;
  }
}
`;
