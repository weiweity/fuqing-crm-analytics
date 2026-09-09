/** Finite first-purchase native-query wire script. Mock never fabricates compute results. */
import { FIRST_PURCHASE_TOOL_NAME } from '../../dsh-plugins/analytics-workbench/src/first-purchase-query-model.mjs';

export function firstPurchaseRequest(observationDays = 30) {
  return {
    schema_version: 'analytics-first-purchase-path/v1',
    query_id: 'first_purchase_product_path',
    query_version: 'first-purchase-path-query/v1',
    metric_id: 'first_purchase_product_n_day_finished',
    metric_version: 'first-purchase-path-metric/v1',
    cohort_window: { kind: 'FIXED', start_date: '2026-06-01', end_date: '2026-09-01' },
    observation_days: observationDays,
    data_snapshot_ref: 'synthetic-first-purchase-v1',
    timezone: 'Asia/Shanghai',
    channel_ids: [],
    cohort_ref: null,
    product_ids: [],
    exclude_low_price: false,
    comparison: null,
  };
}

export function firstPurchaseMockScript() {
  const wrap = '合成首购查询完成：数字来自后端 JSON 计算，不是模型编造，不能当作真实经营结论。';
  const fast = Object.freeze({ chunkSize: 32, chunkDelayMs: 0 });
  return [
    { sequence: ['tool_call_success'], toolName: FIRST_PURCHASE_TOOL_NAME,
      toolArguments: JSON.stringify(firstPurchaseRequest(30)), successText: wrap, ...fast },
    { sequence: ['success'], successText: wrap, ...fast },
  ];
}
