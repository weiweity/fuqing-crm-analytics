export const FIRST_PURCHASE_TOOL_NAME: 'analytics_first_purchase_query';
export const FIRST_PURCHASE_SCHEMA: 'analytics-first-purchase-path/v1';
export const FIRST_PURCHASE_RECEIPT_SCHEMA: 'analytics-run-first-purchase-native-receipt/v1';
export const FIRST_PURCHASE_KERNEL_URL: 'http://127.0.0.1:4315/internal/native/first-purchase';
export const FIRST_PURCHASE_RECEIPT_LIMIT: number;
export const JS_MAX_SAFE_INTEGER: 9007199254740991;

export type FirstPurchaseQueryRequest = {
  schema_version: 'analytics-first-purchase-path/v1';
  query_id: 'first_purchase_product_path';
  query_version: 'first-purchase-path-query/v1';
  metric_id: 'first_purchase_product_n_day_finished';
  metric_version: 'first-purchase-path-metric/v1';
  cohort_window: { kind: 'FIXED'; start_date: string; end_date: string };
  observation_days: 30 | 60 | 90;
  data_snapshot_ref: 'synthetic-first-purchase-v1';
  timezone: 'Asia/Shanghai';
  channel_ids: Array<'A' | 'B'>;
  cohort_ref: null;
  product_ids: [];
  exclude_low_price: false;
  comparison: null;
};

export type FirstPurchaseResolvedFilters = {
  schema_version: 'analytics-first-purchase-path/v1';
  query_id: 'first_purchase_product_path';
  query_version: 'first-purchase-path-query/v1';
  metric_id: 'first_purchase_product_n_day_finished';
  metric_version: 'first-purchase-path-metric/v1';
  data_version: 'synthetic-first-purchase-data/v1';
  hash_version: 'first-purchase-path-filter-hash/v1';
  cohort_window_kind: 'FIXED';
  resolved_cohort_start: string;
  resolved_cohort_end: string;
  observation_days: 30 | 60 | 90;
  data_snapshot_ref: 'synthetic-first-purchase-v1';
  as_of: string;
  timezone: 'Asia/Shanghai';
  channel_ids: Array<'A' | 'B'>;
  cohort_ref: null;
  product_ids: [];
  exclude_low_price: false;
  comparison: null;
  permission_scope: string;
  data_digest: string;
  filter_hash: string;
};

export type FirstPurchaseProductRow = {
  product_id: string;
  role: 'sample' | 'finished';
  enrolled_count: number;
  mature_count: number;
  immature_count: number;
  finished_conversion_count: number;
  finished_conversion_ratio: number | null;
  empty_reason: 'EMPTY_MATURE_COHORT' | null;
};

export type FirstPurchaseFacts = {
  display_name: '首购商品路径 / N日正装转化';
  currency: 'CNY';
  amount_unit: 'minor';
  amount_precision: 'integer_fen';
  observation_days: 30 | 60 | 90;
  cohort_enrolled_count: number;
  cohort_mature_count: number;
  cohort_immature_count: number;
  products: FirstPurchaseProductRow[];
};

export type FirstPurchaseResult = {
  schema_version: 'analytics-first-purchase-path/v1';
  answer_mode: 'DETERMINISTIC_TOOL';
  query_id: 'first_purchase_product_path';
  query_version: 'first-purchase-path-query/v1';
  metric_id: 'first_purchase_product_n_day_finished';
  metric_version: 'first-purchase-path-metric/v1';
  data_version: 'synthetic-first-purchase-data/v1';
  hash_version: 'first-purchase-path-filter-hash/v1';
  contains_real_data: false;
  data_source: 'SYNTHETIC_SNAPSHOT';
  data_snapshot_ref: 'synthetic-first-purchase-v1';
  as_of: string;
  resolved_filters: FirstPurchaseResolvedFilters;
  filter_hash: string;
  status: 'OK' | 'REJECTED';
  reason_code: 'MISSING_PRODUCT_ROLE' | null;
  missing_product_ids: string[];
  facts: FirstPurchaseFacts | null;
  limitations: string[];
};

export type FirstPurchaseNativeReceipt = {
  schema_version: 'analytics-run-first-purchase-native-receipt/v1';
  run_id: string;
  request_id: string;
  call_id: string;
  attempt_id: string;
  step_id: string | null;
  disposition: 'EXECUTE' | 'REUSE_RESULT' | 'IN_FLIGHT';
  run_status: 'QUEUED' | 'RUNNING' | 'NEEDS_INPUT' | 'SUCCEEDED' | 'FAILED' | 'CANCELLING' | 'CANCELLED' | 'UNKNOWN';
  result: FirstPurchaseResult | null;
};

export function decodeFirstPurchaseRequest(value: unknown): FirstPurchaseQueryRequest | null;
export function decodeFirstPurchaseReceipt(value: unknown): FirstPurchaseNativeReceipt | null;
export function receiptMatchesRequest(
  receipt: FirstPurchaseNativeReceipt | null,
  request: FirstPurchaseQueryRequest | null,
  ids?: { requestId?: string; callId?: string },
): boolean;
export function firstPurchaseSaveBinding(runId: string): { readonly created_from_run_id: string; readonly source: 'first-purchase-run' } | null;
export function readBoundedJson(response: Response, limit: number): Promise<unknown>;
