/** DSH tool/skill apply for Grok to import. Does not start a second runtime or HTTP. */
import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { freezeCompetitionSkillPackage } from './skill-package.mjs';
import {
  CAPABILITIES_TOOL_NAME, PATCH_TOOL_NAME, RESOURCE_SCHEMA, RESOURCE_TOOL_NAME, STEP_TOOL_NAME,
} from './family.mjs';
import { createCompetitionToolBoundary } from './boundary.mjs';
import { liveDiagnosisCall } from './tools.mjs';

export const name = 'analytics-workbench-competition-growth';
export const inject = ['skills', 'tools'];

export function apply(ctx: Context, packInput: { manifest: object; contents: Record<string, string> }): void {
  const pack = freezeCompetitionSkillPackage(packInput);
  const boundary = createCompetitionToolBoundary();
  ctx.tools.guard(boundary.guard);
  ctx.on('tools/result', boundary.mark);
  ctx.on('agent/turn-stopping', ({ agent }) => { boundary.clear(agent); });
  ctx.on('agent/disposed', ({ agent }) => { boundary.clear(agent); });
  ctx.skills.register(pack.definition as never);
  ctx.tools.register(defineTool({
    name: RESOURCE_TOOL_NAME,
    description: 'Read one exact registered competition-growth method resource. Examples are not evidence.',
    parameters: { resource: { type: 'string', enum: [...pack.resources], required: true } },
    output: {
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          schema_version: { type: 'string', const: RESOURCE_SCHEMA, required: true },
          package_digest: { type: 'string', required: true },
          resource: { type: 'string', required: true },
          content_digest: { type: 'string', required: true },
          content: { type: 'string', required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    execute: async args => pack.read(args.resource) as never,
  }));
  for (const toolName of [CAPABILITIES_TOOL_NAME, STEP_TOOL_NAME, PATCH_TOOL_NAME]) {
    ctx.tools.register(defineTool({
      name: toolName,
      description: 'Competition diagnosis adapter. Uses COMPETITION_HTTP_BASE when set; otherwise NOT_CONNECTED.',
      parameters: {
        request_id: { type: 'string', required: true },
        ...(toolName === STEP_TOOL_NAME ? {
          capability_id: { type: 'string' as const, required: true as const },
          condition_mode: { type: 'string' as const, enum: ['INHERIT', 'EXPLICIT'], required: true as const },
          condition: { type: 'object' as const, additionalProperties: true,
            description: 'Complete competition-condition/v1 object, validated by backend. Fields: metric_type=GSV; timezone=Asia/Shanghai; current_period and comparison_period each {start_date,end_date,end_bound:INCLUSIVE_CALENDAR_DAY}; comparison_mode (e.g. YOY_SAME_PERIOD); sales_scope and history_scope each {kind:ALL|CHANNEL_IDS|PRODUCT_IDS|CHANNEL_AND_PRODUCT,channel_ids:[],product_ids:[]}; sample_mode=INCLUDE|EXCLUDE_CURRENT_SALES_ONLY|EXCLUDE_AND_RECOMPUTE_HISTORY; sample_channel_ids null for INCLUDE or explicit channel IDs. Never infer a brand ID as a channel ID. No owner/actor/permissions. First request must supply explicit periods and scopes.' },
          condition_patch: { type: 'object' as const, additionalProperties: true,
            description: 'EXPLICIT changes to previous condition, using the same field names. Changing current_period or comparison_mode requires comparison_period. INHERIT must omit both condition objects. Backend validates all fields; never guess sample channels.' },
        } : {}),
        ...(toolName === PATCH_TOOL_NAME ? {
          intent: { type: 'string' as const, enum: ['STYLE_ONLY', 'FILTER_CHANGE', 'STRUCTURE'], required: true as const },
          selection: { type: 'object' as const, additionalProperties: false, properties: {
            board_id: { type: 'string' as const, required: true as const },
            block_id: { type: 'string' as const },
            base_version: { type: 'integer' as const, required: true as const },
          }, description: 'Only the explicit selected target; never invent identifiers or a version.' },
          payload: { type: 'object' as const, additionalProperties: true,
            description: 'Controlled patch payload, validated by backend. For STYLE_ONLY send exactly one display_op, for example {op:"display",card_id:"<selected block>",display_overrides:{}}; FILTER_CHANGE requires filter_change; STRUCTURE requires cockpit_op. No arbitrary scripts or HTML. This tool plans a patch; it does not persist a board.' },
        } : {}),
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      },
      // HTTP computation remains bounded to 5s; leave 2s for a cancel receipt.
      timeoutMs: toolName === STEP_TOOL_NAME ? 7500 : 5000,
      isConcurrencySafe: () => false,
      execute: async (args, exec) => liveDiagnosisCall(toolName, {
        ...args, session_id: exec.agent?.session.id,
      }, exec.signal) as never,
    }));
  }
}
