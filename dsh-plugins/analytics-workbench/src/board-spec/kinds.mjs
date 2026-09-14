/** Registered renderers. New kinds require a contract and renderer, never arbitrary code. */
export const BOARD_SPEC_KINDS = Object.freeze([
  'METRIC',
  'BAR',
  'LINE',
  'TABLE',
  'TEXT',
  'EVIDENCE',
  'PROCESS',
  'TIMELINE',
  'WATERFALL',
  'FUNNEL',
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
  'set_props',
]);
