/** Closed renderer set for BoardSpec. Not the legacy STYLE_ONLY chart_type list. */
export const BOARD_SPEC_KINDS = Object.freeze([
  'METRIC',
  'BAR',
  'LINE',
  'TABLE',
  'EVIDENCE',
  'html_sandbox',
  'LINK',
]);

export const BOARD_SPEC_OPS = Object.freeze([
  'GENERATE_BOARD',
  'PATCH_BLOCK',
  'ROLLBACK',
]);

export const PATCH_OPS = Object.freeze([
  'set_title',
  'set_kind',
  'set_metric_ref',
  'set_layout',
]);
