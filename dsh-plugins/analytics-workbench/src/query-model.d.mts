export const QUERY_TOOL_NAME: 'analytics_channel_followup_query';
export const QUERY_SCHEMA: 'analytics-channel-followup/v1';
export const QUERY_RECEIPT_SCHEMA: 'analytics-run-channel-followup-native-receipt/v1';
export const QUERY_KERNEL_URL: 'http://127.0.0.1:4315/internal/native/channel-followup';
export const QUERY_RECEIPT_LIMIT: number;
export const JS_MAX_SAFE_INTEGER: 9007199254740991;
export function decodeQueryRequest(value: unknown): Record<string, unknown> | null;
export function decodeQueryReceipt(value: unknown): {
  schema_version: 'analytics-run-channel-followup-native-receipt/v1';
  run_id: string;
  attempt_id: string;
  step_id: string;
  disposition: 'EXECUTE' | 'REUSE_RESULT';
  result: Record<string, unknown>;
} | null;
export function readBoundedJson(response: Response, limit: number): Promise<unknown>;
