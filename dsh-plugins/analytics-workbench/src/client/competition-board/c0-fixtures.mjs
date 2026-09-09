/** Verbatim C0 fixtures. Not a second field authority. Tests compare these to frozen JSON. */

export const C0_CONTRACT_HASH = '97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a';
export const C0_SCHEMA = 'competition-c0/v1';
export const FIXTURE_ROOT = 'docs/hackathon/parallel-competition-2026-09-09/contracts/fixtures';

export const BOARD_SUCCESS = Object.freeze(JSON.parse(`{
  "batch": {
    "batch_id": "batch_c0_1",
    "layout_mode": "ONE_BOARD_MULTI_BLOCK",
    "operations": [
      {
        "board_id": null,
        "endorsed_result_refs": [
          {
            "analysis_id": "analysis_c0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "completeness": "COMPLETE",
            "evidence_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "result_id": "result_c0_gsv_20260831",
            "run_id": "run_c0_gsv_20260831"
          }
        ],
        "idempotency_key": "board-create-a",
        "layout_mode": "ONE_BOARD_MULTI_BLOCK",
        "operation_id": "op_c0_board_a",
        "request_fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "title": "8月GSV诊断板"
      }
    ],
    "schema_version": "competition-board-batch/v1"
  },
  "board": {
    "affected_block_ids": ["card_c0_block_1", "card_c0_block_2"],
    "base_version": 3,
    "batch_id": "batch_c0_1",
    "block_ids": ["card_c0_block_1", "card_c0_block_2"],
    "board_id": "dash_c0_board_a",
    "data_mode": "SNAPSHOT",
    "data_namespace": "analytics-cockpit/v1",
    "existing_dashboard_schema": "analytics-cockpit/v1",
    "layout_mode": "ONE_BOARD_MULTI_BLOCK",
    "limitations": ["沿用 analytics-cockpit/v1 SNAPSHOT 读兼容；competition-board/v1 新板走隔离命名空间。"],
    "operation_id": "op_c0_board_a",
    "owner_id": "analyst.brand-a",
    "persisted": true,
    "preview": false,
    "schema_version": "competition-board/v1",
    "snapshot_compat": "READ_OLD_SNAPSHOT",
    "title": "8月GSV诊断板",
    "version": 4,
    "visibility": "PRIVATE"
  },
  "patch": {
    "attempt_id": "attempt_c0_style_1",
    "base_version": 4,
    "block_id": "card_c0_block_1",
    "board_id": "dash_c0_board_a",
    "cockpit_op": null,
    "display_op": {
      "card_id": "card_c0_block_1",
      "display_overrides": { "title": "渠道贡献（样式）" },
      "op": "display"
    },
    "filter_change": null,
    "idempotency_key": "patch-style-1",
    "intent": "STYLE_ONLY",
    "schema_version": "competition-board-patch/v1"
  }
}`));

export const BOARD_EMPTY = Object.freeze(JSON.parse(`{
  "affected_block_ids": [],
  "base_version": 1,
  "batch_id": null,
  "block_ids": [],
  "board_id": "dash_c0_board_a",
  "data_mode": "SNAPSHOT",
  "data_namespace": "analytics-cockpit/v1",
  "existing_dashboard_schema": "analytics-cockpit/v1",
  "layout_mode": "ONE_BOARD_MULTI_BLOCK",
  "limitations": ["无块的已存板仍是合法 BoardSpec，不等于失败。"],
  "operation_id": null,
  "owner_id": "analyst.brand-a",
  "persisted": true,
  "preview": false,
  "schema_version": "competition-board/v1",
  "snapshot_compat": "READ_OLD_SNAPSHOT",
  "title": "空板",
  "version": 1,
  "visibility": "PRIVATE"
}`));

export const BOARD_PARTIAL = Object.freeze(JSON.parse(`{
  "batch_id": "batch_c0_multi",
  "items": [
    {
      "board_id": "dash_c0_board_a",
      "error_code": null,
      "operation_id": "op_c0_board_a",
      "retryable": false,
      "status": "SUCCEEDED",
      "version": 1
    },
    {
      "board_id": null,
      "error_code": "ANALYSIS_UNAVAILABLE",
      "operation_id": "op_c0_board_b",
      "retryable": true,
      "status": "FAILED",
      "version": null
    }
  ],
  "schema_version": "competition-board-batch/v1",
  "status": "PARTIAL"
}`));

