/** DSH tool/skill apply for Grok to import. Does not start a second runtime or HTTP. */
import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { freezeCompetitionSkillPackage } from './skill-package.mjs';
import {
  CAPABILITIES_TOOL_NAME, PATCH_TOOL_NAME, RESOURCE_SCHEMA, RESOURCE_TOOL_NAME, STEP_TOOL_NAME,
} from './family.mjs';
import { liveDiagnosisCall } from './tools.mjs';

export const name = 'analytics-workbench-competition-growth';
export const inject = ['skills', 'tools'];

export function apply(ctx: Context, packInput: { manifest: object; contents: Record<string, string> }): void {
  const pack = freezeCompetitionSkillPackage(packInput);
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
        capability_id: { type: 'string' },
        condition_mode: { type: 'string' },
        intent: { type: 'string' },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      },
      timeoutMs: 5000,
      isConcurrencySafe: () => false,
      execute: async args => liveDiagnosisCall(toolName, args) as never,
    }));
  }
}
