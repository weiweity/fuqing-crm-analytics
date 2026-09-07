import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { TOOL_NAME, decodeFixture } from './model.mjs';
import { requestForTool } from './native-evidence.mjs';
import { QUERY_FAMILY, runtimeFamily } from './runtime-family.mjs';
import { apply as applyQueryTool } from './query-tool.ts';

export const name = 'analytics-workbench-b0-tool';
export const inject = ['tools'];

/** The only Host capability contributed by this package. */
export function apply(ctx: Context): void {
  if (runtimeFamily() === QUERY_FAMILY) {
    applyQueryTool(ctx);
    return;
  }
  ctx.tools.register(defineTool({
    name: TOOL_NAME,
    description: 'B0 synthetic fixture only. Request the fixed channel sample from the local run kernel; no real database or arbitrary SQL.',
    parameters: {
      query: { type: 'string', enum: ['channel_repeat_rate'], required: true },
    },
    output: {
      schema: {
        type: 'object', additionalProperties: false,
        properties: {
          schema_version: { type: 'string', const: 'analytics-b0/v1', required: true },
          answer_mode: { type: 'string', const: 'STUB', required: true },
          data_source: { type: 'string', const: 'SYNTHETIC_FIXTURE', required: true },
          fixture_id: { type: 'string', const: 'b0-channel-repeat-2026-09-01', required: true },
          data_as_of: { type: 'string', const: '2026-09-01', required: true },
          channel: { type: 'string', const: '合成渠道 A', required: true },
          customers: { type: 'integer', const: 100, required: true },
          repeat_customers: { type: 'integer', const: 25, required: true },
          repeat_rate: { type: 'number', const: 0.25, required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      // Canonical output is not automatically durable on a DSH tool/result.
      presentationMeta: (_args, value) => ({ ...value }),
    },
    // Transport safety fuses exceed the server's <=30s query budget. The
    // authoritative deadline/step/worker budget comes only from FastAPI.
    timeoutMs: 35000,
    isConcurrencySafe: () => false,
    execute: async (args, exec) => {
      exec.signal.throwIfAborted();
      const token = process.env.B0_RUNTIME_TOKEN;
      const agent = exec.agent;
      if (!token || !agent || agent.id !== process.env.B0_SESSION_ID) throw new Error('B0 tool has no bound execution context');
      const requestId = requestForTool(agent.session.snapshotEvents(), exec.callId);
      if (!requestId) throw new Error('B0 tool has no journal-correlated native request');
      const response = await fetch('http://127.0.0.1:4315/internal/native/fixture', {
        method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: agent.id, request_id: requestId, call_id: exec.callId, query: args.query }),
        signal: AbortSignal.any([exec.signal, AbortSignal.timeout(33000)]), redirect: 'error',
      });
      if (!response.ok) throw new Error('B0 run kernel refused tool execution');
      const receipt = await response.json();
      const result = decodeFixture(receipt.result);
      if (!result) throw new Error('B0 run kernel returned invalid fixture');
      return result;
    },
  }));
}
