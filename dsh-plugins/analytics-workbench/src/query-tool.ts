import { kernelUrl } from './runtime-endpoints.ts';
import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { requestForTool } from './native-evidence.mjs';
import { isRegisteredSession } from './runtime-family.mjs';
import {
  QUERY_RECEIPT_LIMIT, QUERY_TOOL_NAME,
  decodeQueryReceipt, decodeQueryRequest, readBoundedJson,
} from './query-model.mjs';

const countFields = {
  channel_mature_cohort_count: { type: 'integer' as const, required: true as const },
  channel_immature_count: { type: 'integer' as const, required: true as const },
  channel_repeat_count: { type: 'integer' as const, required: true as const },
  channel_cross_channel_count: { type: 'integer' as const, required: true as const },
  channel_repeat_ratio: {
    oneOf: [{ type: 'null' as const }, { type: 'number' as const }] as const, required: true as const,
  },
  channel_cross_channel_ratio: {
    oneOf: [{ type: 'null' as const }, { type: 'number' as const }] as const, required: true as const,
  },
  channel_window_net_paid_minor: {
    oneOf: [{ type: 'null' as const }, { type: 'integer' as const }] as const, required: true as const,
  },
  channel_empty_reason: {
    oneOf: [{ type: 'null' as const }, { type: 'string' as const, const: 'EMPTY_MATURE_COHORT' as const }] as const,
    required: true as const,
  },
};
const countsSchema = {
  type: 'object' as const, additionalProperties: false as const,
  properties: countFields,
};
const channelRowSchema = {
  type: 'object' as const, additionalProperties: false as const,
  properties: { channel_id: { type: 'string' as const, enum: ['A', 'B'] as const, required: true as const }, ...countFields },
};
const queryConsts = {
  schema_version: { type: 'string' as const, const: 'analytics-channel-followup/v1', required: true as const },
  query_id: { type: 'string' as const, const: 'channel_first_observed_followup', required: true as const },
  query_version: { type: 'string' as const, const: 'channel-followup-query/v1', required: true as const },
  metric_id: { type: 'string' as const, const: 'channel_first_observed_n_day_repeat', required: true as const },
  metric_version: { type: 'string' as const, const: 'channel-followup-metric/v1', required: true as const },
};