export const BOARD_CONFLICT = Object.freeze(JSON.parse(`{
  "error": {
    "code": "VERSION_CONFLICT",
    "doc_ref": "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T11",
    "http_status": 409,
    "maps_to": "backend.contracts.analytics.AnalyticsErrorDetail",
    "message": "base_version 与已保存版本不一致，未覆盖。",
    "param": "base_version",
    "recovery_url": null,
    "request_id": "req_c0_409_board",
    "retry_after": null,
    "retryable": false,
    "schema_version": "competition-error/v1"
  }
}`));

export const BOARD_FORBIDDEN = Object.freeze(JSON.parse(`{
  "error": {
    "code": "FORBIDDEN",
    "doc_ref": "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06",
    "http_status": 403,
    "maps_to": "backend.contracts.analytics.AnalyticsErrorDetail",
    "message": "当前身份无权读取或编辑该驾驶舱。",
    "param": "board_id",
    "recovery_url": null,
    "request_id": "req_c0_403_board",
    "retry_after": null,
    "retryable": false,
    "schema_version": "competition-error/v1"
  }
}`));

export const BOARD_PARAM_ERROR = Object.freeze(JSON.parse(`{
  "expected": { "code": "INVALID_REQUEST", "http_status": 422, "param": "visibility" },
  "payload": {
    "affected_block_ids": ["card_c0_block_1", "card_c0_block_2"],
    "base_version": 3,
    "batch_id": "batch_c0_1",
    "block_ids": ["card_c0_block_1", "card_c0_block_2"],
    "board_id": "dash_c0_board_a",
    "data_mode": "SNAPSHOT",
    "data_namespace": "analytics-cockpit/v1",
    "existing_dashboard_schema": "analytics-cockpit/v1",
    "layout_mode": "ONE_BOARD_MULTI_BLOCK",
    "limitations": ["沿用 analytics-cockpit/v1 SNAPSHOT 读兼容；competition-board/v1 新板走隔离命名空间。"],
    "operation_id": "op_c0_board_a",
    "owner_id": "analyst.brand-a",
    "persisted": true,
    "preview": false,
    "schema_version": "competition-board/v1",
    "snapshot_compat": "READ_OLD_SNAPSHOT",
    "title": "8月GSV诊断板",
    "version": 4,
    "visibility": "PUBLIC"
  }
}`));

