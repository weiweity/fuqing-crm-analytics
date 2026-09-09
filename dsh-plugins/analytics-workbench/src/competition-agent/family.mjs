/** Competition-growth skill family. Grok registers this into pack-skills/FAMILIES. */

export const SKILL_NAME = 'competition-growth';
export const RESOURCE_TOOL_NAME = 'competition_growth_skill_resource';
export const CAPABILITIES_TOOL_NAME = 'competition_growth_capabilities';
export const STEP_TOOL_NAME = 'competition_growth_step';
export const PATCH_TOOL_NAME = 'competition_growth_patch';
export const FAMILY = 'competition_growth';
export const SCHEMA_VERSION = 'competition-growth-skill-package/v1';
export const RESOURCE_SCHEMA = 'competition-growth-skill-resource/v1';
export const SCOPE = 'COMPETITION_SYNTHETIC_ONLY';
export const PROVIDER = 'analytics-competition-approved-bundle';
export const VERSION_PATTERN = /^cg-v[1-9][0-9]*$/;
export const SKILL_VERSION = 'cg-v1';
export const PACKAGE_LIMITS = Object.freeze({ files: 16, fileBytes: 32768, totalBytes: 65536 });
export const REGISTERED_TOOLS = Object.freeze([
  RESOURCE_TOOL_NAME, CAPABILITIES_TOOL_NAME, STEP_TOOL_NAME, PATCH_TOOL_NAME,
]);
export const FORBIDDEN_EXPANSIONS = Object.freeze([
  '/api/v1/audience/table', '/api/v1/audience/summary', '/api/v1/analytics/catalog',
  'analytics_b0_query', 'analytics_channel_followup_query', 'analytics_first_purchase_query',
  'execute_sql', 'run_script', 'shell',
]);
export const STEP_CAPABILITIES = Object.freeze([
  'diag.gsv', 'diag.yoy', 'diag.last_week_same_weekday', 'diag.promo_dual_window',
  'diag.channel', 'diag.sample_exclude_current', 'diag.sample_recompute_history',
  'diag.new_old', 'diag.member', 'diag.product', 'diag.rfm',
  'diag.fixed_cohort', 'diag.non_repurchase', 'action.draft',
]);
export const SELECTED_EDIT_PORT = 'a7.selected_edit';
