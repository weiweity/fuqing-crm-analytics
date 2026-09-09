/** Generated competition C0 contract; do not edit. Not an HTTP API. OpenAPI SHA-256: 6d6558e894441d707417003ad9f92e4fc486c1c21c1b92a6d9bc1a24f5c5967f */
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AnalyticsCockpitAddOp */
        AnalyticsCockpitAddOp: {
            analysis_ref: components["schemas"]["AnalyticsCockpitAnalysisRef"];
            /** @default null */
            display_overrides: components["schemas"]["AnalyticsCockpitDisplayOverrides"] | null;
            /** @default null */
            layout: components["schemas"]["AnalyticsCockpitLayout"] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "add";
            /** @default null */
            plugin_ref: components["schemas"]["AnalyticsCockpitTablePlugin"] | null;
        };
        /** AnalyticsCockpitAnalysisRef */
        AnalyticsCockpitAnalysisRef: {
            /** Analysis Id */
            analysis_id: string;
            /** Version */
            version: number;
        };
        /** AnalyticsCockpitCopyOp */
        AnalyticsCockpitCopyOp: {
            /** Card Id */
            card_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "copy";
        };
        /** AnalyticsCockpitDisplayOverrides */
        AnalyticsCockpitDisplayOverrides: {
            /** Title */
            title: string;
        };
        /** AnalyticsCockpitLayout */
        AnalyticsCockpitLayout: {
            /** H */
            h: number;
            /** W */
            w: number;
            /** X */
            x: number;
            /** Y */
            y: number;
        };
        /** AnalyticsCockpitLayoutOp */
        AnalyticsCockpitLayoutOp: {
            /** Card Id */
            card_id: string;
            layout: components["schemas"]["AnalyticsCockpitLayout"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "layout";
        };
        /** AnalyticsCockpitRemoveOp */
        AnalyticsCockpitRemoveOp: {
            /** Card Id */
            card_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "remove";
        };
        /** AnalyticsCockpitTablePlugin */
        AnalyticsCockpitTablePlugin: {
            /**
             * Type
             * @default TABLE
             * @constant
             */
            type: "TABLE";
            /**
             * Version
             * @default analytics-visual-table/v1
             * @constant
             */
            version: "analytics-visual-table/v1";
        };
        /** AnalyticsCockpitUndoOp */
        AnalyticsCockpitUndoOp: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "undo";
            /** Restore From Version */
            restore_from_version: number;
            /**
             * Scope
             * @constant
             */
            scope: "board";
        };
        /**
         * BoardLayoutMode
         * @enum {string}
         */
        BoardLayoutMode: "ONE_BOARD_MULTI_BLOCK" | "BATCH_MULTI_BOARD";
        /** BoardOperation */
        BoardOperation: {
            /**
             * Board Id
             * @default null
             */
            board_id: string | null;
            /** Endorsed Result Refs */
            endorsed_result_refs: components["schemas"]["EndorsedResultRef"][];
            /** Idempotency Key */
            idempotency_key: string;
            layout_mode: components["schemas"]["BoardLayoutMode"];
            /** Operation Id */
            operation_id: string;
            /** Request Fingerprint */
            request_fingerprint: string;
            /** Title */
            title: string;
        };
        /** BoardOpReceipt */
        BoardOpReceipt: {
            /** Board Id */
            board_id: string | null;
            /**
             * Error Code
             * @default null
             */
            error_code: string | null;
            /** Operation Id */
            operation_id: string;
            /**
             * Retryable
             * @default false
             */
            retryable: boolean;
            /**
             * Status
             * @enum {string}
             */
            status: "SUCCEEDED" | "FAILED" | "CONFLICT";
            /**
             * Version
             * @default null
             */
            version: number | null;
        };
        /** CandidateExplanation */
        CandidateExplanation: {
            /** Customer Key */
            customer_key: string;
            /** Reasons */
            reasons: string[];
        };
        /** CohortRule */
        CohortRule: {
            /** Channel Ids */
            channel_ids?: string[];
            /**
             * F Grain Status
             * @enum {string}
             */
            f_grain_status: "UNKNOWN" | "W4_ORDER_GRAIN";
            /**
             * F Threshold
             * @default null
             */
            f_threshold: number | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "ENROLLMENT_SNAPSHOT" | "NON_REPURCHASE" | "MEMBER_CROSS";
            member_mark: components["schemas"]["MemberMark"];
            /** @default null */
            non_repurchase: components["schemas"]["NonRepurchaseKind"] | null;
            /** Product Ids */
            product_ids?: string[];
            /** Rule Id */
            rule_id: string;
        };
        /**
         * CombineOp
         * @enum {string}
         */
        CombineOp: "AND" | "OR";
        /**
         * ComparisonMode
         * @enum {string}
         */
        ComparisonMode: "YOY_SAME_PERIOD" | "LAST_WEEK_SAME_WEEKDAY" | "CUSTOM_DUAL_WINDOW";
        /** CompetitionActionDraft */
        CompetitionActionDraft: {
            /**
             * Auto Send
             * @default false
             * @constant
             */
            auto_send: false;
            /**
             * Budget Cap Minor
             * @default null
             */
            budget_cap_minor: number | null;
            /** Candidate Set Id */
            candidate_set_id: string;
            /**
             * Channel
             * @default null
             */
            channel: string | null;
            /**
             * Control Design
             * @default null
             */
            control_design: string | null;
            /**
             * Copy Only Change
             * @default false
             */
            copy_only_change: boolean;
            /**
             * Currency
             * @default CNY
             * @constant
             */
            currency: "CNY";
            /** Draft Id */
            draft_id: string;
            /**
             * Existing Mission Export
             * @default not-mission-draft-export
             * @constant
             */
            existing_mission_export: "not-mission-draft-export";
            /**
             * Expired Reason
             * @default null
             */
            expired_reason: ("RULE_CHANGED" | "SOURCE_CHANGED") | null;
            /** Limitations */
            limitations: string[];
            /** Owner Id */
            owner_id: string;
            /**
             * Product Id
             * @default null
             */
            product_id: string | null;
            /**
             * Review By
             * @default null
             */
            review_by: string | null;
            /**
             * Reviewer Id
             * @default null
             */
            reviewer_id: string | null;
            /**
             * Schema Version
             * @default competition-action/v1
             * @constant
             */
            schema_version: "competition-action/v1";
            /** Source Result Ref */
            source_result_ref: string;
            status: components["schemas"]["DraftStatus"];
            /**
             * Stop Condition
             * @default null
             */
            stop_condition: string | null;
            /** Unknowns */
            unknowns: string[];
            /** Version */
            version: number;
        };
        /** CompetitionBoardBatchReceipt */
        CompetitionBoardBatchReceipt: {
            /** Batch Id */
            batch_id: string;
            /** Items */
            items: components["schemas"]["BoardOpReceipt"][];
            /**
             * Schema Version
             * @default competition-board-batch/v1
             * @constant
             */
            schema_version: "competition-board-batch/v1";
            /**
             * Status
             * @enum {string}
             */
            status: "SUCCEEDED" | "PARTIAL" | "FAILED";
        };
        /** CompetitionBoardBatchRequest */
        CompetitionBoardBatchRequest: {
            /** Batch Id */
            batch_id: string;
            layout_mode: components["schemas"]["BoardLayoutMode"];
            /** Operations */
            operations: components["schemas"]["BoardOperation"][];
            /**
             * Schema Version
             * @default competition-board-batch/v1
             * @constant
             */
            schema_version: "competition-board-batch/v1";
        };
        /** CompetitionBoardSpec */
        CompetitionBoardSpec: {
            /** Affected Block Ids */
            affected_block_ids: string[];
            /** Base Version */
            base_version: number;
            /**
             * Batch Id
             * @default null
             */
            batch_id: string | null;
            /** Block Ids */
            block_ids: string[];
            /** Board Id */
            board_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "SNAPSHOT";
            /**
             * Data Namespace
             * @enum {string}
             */
            data_namespace: "analytics-cockpit/v1" | "competition-board/v1";
            /**
             * Existing Dashboard Schema
             * @constant
             */
            existing_dashboard_schema: "analytics-cockpit/v1";
            layout_mode: components["schemas"]["BoardLayoutMode"];
            /** Limitations */
            limitations: string[];
            /**
             * Operation Id
             * @default null
             */
            operation_id: string | null;
            /** Owner Id */
            owner_id: string;
            /** Persisted */
            persisted: boolean;
            /** Preview */
            preview: boolean;
            /**
             * Schema Version
             * @default competition-board/v1
             * @constant
             */
            schema_version: "competition-board/v1";
            snapshot_compat: components["schemas"]["SnapshotCompat"];
            /** Title */
            title: string;
            /** Version */
            version: number;
            /**
             * Visibility
             * @constant
             */
            visibility: "PRIVATE";
        };
        /** CompetitionCandidateSet */
        CompetitionCandidateSet: {
            /**
             * Auto Send
             * @default false
             * @constant
             */
            auto_send: false;
            /** Candidate Set Id */
            candidate_set_id: string;
            /** Cohort Id */
            cohort_id: string;
            combine: components["schemas"]["CombineOp"];
            /** Customer Keys */
            customer_keys: string[];
            /** Explanations */
            explanations: components["schemas"]["CandidateExplanation"][];
            /** Limitations */
            limitations: string[];
            /** Permission Scope */
            permission_scope: string;
            /**
             * Schema Version
             * @default competition-audience/v1
             * @constant
             */
            schema_version: "competition-audience/v1";
            /** Source Result Ref */
            source_result_ref: string;
            /** Unique Count */
            unique_count: number;
        };
        /** CompetitionCapability */
        CompetitionCapability: {
            /**
             * Actor Filtered
             * @default true
             * @constant
             */
            actor_filtered: true;
            /**
             * Backend Recheck
             * @default true
             * @constant
             */
            backend_recheck: true;
            /** Capability Id */
            capability_id: string;
            /**
             * Concept
             * @enum {string}
             */
            concept: "Condition" | "ResultRef" | "BoardSpec" | "Patch" | "Audience" | "Action" | "Error" | "Capabilities" | "FrontendPort";
            /** Existing Types */
            existing_types: string[];
            /**
             * Http Mapping
             * @default null
             */
            http_mapping: string | null;
            /** Notes */
            notes: string;
            /** Required Capabilities */
            required_capabilities: string[];
            /**
             * Schema Version
             * @default competition-capabilities/v1
             * @constant
             */
            schema_version: "competition-capabilities/v1";
            /**
             * Service Mapping
             * @default null
             */
            service_mapping: string | null;
            support_status: components["schemas"]["SupportStatus"];
            /** Title */
            title: string;
            /** Unknown Flags */
            unknown_flags?: string[];
            /**
             * W4 Mapping
             * @default null
             */
            w4_mapping: string | null;
        };
        /** CompetitionCohortSpec */
        CompetitionCohortSpec: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Cohort Id */
            cohort_id: string;
            /** Enrollment Rule Version */
            enrollment_rule_version: string;
            enrollment_window: components["schemas"]["InclusiveDateRange"];
            /**
             * Existing Family
             * @enum {string}
             */
            existing_family: "analytics-handoff-audience/v1" | "none";
            /** Limitations */
            limitations: string[];
            /**
             * Member History Status
             * @constant
             */
            member_history_status: "UNKNOWN";
            observation_window: components["schemas"]["InclusiveDateRange"];
            /** Permission Scope */
            permission_scope: string;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Rules */
            rules: components["schemas"]["CohortRule"][];
            /**
             * Schema Version
             * @default competition-audience/v1
             * @constant
             */
            schema_version: "competition-audience/v1";
            source_tense: components["schemas"]["SourceTense"];
        };
        /** CompetitionConceptMap */
        CompetitionConceptMap: {
            /** C0 Type */
            c0_type: string;
            /** Concept */
            concept: string;
            /** Existing Types */
            existing_types: string[];
            /** Notes */
            notes: string;
        };
        /**
         * CompetitionCondition
         * @description C0 Condition. Callers must send every execution-relevant field explicitly.
         */
        CompetitionCondition: {
            /**
             * As Of
             * @default null
             */
            as_of: string | null;
            comparison_mode: components["schemas"]["ComparisonMode"];
            comparison_period: components["schemas"]["InclusiveDateRange"];
            current_period: components["schemas"]["InclusiveDateRange"];
            /**
             * Data Cutoff Policy
             * @constant
             */
            data_cutoff_policy: "T_PLUS_1_YESTERDAY";
            /**
             * Data Snapshot Ref
             * @default null
             */
            data_snapshot_ref: string | null;
            history_scope: components["schemas"]["FilterScope"];
            /**
             * Leap Day Alignment
             * @constant
             */
            leap_day_alignment: "CLAMP_TO_MONTH_END";
            /**
             * Metric Type
             * @constant
             */
            metric_type: "GSV";
            /**
             * Metrics Contract Id
             * @default competition-metrics/v1
             * @constant
             */
            metrics_contract_id: "competition-metrics/v1";
            /**
             * Rule Version
             * @default null
             */
            rule_version: string | null;
            sales_scope: components["schemas"]["FilterScope"];
            /**
             * Sample Channel Ids
             * @default null
             */
            sample_channel_ids: string[] | null;
            sample_mode: components["schemas"]["SampleMode"];
            /**
             * Schema Version
             * @default competition-condition/v1
             * @constant
             */
            schema_version: "competition-condition/v1";
            /**
             * Timezone
             * @constant
             */
            timezone: "Asia/Shanghai";
        };
        /** CompetitionDisplayOp */
        CompetitionDisplayOp: {
            /** Card Id */
            card_id: string;
            display_overrides: components["schemas"]["AnalyticsCockpitDisplayOverrides"];
            /**
             * Op
             * @constant
             */
            op: "display";
        };
        /** CompetitionErrorDetail */
        CompetitionErrorDetail: {
            /** Code */
            code: string;
            /**
             * Doc Ref
             * @default null
             */
            doc_ref: string | null;
            /** Http Status */
            http_status: number;
            /**
             * Maps To
             * @constant
             */
            maps_to: "backend.contracts.analytics.AnalyticsErrorDetail";
            /** Message */
            message: string;
            /**
             * Param
             * @default null
             */
            param: string | null;
            /**
             * Recovery Url
             * @default null
             */
            recovery_url: string | null;
            /** Request Id */
            request_id: string;
            /**
             * Retry After
             * @default null
             */
            retry_after: number | null;
            /** Retryable */
            retryable: boolean;
            /**
             * Schema Version
             * @default competition-error/v1
             * @constant
             */
            schema_version: "competition-error/v1";
        };
        /** CompetitionErrorResponse */
        CompetitionErrorResponse: {
            error: components["schemas"]["CompetitionErrorDetail"];
        };
        /** CompetitionFilterChangeOp */
        CompetitionFilterChangeOp: {
            /** Card Id */
            card_id: string;
            /** Local Filters */
            local_filters: {
                [key: string]: string[];
            };
            /**
             * Op
             * @constant
             */
            op: "filter_change";
        };
        /** CompetitionFrontendPort */
        CompetitionFrontendPort: {
            /** Name */
            name: string;
            /** Notes */
            notes: string;
            /**
             * Owner
             * @enum {string}
             */
            owner: "A4" | "A5" | "A6" | "A7" | "A8";
            /** Port Id */
            port_id: string;
            /**
             * Schema Version
             * @default competition-frontend-ports/v1
             * @constant
             */
            schema_version: "competition-frontend-ports/v1";
            /** Signature */
            signature: string;
            /**
             * Support Status
             * @default NOT_CONNECTED
             * @constant
             */
            support_status: "NOT_CONNECTED";
        };
        /** CompetitionPatchRequest */
        CompetitionPatchRequest: {
            /** Attempt Id */
            attempt_id: string;
            /** Base Version */
            base_version: number;
            /**
             * Block Id
             * @default null
             */
            block_id: string | null;
            /** Board Id */
            board_id: string;
            /**
             * Cockpit Op
             * @default null
             */
            cockpit_op: (components["schemas"]["AnalyticsCockpitAddOp"] | components["schemas"]["AnalyticsCockpitCopyOp"] | components["schemas"]["AnalyticsCockpitRemoveOp"] | components["schemas"]["AnalyticsCockpitLayoutOp"] | components["schemas"]["AnalyticsCockpitUndoOp"]) | null;
            /** @default null */
            display_op: components["schemas"]["CompetitionDisplayOp"] | null;
            /** @default null */
            filter_change: components["schemas"]["CompetitionFilterChangeOp"] | null;
            /** Idempotency Key */
            idempotency_key: string;
            intent: components["schemas"]["PatchIntent"];
            /**
             * Schema Version
             * @default competition-board-patch/v1
             * @constant
             */
            schema_version: "competition-board-patch/v1";
        };
        /** CompetitionResolvedCondition */
        CompetitionResolvedCondition: {
            /** Actor Id */
            actor_id: string;
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            comparison_mode: components["schemas"]["ComparisonMode"];
            comparison_period: components["schemas"]["InclusiveDateRange"];
            current_period: components["schemas"]["InclusiveDateRange"];
            /**
             * Cutoff
             * Format: date
             */
            cutoff: string;
            /**
             * Data Cutoff Policy
             * @constant
             */
            data_cutoff_policy: "T_PLUS_1_YESTERDAY";
            /** Data Snapshot Ref */
            data_snapshot_ref: string;
            /** Data Version */
            data_version: string;
            /**
             * Event Time
             * Format: date-time
             */
            event_time: string;
            /**
             * Feature As Of
             * @default null
             */
            feature_as_of: string | null;
            /** Filter Hash */
            filter_hash: string;
            history_scope: components["schemas"]["FilterScope"];
            /** Ignored Filters */
            ignored_filters?: string[];
            /**
             * Leap Day Alignment
             * @constant
             */
            leap_day_alignment: "CLAMP_TO_MONTH_END";
            /** Limitations */
            limitations: string[];
            /**
             * Metric Type
             * @constant
             */
            metric_type: "GSV";
            /**
             * Metrics Contract Id
             * @default competition-metrics/v1
             * @constant
             */
            metrics_contract_id: "competition-metrics/v1";
            /** Permission Scope */
            permission_scope: string;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Rule Version */
            rule_version: string;
            sales_scope: components["schemas"]["FilterScope"];
            /**
             * Sample Channel Ids
             * @default null
             */
            sample_channel_ids: string[] | null;
            /**
             * Sample Channel Set Status
             * @constant
             */
            sample_channel_set_status: "UNKNOWN";
            /** Sample History Recomputed */
            sample_history_recomputed: boolean;
            sample_mode: components["schemas"]["SampleMode"];
            /**
             * Schema Version
             * @default competition-condition/v1
             * @constant
             */
            schema_version: "competition-condition/v1";
            source_tense: components["schemas"]["SourceTense"];
            /**
             * Timezone
             * @constant
             */
            timezone: "Asia/Shanghai";
            /** Unknown Flags */
            unknown_flags: components["schemas"]["UnknownFlag"][];
            /**
             * Warehouse As Of
             * @default null
             */
            warehouse_as_of: string | null;
        };
        /** CompetitionResultRef */
        CompetitionResultRef: {
            /**
             * Analysis Id
             * @default null
             */
            analysis_id: string | null;
            completeness: components["schemas"]["Completeness"];
            /**
             * Contains Real Data
             * @default false
             * @constant
             */
            contains_real_data: false;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "SNAPSHOT";
            /**
             * Empty Reason
             * @default null
             * @enum {unknown}
             */
            empty_reason: "NO_CURRENT_MONTH_DATA" | "EMPTY_MATURE_COHORT" | "ZERO_COHORT" | "PERIOD_AFTER_AS_OF" | null;
            /**
             * Evidence Digest
             * @default null
             */
            evidence_digest: string | null;
            /**
             * Existing Result Schema
             * @enum {string}
             */
            existing_result_schema: "analytics-channel-followup/v1" | "analytics-first-purchase-path/v1" | "analytics-saved-analysis/v1" | "analytics-run-b0/v1" | "analytics-handoff-audience/v1" | "none";
            /**
             * Facts Schema Ref
             * @enum {string}
             */
            facts_schema_ref: "backend.contracts.analytics_query.ChannelFollowupResult" | "backend.contracts.analytics_first_purchase.FirstPurchaseResult" | "backend.contracts.audience.AudienceSummaryResponse" | "backend.semantic.analytics_handoff_audience" | "competition-result/v1#empty" | "competition-result/v1#unsupported";
            /** Limitations */
            limitations: string[];
            /**
             * Metric Id
             * @default null
             */
            metric_id: string | null;
            /**
             * Metric Version
             * @default null
             */
            metric_version: string | null;
            /** @default null */
            page: components["schemas"]["ResultPage"] | null;
            /**
             * Primary Result Ref
             * @default null
             */
            primary_result_ref: string | null;
            /** Query Id */
            query_id: string;
            /** Query Version */
            query_version: string;
            resolved_condition: components["schemas"]["CompetitionResolvedCondition"];
            /** Result Id */
            result_id: string;
            /** Row Count */
            row_count: number;
            /**
             * Run Id
             * @default null
             */
            run_id: string | null;
            /**
             * Schema Version
             * @default competition-result/v1
             * @constant
             */
            schema_version: "competition-result/v1";
        };
        /**
         * Completeness
         * @enum {string}
         */
        Completeness: "COMPLETE" | "EMPTY" | "INSUFFICIENT" | "UNSUPPORTED" | "FAILED" | "PARTIAL";
        /**
         * DraftStatus
         * @enum {string}
         */
        DraftStatus: "DRAFT" | "REVIEW_PENDING" | "EXPIRED" | "SUPERSEDED";
        /** EndorsedResultRef */
        EndorsedResultRef: {
            /**
             * Analysis Id
             * @default null
             */
            analysis_id: string | null;
            /**
             * Completeness
             * @default COMPLETE
             * @constant
             */
            completeness: "COMPLETE";
            /** Evidence Digest */
            evidence_digest: string;
            /** Result Id */
            result_id: string;
            /** Run Id */
            run_id: string;
        };
        /** FilterScope */
        FilterScope: {
            /** Channel Ids */
            channel_ids?: string[];
            kind: components["schemas"]["ScopeKind"];
            /** Product Ids */
            product_ids?: string[];
        };
        /** InclusiveDateRange */
        InclusiveDateRange: {
            /**
             * End Bound
             * @default INCLUSIVE_CALENDAR_DAY
             * @constant
             */
            end_bound: "INCLUSIVE_CALENDAR_DAY";
            /**
             * End Date
             * Format: date
             */
            end_date: string;
            /**
             * Start Date
             * Format: date
             */
            start_date: string;
        };
        /**
         * MemberMark
         * @enum {string}
         */
        MemberMark: "MEMBER" | "NON_MEMBER" | "UNKNOWN";
        /**
         * NonRepurchaseKind
         * @enum {string}
         */
        NonRepurchaseKind: "ORIGIN_CHANNEL_ABSENT" | "ORIGIN_PRODUCT_ABSENT" | "STOREWIDE_ABSENT";
        /**
         * PatchIntent
         * @enum {string}
         */
        PatchIntent: "STYLE_ONLY" | "FILTER_CHANGE" | "STRUCTURE";
        /** PendingDefault */
        PendingDefault: {
            /** Key */
            key: string;
            /** Note */
            note: string;
            /** Pending Confirmation */
            pending_confirmation: boolean;
            /** Value */
            value: string | boolean;
        };
        /** ResultPage */
        ResultPage: {
            /** Checksum */
            checksum: string;
            /** Complete */
            complete: boolean;
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /**
         * SampleMode
         * @enum {string}
         */
        SampleMode: "INCLUDE" | "EXCLUDE_CURRENT_SALES_ONLY" | "EXCLUDE_AND_RECOMPUTE_HISTORY";
        /**
         * ScopeKind
         * @enum {string}
         */
        ScopeKind: "ALL" | "CHANNEL_IDS" | "PRODUCT_IDS" | "CHANNEL_AND_PRODUCT";
        /**
         * SnapshotCompat
         * @enum {string}
         */
        SnapshotCompat: "READ_OLD_SNAPSHOT" | "ISOLATED_NEW" | "REJECT_UNSUPPORTED_VERSION";
        /**
         * SourceTense
         * @enum {string}
         */
        SourceTense: "PUBLISHED_SNAPSHOT" | "REBUILT_FROM_LATEST_CORRECTIONS";
        /**
         * SupportStatus
         * @enum {string}
         */
        SupportStatus: "SUPPORTED" | "PARTIAL" | "UNSUPPORTED" | "UNKNOWN" | "NOT_CONNECTED";
        /** UnknownFlag */
        UnknownFlag: {
            /**
             * Code
             * @enum {string}
             */
            code: "SAMPLE_CHANNEL_SET" | "MEMBER_HISTORY" | "F_ORDER_GRAIN_OLD_CRM" | "NEW_OLD_CUSTOM_MONTH_CUTOFF" | "VALID_ORDER_RULE_OLD_CRM";
            /** Note */
            note: string;
            /**
             * Status
             * @default UNKNOWN
             * @constant
             */
            status: "UNKNOWN";
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