export const RESULT_SUCCESS = Object.freeze(JSON.parse(`{
  "analysis_id": "analysis_c0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "completeness": "COMPLETE",
  "contains_real_data": false,
  "data_mode": "SNAPSHOT",
  "empty_reason": null,
  "evidence_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "existing_result_schema": "analytics-channel-followup/v1",
  "facts_schema_ref": "backend.contracts.analytics_query.ChannelFollowupResult",
  "limitations": [
    "facts_schema_ref 指向已有 ChannelFollowupResult，不另造渠道二单事实。",
    "C0 不把 B0 STUB 或未核清口径写成 SUPPORTED。"
  ],
  "metric_id": "channel_first_observed_n_day_repeat",
  "metric_version": "channel-followup-metric/v1",
  "page": {
    "checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "complete": true,
    "limit": 50,
    "offset": 0,
    "total": 2
  },
  "primary_result_ref": "result_c0_gsv_20260831",
  "query_id": "channel_first_observed_followup",
  "query_version": "channel-followup-query/v1",
  "resolved_condition": {
    "actor_id": "analyst.brand-a",
    "as_of": "2026-08-31T16:00:00.000000+00:00",
    "comparison_mode": "YOY_SAME_PERIOD",
    "comparison_period": { "end_bound": "INCLUSIVE_CALENDAR_DAY", "end_date": "2025-08-31", "start_date": "2025-08-01" },
    "current_period": { "end_bound": "INCLUSIVE_CALENDAR_DAY", "end_date": "2026-08-31", "start_date": "2026-08-01" },
    "cutoff": "2026-07-31",
    "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
    "data_snapshot_ref": "synthetic-c0-demo-v1",
    "data_version": "synthetic-c0-demo-data/v1",
    "event_time": "2026-08-31T16:00:00.000000+00:00",
    "feature_as_of": "2026-08-31T16:00:00.000000+00:00",
    "filter_hash": "fa03728a51098b85b12c29eed66cabdfe2ef6a55ab2af46d578b3f0a3e999bb3",
    "history_scope": { "channel_ids": [], "kind": "ALL", "product_ids": [] },
    "ignored_filters": [],
    "leap_day_alignment": "CLAMP_TO_MONTH_END",
    "limitations": [
      "facts_schema_ref 指向已有 ChannelFollowupResult，不另造渠道二单事实。",
      "C0 不把 B0 STUB 或未核清口径写成 SUPPORTED。"
    ],
    "metric_type": "GSV",
    "metrics_contract_id": "competition-metrics/v1",
    "permission_scope": "scope-brand-a",
    "published_at": "2026-08-31T16:00:00.000000+00:00",
    "rule_version": "competition-condition-rule/v1",
    "sales_scope": { "channel_ids": [], "kind": "ALL", "product_ids": [] },
    "sample_channel_ids": ["sample-channel-unverified-a", "sample-channel-unverified-b"],
    "sample_channel_set_status": "UNKNOWN",
    "sample_history_recomputed": false,
    "sample_mode": "EXCLUDE_CURRENT_SALES_ONLY",
    "schema_version": "competition-condition/v1",
    "source_tense": "PUBLISHED_SNAPSHOT",
    "timezone": "Asia/Shanghai",
    "unknown_flags": [
      { "code": "SAMPLE_CHANNEL_SET", "note": "派样渠道集合未在 C0 冻结；执行必须回显实际 sample_channel_ids。", "status": "UNKNOWN" },
      { "code": "MEMBER_HISTORY", "note": "无核验历史会员状态，不得把 UNKNOWN 当非会员。", "status": "UNKNOWN" },
      { "code": "F_ORDER_GRAIN_OLD_CRM", "note": "旧 CRM RFM F 粒度未核清；W4 仅声明 (synthetic_user_id, order_id)。", "status": "UNKNOWN" },
      { "code": "NEW_OLD_CUSTOM_MONTH_CUTOFF", "note": "audience_summary 自定义日期仍用月初 cutoff；C0 要求 start-1。", "status": "UNKNOWN" },
      { "code": "VALID_ORDER_RULE_OLD_CRM", "note": "旧有效订单规则以 FilterBuilder.valid_order 为准，不在 C0 另造阈值。", "status": "UNKNOWN" }
    ],
    "warehouse_as_of": "2026-08-31T16:00:00.000000+00:00"
  },
  "result_id": "result_c0_gsv_20260831",
  "row_count": 2,
  "run_id": "run_c0_gsv_20260831",
  "schema_version": "competition-result/v1"
}`));

