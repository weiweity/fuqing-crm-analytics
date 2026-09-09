/** Verbatim C0 audience/action fixtures. Not a second field authority. */

export const AUDIENCE_SUCCESS = Object.freeze(JSON.parse(`{
  "candidates": {
    "auto_send": false,
    "candidate_set_id": "cand_c0_10",
    "cohort_id": "cohort_c0_ly_f_unknown",
    "combine": "AND",
    "customer_keys": ["cust_c0_1", "cust_c0_2"],
    "explanations": [
      { "customer_key": "cust_c0_1", "reasons": ["ORIGIN_CHANNEL_ABSENT"] },
      { "customer_key": "cust_c0_2", "reasons": ["ORIGIN_CHANNEL_ABSENT"] }
    ],
    "limitations": ["合成 customer_key，不导出真实名单。"],
    "permission_scope": "scope-brand-a",
    "schema_version": "competition-audience/v1",
    "source_result_ref": "result_c0_gsv_20260831",
    "unique_count": 2
  },
  "cohort": {
    "as_of": "2026-08-31T16:00:00.000000+00:00",
    "cohort_id": "cohort_c0_ly_f_unknown",
    "enrollment_rule_version": "competition-cohort-rule/v1",
    "enrollment_window": { "end_bound": "INCLUSIVE_CALENDAR_DAY", "end_date": "2025-12-31", "start_date": "2025-01-01" },
    "existing_family": "none",
    "limitations": [
      "去年 F≥4 固定入组未核清旧 CRM F 粒度，C0 禁止带 f_threshold。",
      "handoff-audience 不得冒充本 cohort。"
    ],
    "member_history_status": "UNKNOWN",
    "observation_window": { "end_bound": "INCLUSIVE_CALENDAR_DAY", "end_date": "2026-08-31", "start_date": "2026-08-01" },
    "permission_scope": "scope-brand-a",
    "published_at": "2026-08-31T16:00:00.000000+00:00",
    "rules": [
      {
        "channel_ids": ["channel-unverified-origin"],
        "f_grain_status": "UNKNOWN",
        "f_threshold": null,
        "kind": "NON_REPURCHASE",
        "member_mark": "UNKNOWN",
        "non_repurchase": "ORIGIN_CHANNEL_ABSENT",
        "product_ids": [],
        "rule_id": "rule_origin_channel"
      }
    ],
    "schema_version": "competition-audience/v1",
    "source_tense": "PUBLISHED_SNAPSHOT"
  },
  "draft": {
    "auto_send": false,
    "budget_cap_minor": 100000,
    "candidate_set_id": "cand_c0_10",
    "channel": "channel-unverified-origin",
    "control_design": "holdout 待确认",
    "copy_only_change": false,
    "currency": "CNY",
    "draft_id": "draft_c0_1",
    "existing_mission_export": "not-mission-draft-export",
    "expired_reason": null,
    "limitations": ["GSV 下降不等于投放回报低；缺成本时只给试验优先级。"],
    "owner_id": "analyst.brand-a",
    "product_id": null,
    "review_by": "2026-09-15",
    "reviewer_id": "reviewer.ops",
    "schema_version": "competition-action/v1",
    "source_result_ref": "result_c0_gsv_20260831",
    "status": "DRAFT",
    "stop_condition": "观察窗结束或人工停止",
    "unknowns": ["MEMBER_HISTORY", "SAMPLE_CHANNEL_SET", "incremental_roi"],
    "version": 1
  }
}`));

export const AUDIENCE_EMPTY = Object.freeze(JSON.parse(`{
  "auto_send": false,
  "candidate_set_id": "cand_c0_zero",
  "cohort_id": "cohort_c0_ly_f_unknown",
  "combine": "AND",
  "customer_keys": [],
  "explanations": [],
  "limitations": ["零候选不得伪造建议名单。"],
  "permission_scope": "scope-brand-a",
  "schema_version": "competition-audience/v1",
  "source_result_ref": "result_c0_gsv_20260831",
  "unique_count": 0
}`));