export function apply(ctx: Context): void {
  ctx.tools.register(defineTool({
    name: QUERY_TOOL_NAME,
    description: 'Synthetic channel-follow-up query only. Submit the full registered G2 request to the local run kernel; no real database or arbitrary SQL.',
    parameters: {
      ...queryConsts,
      cohort_window: {
        type: 'object' as const, additionalProperties: false as const, required: true as const,
        properties: {
          kind: { type: 'string', const: 'FIXED', required: true as const },
          start_date: { type: 'string', required: true as const },
          end_date: { type: 'string', required: true as const },
        },
      },
      observation_days: { type: 'integer', enum: [30, 60, 90], required: true as const },
      data_snapshot_ref: { type: 'string', const: 'synthetic-channel-followup-v1', required: true as const },
      timezone: { type: 'string', const: 'Asia/Shanghai', required: true as const },
      channel_ids: { type: 'array', items: { type: 'string', enum: ['A', 'B'] }, required: true as const },
      cohort_ref: { type: 'null', required: true as const },
      product_ids: { type: 'array', items: { type: 'string' }, required: true as const },
      exclude_low_price: { type: 'boolean', const: false, required: true as const },
      comparison: { type: 'null', required: true as const },
    },
    output: {
      schema: {
        type: 'object' as const, additionalProperties: false as const,
        properties: {
          schema_version: { type: 'string', const: 'analytics-run-channel-followup-native-receipt/v1', required: true as const },
          run_id: { type: 'string', required: true as const },
          attempt_id: { type: 'string', required: true as const },
          step_id: { type: 'string', required: true as const },
          disposition: { type: 'string', enum: ['EXECUTE', 'REUSE_RESULT'], required: true as const },
          result: {
            type: 'object' as const, additionalProperties: false as const, required: true as const,
            properties: {
              ...queryConsts,
              answer_mode: { type: 'string', const: 'DETERMINISTIC_TOOL', required: true as const },
              data_version: { type: 'string', const: 'synthetic-channel-followup-data/v1', required: true as const },
              hash_version: { type: 'string', const: 'channel-followup-filter-hash/v1', required: true as const },
              contains_real_data: { type: 'boolean', const: false, required: true as const },
              data_source: { type: 'string', const: 'SYNTHETIC_SNAPSHOT', required: true as const },
              data_snapshot_ref: { type: 'string', const: 'synthetic-channel-followup-v1', required: true as const },
              as_of: { type: 'string', required: true as const },
              filter_hash: { type: 'string', required: true as const },
              limitations: { type: 'array', items: { type: 'string' }, required: true as const },
              resolved_filters: {
                type: 'object' as const, additionalProperties: false as const, required: true as const,
                properties: {
                  ...queryConsts,
                  data_version: { type: 'string', const: 'synthetic-channel-followup-data/v1', required: true as const },
                  hash_version: { type: 'string', const: 'channel-followup-filter-hash/v1', required: true as const },
                  cohort_window_kind: { type: 'string', const: 'FIXED', required: true as const },
                  resolved_cohort_start: { type: 'string', required: true as const },
                  resolved_cohort_end: { type: 'string', required: true as const },
                  observation_days: { type: 'integer', enum: [30, 60, 90], required: true as const },
                  data_snapshot_ref: { type: 'string', const: 'synthetic-channel-followup-v1', required: true as const },
                  as_of: { type: 'string', required: true as const },
                  timezone: { type: 'string', const: 'Asia/Shanghai', required: true as const },
                  channel_ids: { type: 'array', items: { type: 'string', enum: ['A', 'B'] }, required: true as const },
                  cohort_ref: { type: 'null', required: true as const },
                  product_ids: { type: 'array', items: { type: 'string' }, required: true as const },
                  exclude_low_price: { type: 'boolean', const: false, required: true as const },
                  comparison: { type: 'null', required: true as const },
                  permission_scope: { type: 'string', required: true as const },
                  data_digest: { type: 'string', required: true as const },
                  filter_hash: { type: 'string', required: true as const },
                },
              },
              facts: {
                type: 'object' as const, additionalProperties: false as const, required: true as const,
                properties: {
                  display_name: { type: 'string', const: '首次观察到的渠道 / N日二单率', required: true as const },
                  currency: { type: 'string', const: 'CNY', required: true as const },
                  amount_unit: { type: 'string', const: 'minor', required: true as const },
                  amount_precision: { type: 'string', const: 'integer_fen', required: true as const },
                  observation_days: { type: 'integer', enum: [30, 60, 90], required: true as const },
                  channels: { type: 'array', items: channelRowSchema, required: true as const },
                  totals: { ...countsSchema, required: true as const },
                },
              },
            },
          },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (_args, value) => value,
    },
    timeoutMs: 35000,
    isConcurrencySafe: () => false,
    execute: async (args, exec) => {
      exec.signal.throwIfAborted();
      const token = process.env.B0_RUNTIME_TOKEN;
      const agent = exec.agent;
      if (!token || !agent || !isRegisteredSession(agent.id)) throw new Error('query tool has no bound execution context');
      const request = decodeQueryRequest(args);
      if (!request) throw new Error('query tool rejected invalid parameters');
      const requestId = requestForTool(agent.session.snapshotEvents(), exec.callId);
      if (!requestId) throw new Error('query tool has no journal-correlated native request');
      const response = await fetch(kernelUrl('/internal/native/channel-followup'), {
        method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: agent.id, request_id: requestId, call_id: exec.callId, request }),
        signal: AbortSignal.any([exec.signal, AbortSignal.timeout(33000)]), redirect: 'error',
      });
      if (!response.ok) { await response.body?.cancel(); throw new Error('query run kernel refused tool execution'); }
      const receipt = decodeQueryReceipt(await readBoundedJson(response, QUERY_RECEIPT_LIMIT));
      if (!receipt) throw new Error('query run kernel returned invalid receipt');
      return receipt as never;
    },
  }));
}