export const RESULT_EMPTY = Object.freeze(JSON.parse(`{
  "analysis_id": null,
  "completeness": "EMPTY",
  "contains_real_data": false,
  "data_mode": "SNAPSHOT",
  "empty_reason": "NO_CURRENT_MONTH_DATA",
  "evidence_digest": null,
  "existing_result_schema": "none",
  "facts_schema_ref": "competition-result/v1#empty",
  "limitations": [
    "2026-09-01 T+1 时 9 月尚无可用数据：EMPTY，不比较未来完整月。",
    "C0 不把 B0 STUB 或未核清口径写成 SUPPORTED。"
  ],
  "metric_id": null,
  "metric_version": null,
  "page": null,
  "primary_result_ref": null,
  "query_id": "competition_gsv_mtd",
  "query_version": "competition-metrics/v1",
  "resolved_condition": {
    "actor_id": "analyst.brand-a",
    "as_of": "2026-08-31T16:00:00.000000+00:00",
    "comparison_mode": "YOY_SAME_PERIOD",
    "comparison_period": { "end_bound": "INCLUSIVE_CALENDAR_DAY", "end_date": "2025-08-31", "start_date": "2025-08-01" },
    "current_period": { "end_bound": "INCLUSIVE_CALENDAR_DAY", "end_date": "2026-09-01", "start_date": "2026-09-01" },
    "cutoff": "2026-08-31",
    "data_cutoff_policy": "T_PLUS_1_YESTERDAY",
    "data_snapshot_ref": "synthetic-c0-demo-v1",
    "data_version": "synthetic-c0-demo-data/v1",
    "event_time": "2026-08-31T16:00:00.000000+00:00",
    "feature_as_of": "2026-08-31T16:00:00.000000+00:00",
    "filter_hash": "f78739b000599e5e183a868646ee5a81a2c988e39cbb444e8abd4ac3cd20ba81",
    "history_scope": { "channel_ids": [], "kind": "ALL", "product_ids": [] },
    "ignored_filters": [],
    "leap_day_alignment": "CLAMP_TO_MONTH_END",
    "limitations": [
      "2026-09-01 T+1 时 9 月尚无可用数据：EMPTY，不比较未来完整月。",
      "C0 不把 B0 STUB 或未核清口径写成 SUPPORTED。"
    ],
    "metric_type": "GSV",
    "metrics_contract_id": "competition-metrics/v1",
    "permission_scope": "scope-brand-a",
    "published_at": "2026-08-31T16:00:00.000000+00:00",
    "rule_version": "competition-condition-rule/v1",
    "sales_scope": { "channel_ids": [], "kind": "ALL", "product_ids": [] },
    "sample_channel_ids": null,
    "sample_channel_set_status": "UNKNOWN",
    "sample_history_recomputed": false,
    "sample_mode": "INCLUDE",
    "schema_version": "competition-condition/v1",
    "source_tense": "PUBLISHED_SNAPSHOT",
    "timezone": "Asia/Shanghai",
    "unknown_flags": [
      { "code": "SAMPLE_CHANNEL_SET", "note": "派样渠道集合未在 C0 冻结；执行必须回显实际 sample_channel_ids。", "status": "UNKNOWN" },
      { "code": "MEMBER_HISTORY", "note": "无核验历史会员状态，不得把 UNKNOWN 当非会员。", "status": "UNKNOWN" },
      { "code": "F_ORDER_GRAIN_OLD_CRM", "note": "旧 CRM RFM F 粒度未核清；W4 仅声明 (synthetic_user_id, order_id)。", "status": "UNKNOWN" },
      { "code": "NEW_OLD_CUSTOM_MONTH_CUTOFF", "note": "audience_summary 自定义日期仍用月初 cutoff；C0 要求 start-1。", "status": "UNKNOWN" },
      { "code": "VALID_ORDER_RULE_OLD_CRM", "note": "旧有效订单规则以 FilterBuilder.valid_order 为准，不在 C0 另造阈值。", "status": "UNKNOWN" }
    ],
    "warehouse_as_of": "2026-08-31T16:00:00.000000+00:00"
  },
  "result_id": "result_c0_empty_20260901",
  "row_count": 0,
  "run_id": "run_c0_empty_20260901",
  "schema_version": "competition-result/v1"
}`));

export const RESULT_FORBIDDEN = Object.freeze(JSON.parse(`{
  "error": {
    "code": "FORBIDDEN",
    "doc_ref": "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06",
    "http_status": 403,
    "maps_to": "backend.contracts.analytics.AnalyticsErrorDetail",
    "message": "当前身份无权读取该结果引用。",
    "param": "result_id",
    "recovery_url": null,
    "request_id": "req_c0_403_result",
    "retry_after": null,
    "retryable": false,
    "schema_version": "competition-error/v1"
  }
}`));

export const RESULT_PARAM_ERROR = Object.freeze(JSON.parse(`{
  "expected": { "code": "INVALID_REQUEST", "http_status": 422, "param": "schema_version" },
  "payload": { "completeness": "COMPLETE", "schema_version": "analytics-run-b0/v1" }
}`));

export const DEFAULT_PRINCIPAL = Object.freeze({
  actor_id: 'analyst.brand-a',
  permission_scope: 'scope-brand-a',
});

export const BOARD_LAYOUT_MODE_DEFAULT = Object.freeze({
  key: 'board_layout_mode',
  pending_confirmation: true,
  value: 'ONE_BOARD_MULTI_BLOCK',
  note: '待确认。推荐一组认可分析一板多块；BATCH_MULTI_BOARD 为可选显式模式。',
});

export const REGISTERED_PLUGINS = Object.freeze(['TABLE', 'BAR', 'LINE', 'METRIC', 'EVIDENCE']);