export const AUDIENCE_PARTIAL = Object.freeze(JSON.parse(`{
  "accepted": {
    "auto_send": false,
    "candidate_set_id": "cand_c0_10",
    "cohort_id": "cohort_c0_ly_f_unknown",
    "combine": "AND",
    "customer_keys": ["cust_c0_1", "cust_c0_2"],
    "explanations": [
      { "customer_key": "cust_c0_1", "reasons": ["ORIGIN_CHANNEL_ABSENT"] },
      { "customer_key": "cust_c0_2", "reasons": ["ORIGIN_CHANNEL_ABSENT"] }
    ],
    "limitations": ["合成 customer_key，不导出真实名单。"],
    "permission_scope": "scope-brand-a",
    "schema_version": "competition-audience/v1",
    "source_result_ref": "result_c0_gsv_20260831",
    "unique_count": 2
  },
  "combine": "OR",
  "note": "一条规则成功、一条规则因 F 粒度 UNKNOWN 被拒绝，不得把失败规则人数加进成功集合。",
  "rejected": {
    "error": {
      "code": "UNSUPPORTED_FILTER",
      "doc_ref": "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T05",
      "http_status": 422,
      "maps_to": "backend.contracts.analytics.AnalyticsErrorDetail",
      "message": "F 粒度 UNKNOWN，拒绝应用 f_threshold。",
      "param": "f_threshold",
      "recovery_url": null,
      "request_id": "req_c0_partial_audience",
      "retry_after": null,
      "retryable": false,
      "schema_version": "competition-error/v1"
    },
    "rule_id": "rule_f_ge_4"
  },
  "status": "PARTIAL"
}`));

export const AUDIENCE_CONFLICT = Object.freeze(JSON.parse(`{
  "error": {
    "code": "VERSION_CONFLICT",
    "doc_ref": "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T12",
    "http_status": 409,
    "maps_to": "backend.contracts.analytics.AnalyticsErrorDetail",
    "message": "草稿 base_version 冲突，未覆盖。",
    "param": "version",
    "recovery_url": null,
    "request_id": "req_c0_409_draft",
    "retry_after": null,
    "retryable": false,
    "schema_version": "competition-error/v1"
  }
}`));

export const AUDIENCE_FORBIDDEN = Object.freeze(JSON.parse(`{
  "error": {
    "code": "FORBIDDEN",
    "doc_ref": "docs/hackathon/COMPETITION-TEST-PLAN-2026-09-09.md#T06",
    "http_status": 403,
    "maps_to": "backend.contracts.analytics.AnalyticsErrorDetail",
    "message": "当前身份无权预览该候选明细。",
    "param": "customer_key",
    "recovery_url": null,
    "request_id": "req_c0_403_audience",
    "retry_after": null,
    "retryable": false,
    "schema_version": "competition-error/v1"
  }
}`));

export const AUDIENCE_PARAM_ERROR = Object.freeze(JSON.parse(`{
  "expected": { "code": "INVALID_REQUEST", "http_status": 422, "param": "unique_count" },
  "payload": {
    "auto_send": false,
    "candidate_set_id": "cand_c0_10",
    "cohort_id": "cohort_c0_ly_f_unknown",
    "combine": "AND",
    "customer_keys": ["cust_c0_1", "cust_c0_2"],
    "explanations": [
      { "customer_key": "cust_c0_1", "reasons": ["ORIGIN_CHANNEL_ABSENT"] },
      { "customer_key": "cust_c0_2", "reasons": ["ORIGIN_CHANNEL_ABSENT"] }
    ],
    "limitations": ["合成 customer_key，不导出真实名单。"],
    "permission_scope": "scope-brand-a",
    "schema_version": "competition-audience/v1",
    "source_result_ref": "result_c0_gsv_20260831",
    "unique_count": 99
  }
}`));

export const NON_REPURCHASE = Object.freeze(['ORIGIN_CHANNEL_ABSENT', 'ORIGIN_PRODUCT_ABSENT', 'STOREWIDE_ABSENT']);
