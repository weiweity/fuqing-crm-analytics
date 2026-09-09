import { kernelUrl } from './runtime-endpoints.ts';
import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { requestForTool } from './native-evidence.mjs';
import { isRegisteredSession } from './runtime-family.mjs';
import {
  FIRST_PURCHASE_RECEIPT_LIMIT, FIRST_PURCHASE_TOOL_NAME,
  decodeFirstPurchaseReceipt, decodeFirstPurchaseRequest, readBoundedJson, receiptMatchesRequest,
  type FirstPurchaseNativeReceipt,
} from './first-purchase-query-model.mjs';

const queryConsts = {
  schema_version: { type: 'string' as const, const: 'analytics-first-purchase-path/v1', required: true as const },
  query_id: { type: 'string' as const, const: 'first_purchase_product_path', required: true as const },
  query_version: { type: 'string' as const, const: 'first-purchase-path-query/v1', required: true as const },
  metric_id: { type: 'string' as const, const: 'first_purchase_product_n_day_finished', required: true as const },
  metric_version: { type: 'string' as const, const: 'first-purchase-path-metric/v1', required: true as const },
};

function cancelledError(): Error {
  const error = new Error('first-purchase run was cancelled');
  error.name = 'FirstPurchaseCancelled';
  return error;
}

export function apply(ctx: Context): void {
  ctx.tools.register(defineTool({
    name: FIRST_PURCHASE_TOOL_NAME,
    description: 'Synthetic first-purchase path query only. Submit the registered request to the local run kernel; no owner, permission_scope, SQL, or client facts.',
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
      data_snapshot_ref: { type: 'string', const: 'synthetic-first-purchase-v1', required: true as const },
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
          schema_version: { type: 'string', const: 'analytics-run-first-purchase-native-receipt/v1', required: true as const },
          run_id: { type: 'string', required: true as const },
          request_id: { type: 'string', required: true as const },
          call_id: { type: 'string', required: true as const },
          attempt_id: { type: 'string', required: true as const },
          step_id: { oneOf: [{ type: 'null' as const }, { type: 'string' as const }], required: true as const },
          disposition: { type: 'string', enum: ['EXECUTE', 'REUSE_RESULT', 'IN_FLIGHT'], required: true as const },
          run_status: {
            type: 'string',
            enum: ['QUEUED', 'RUNNING', 'NEEDS_INPUT', 'SUCCEEDED', 'FAILED', 'CANCELLING', 'CANCELLED', 'UNKNOWN'],
            required: true as const,
          },
          result: { oneOf: [{ type: 'null' as const }, { type: 'object' as const, additionalProperties: true as const }], required: true as const },
        },
      },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      presentationMeta: (_args, value) => value,
    },
    timeoutMs: 35000,
    isConcurrencySafe: () => false,
    execute: async (args, exec): Promise<FirstPurchaseNativeReceipt> => {
      exec.signal.throwIfAborted();
      const token = process.env.B0_RUNTIME_TOKEN;
      const agent = exec.agent;
      if (!token || !agent || !isRegisteredSession(agent.id)) throw new Error('first-purchase tool has no bound execution context');
      const request = decodeFirstPurchaseRequest(args);
      if (!request) throw new Error('first-purchase tool rejected invalid parameters');
      const requestId = requestForTool(agent.session.snapshotEvents(), exec.callId);
      if (!requestId) throw new Error('first-purchase tool has no journal-correlated native request');
      const response = await fetch(kernelUrl('/internal/native/first-purchase'), {
        method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: agent.id, request_id: requestId, call_id: exec.callId, request }),
        signal: AbortSignal.any([exec.signal, AbortSignal.timeout(33000)]), redirect: 'error',
      });
      if (response.status !== 200 && response.status !== 202) {
        let body: unknown = null;
        try { body = await readBoundedJson(response, FIRST_PURCHASE_RECEIPT_LIMIT); }
        catch { await response.body?.cancel(); }
        const code = body && typeof body === 'object' && 'error' in body
          ? (body as { error?: { code?: unknown } }).error?.code : undefined;
        if (code === 'RUN_CANCELLED') throw cancelledError();
        throw new Error(code === 'TOOL_FAILED' ? 'first-purchase run failed' : 'first-purchase run kernel refused tool execution');
      }
      const receipt = decodeFirstPurchaseReceipt(await readBoundedJson(response, FIRST_PURCHASE_RECEIPT_LIMIT));
      if (!receipt || !receiptMatchesRequest(receipt, request, { requestId, callId: exec.callId })) {
        throw new Error('first-purchase run kernel returned invalid receipt');
      }
      if (response.status === 202 && receipt.disposition !== 'IN_FLIGHT') {
        throw new Error('first-purchase run kernel returned invalid receipt');
      }
      return receipt;
    },
  }));
}
