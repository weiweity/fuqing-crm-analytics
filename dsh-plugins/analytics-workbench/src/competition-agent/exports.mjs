/** Wiring exports for Grok. Do not register from this module into client/index. */

import {
  CAPABILITIES_TOOL_NAME, FAMILY, PATCH_TOOL_NAME, REGISTERED_TOOLS,
  RESOURCE_TOOL_NAME, SELECTED_EDIT_PORT, SKILL_NAME, STEP_TOOL_NAME,
} from './family.mjs';
import { TOOL_SPECS } from './tools.mjs';
import { selectedEditEvent } from './selected-edit.mjs';

export const integration = Object.freeze({
  owner: 'A7',
  skill_name: SKILL_NAME,
  family: FAMILY,
  register_in: Object.freeze([
    'dsh-plugins/analytics-workbench/src/skill-package.mjs FAMILIES',
    'dsh-plugins/analytics-workbench/pack-skills.mjs',
    'dsh-plugins/analytics-workbench/src/skills.ts',
    'dsh-plugins/analytics-workbench/src/tool.ts',
  ]),
  do_not_edit: Object.freeze([
    'dsh-plugins/analytics-workbench/src/index.ts',
    'dsh-plugins/analytics-workbench/src/client/index.tsx',
    'backend/main.py',
  ]),
  tools: REGISTERED_TOOLS,
  skill_resource_tool: RESOURCE_TOOL_NAME,
  step_tool: STEP_TOOL_NAME,
  capabilities_tool: CAPABILITIES_TOOL_NAME,
  patch_tool: PATCH_TOOL_NAME,
  selected_edit_port: SELECTED_EDIT_PORT,
  second_runtime: false,
  live_transport: 'NOT_CONNECTED',
  apply_module: 'dsh-plugins/analytics-workbench/src/competition-agent/apply.ts',
  pack_module: 'dsh-plugins/analytics-workbench/src/competition-agent/pack-skill.mjs',
  python_adapter: 'backend.services.analytics.competition_diagnosis',
  tool_specs: TOOL_SPECS,
});

export { selectedEditEvent, TOOL_SPECS };
