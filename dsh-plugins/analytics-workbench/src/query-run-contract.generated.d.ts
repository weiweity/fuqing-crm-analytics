/** Generated query-run store contract; do not edit. Not an HTTP API. OpenAPI SHA-256: 303b59d46e814d01650b3b46e8655dccb609f205679e4725ff7b48481f68350c */
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AnalyticsQueryConversation */
        AnalyticsQueryConversation: {
            /** Conversation Id */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Run Ids */
            run_ids?: string[];
            /**
             * Schema Version
             * @default analytics-run-channel-followup/v1
             * @constant
             */
            schema_version: "analytics-run-channel-followup/v1";
            /** Title */
            title: string;
            /**
             * Version
             * @default 1
             */
            version: number;
        };
        /** AnalyticsQueryConversationRequest */
        AnalyticsQueryConversationRequest: {
            /**
             * Title
             * @default 渠道后续购买查询
             */
            title: string;
        };
        /** AnalyticsQueryEventPayload */
        AnalyticsQueryEventPayload: {
            phase: components["schemas"]["AnalyticsRunPhase"];
            status: components["schemas"]["AnalyticsRunStatus"];
            /**
             * Step Id
             * @default null
             */
            step_id: string | null;
            /** Version */
            version: number;
        };
        /** AnalyticsQueryRunAccepted */
        AnalyticsQueryRunAccepted: {
            /** Location */
            location: string;
            /**
             * Phase
             * @default ACCEPTED
             * @constant
             */
            phase: "ACCEPTED";
            /** Run Id */
            run_id: string;
            /**
             * Schema Version
             * @default analytics-run-channel-followup/v1
             * @constant
             */
            schema_version: "analytics-run-channel-followup/v1";
            /**
             * Status
             * @default QUEUED
             * @constant
             */
            status: "QUEUED";
            /**
             * Version
             * @default 1
             * @constant
             */
            version: 1;
        };
        /** AnalyticsQueryRunEvent */
        AnalyticsQueryRunEvent: {
            /** Event Id */
            event_id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            payload: components["schemas"]["AnalyticsQueryEventPayload"];
            /** Run Id */
            run_id: string;
            /** Sequence */
            sequence: number;
            /**
             * Type
             * @enum {string}
             */
            type: "run.updated" | "run.started" | "tool.started" | "tool.completed" | "run.needs_input" | "run.completed" | "run.failed" | "run.cancelled";
        };
        /** AnalyticsQueryRunRequest */
        AnalyticsQueryRunRequest: {
            /**
             * Condition Patch
             * @default null
             */
            condition_patch: null;
            /**
             * Parent Run Id
             * @default null
             */
            parent_run_id: string | null;
            /** Question */
            question: string;
            /**
             * Schema Version
             * @default analytics-run-channel-followup/v1
             * @constant
             */
            schema_version: "analytics-run-channel-followup/v1";
        };
        /** AnalyticsQueryRunSnapshot */
        AnalyticsQueryRunSnapshot: {
            /**
             * Answer Mode
             * @default DETERMINISTIC_TOOL
             * @constant
             */
            answer_mode: "DETERMINISTIC_TOOL";
            /** Conversation Id */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Deadline
             * Format: date-time
             */
            deadline: string;
            diagnostics: components["schemas"]["AnalyticsRunDiagnostics"];
            /** Evidence Digest */
            evidence_digest: string | null;
            /** Evidence Refs */
            evidence_refs: string[];
            /** Last Sequence */
            last_sequence: number;
            /** Limitations */
            limitations?: string[];
            /** Parent Run Id */
            parent_run_id: string | null;
            phase: components["schemas"]["AnalyticsRunPhase"];
            /** Primary Result Ref */
            primary_result_ref: string | null;
            result: components["schemas"]["ChannelFollowupResult"] | null;
            /** Run Id */
            run_id: string;
            /**
             * Schema Version
             * @default analytics-run-channel-followup/v1
             * @constant
             */
            schema_version: "analytics-run-channel-followup/v1";
            /**
             * Source Kind
             * @default CHAT
             * @constant
             */
            source_kind: "CHAT";
            /** Source Ref */
            source_ref: string;
            status: components["schemas"]["AnalyticsRunStatus"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /** AnalyticsRunDiagnostics */
        AnalyticsRunDiagnostics: {
            /** Attempt Id */
            attempt_id: string;
            /** Dispatch Attempts */
            dispatch_attempts: number;
            /**
             * Error Code
             * @default null
             */
            error_code: string | null;
            /** Execution Active */
            execution_active: boolean;
            /** Profile Hash */
            profile_hash: string;
            /** Profile Version */
            profile_version: string;
            /**
             * Runtime Status
             * @enum {string}
             */
            runtime_status: "PENDING" | "DISPATCHING" | "ACCEPTED" | "UNKNOWN" | "EXITED";
            /** Tool Steps Used */
            tool_steps_used: number;
        };
        /**
         * AnalyticsRunPhase
         * @enum {string}
         */
        AnalyticsRunPhase: "ACCEPTED" | "PLANNING" | "EXECUTING" | "FINALIZING";
        /**
         * AnalyticsRunStatus
         * @enum {string}
         */
        AnalyticsRunStatus: "QUEUED" | "RUNNING" | "NEEDS_INPUT" | "SUCCEEDED" | "FAILED" | "CANCELLING" | "CANCELLED" | "UNKNOWN";
        /** ChannelFollowupChannelRow */
        ChannelFollowupChannelRow: {
            /** Channel Cross Channel Count */
            channel_cross_channel_count: number;
            /**
             * Channel Cross Channel Ratio
             * @default null
             */
            channel_cross_channel_ratio: number | null;
            /**
             * Channel Empty Reason
             * @default null
             */
            channel_empty_reason: "EMPTY_MATURE_COHORT" | null;
            /**
             * Channel Id
             * @enum {string}
             */
            channel_id: "A" | "B";
            /** Channel Immature Count */
            channel_immature_count: number;
            /** Channel Mature Cohort Count */
            channel_mature_cohort_count: number;
            /** Channel Repeat Count */
            channel_repeat_count: number;
            /**
             * Channel Repeat Ratio
             * @default null
             */
            channel_repeat_ratio: number | null;
            /**
             * Channel Window Net Paid Minor
             * @default null
             */
            channel_window_net_paid_minor: number | null;
        };
        /**
         * ChannelFollowupCounts
         * @description Count/ratio block; inherits BaseModel so contract lint sees *_ratio fields.
         */
        ChannelFollowupCounts: {
            /** Channel Cross Channel Count */
            channel_cross_channel_count: number;
            /**
             * Channel Cross Channel Ratio
             * @default null
             */
            channel_cross_channel_ratio: number | null;
            /**
             * Channel Empty Reason
             * @default null
             */
            channel_empty_reason: "EMPTY_MATURE_COHORT" | null;
            /** Channel Immature Count */
            channel_immature_count: number;
            /** Channel Mature Cohort Count */
            channel_mature_cohort_count: number;
            /** Channel Repeat Count */
            channel_repeat_count: number;
            /**
             * Channel Repeat Ratio
             * @default null
             */
            channel_repeat_ratio: number | null;
            /**
             * Channel Window Net Paid Minor
             * @default null
             */
            channel_window_net_paid_minor: number | null;
        };
        /** ChannelFollowupFacts */
        ChannelFollowupFacts: {
            /**
             * Amount Precision
             * @default integer_fen
             * @constant
             */
            amount_precision: "integer_fen";
            /**
             * Amount Unit
             * @default minor
             * @constant
             */
            amount_unit: "minor";
            /** Channels */
            channels: components["schemas"]["ChannelFollowupChannelRow"][];
            /**
             * Currency
             * @default CNY
             * @constant
             */
            currency: "CNY";
            /**
             * Display Name
             * @default 首次观察到的渠道 / N日二单率
             * @constant
             */
            display_name: "首次观察到的渠道 / N日二单率";
            /**
             * Observation Days
             * @enum {integer}
             */
            observation_days: 30 | 60 | 90;
            totals: components["schemas"]["ChannelFollowupCounts"];
        };
        /** ChannelFollowupFixtureDescriptor */
        ChannelFollowupFixtureDescriptor: {
            /** As Of */
            as_of: string;
            /** Data Digest */
            data_digest: string;
            /**
             * Data Version
             * @default synthetic-channel-followup-data/v1
             * @constant
             */
            data_version: "synthetic-channel-followup-data/v1";
            /** Physical Sha256 */
            physical_sha256: string;
            /**
             * Snapshot Id
             * @default synthetic-channel-followup-v1
             * @constant
             */
            snapshot_id: "synthetic-channel-followup-v1";
            /**
             * Timezone
             * @default Asia/Shanghai
             * @constant
             */
            timezone: "Asia/Shanghai";
        };
        /** ChannelFollowupResolvedFilters */
        ChannelFollowupResolvedFilters: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Channel Ids */
            channel_ids: ("A" | "B")[];
            /**
             * Cohort Ref
             * @default null
             */
            cohort_ref: null;
            /**
             * Cohort Window Kind
             * @default FIXED
             * @constant
             */
            cohort_window_kind: "FIXED";
            /**
             * Comparison
             * @default null
             */
            comparison: null;
            /** Data Digest */
            data_digest: string;
            /**
             * Data Snapshot Ref
             * @default synthetic-channel-followup-v1
             * @constant
             */
            data_snapshot_ref: "synthetic-channel-followup-v1";
            /**
             * Data Version
             * @default synthetic-channel-followup-data/v1
             * @constant
             */
            data_version: "synthetic-channel-followup-data/v1";
            /**
             * Exclude Low Price
             * @default false
             * @constant
             */
            exclude_low_price: false;
            /** Filter Hash */
            filter_hash: string;
            /**
             * Hash Version
             * @default channel-followup-filter-hash/v1
             * @constant
             */
            hash_version: "channel-followup-filter-hash/v1";
            /**
             * Metric Id
             * @default channel_first_observed_n_day_repeat
             * @constant
             */
            metric_id: "channel_first_observed_n_day_repeat";
            /**
             * Metric Version
             * @default channel-followup-metric/v1
             * @constant
             */
            metric_version: "channel-followup-metric/v1";
            /**
             * Observation Days
             * @enum {integer}
             */
            observation_days: 30 | 60 | 90;
            /** Permission Scope */
            permission_scope: string;
            /**
             * Product Ids
             * @description This subset rejects any product filter; only the empty array is valid.
             * @default []
             * @constant
             */
            product_ids: never[];
            /**
             * Query Id
             * @default channel_first_observed_followup
             * @constant
             */
            query_id: "channel_first_observed_followup";
            /**
             * Query Version
             * @default channel-followup-query/v1
             * @constant
             */
            query_version: "channel-followup-query/v1";
            /**
             * Resolved Cohort End
             * Format: date-time
             */
            resolved_cohort_end: string;
            /**
             * Resolved Cohort Start
             * Format: date-time
             */
            resolved_cohort_start: string;
            /**
             * Schema Version
             * @default analytics-channel-followup/v1
             * @constant
             */
            schema_version: "analytics-channel-followup/v1";
            /**
             * Timezone
             * @default Asia/Shanghai
             * @constant
             */
            timezone: "Asia/Shanghai";
        };
        /** ChannelFollowupResult */
        ChannelFollowupResult: {
            /**
             * Answer Mode
             * @default DETERMINISTIC_TOOL
             * @constant
             */
            answer_mode: "DETERMINISTIC_TOOL";
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /**
             * Contains Real Data
             * @default false
             * @constant
             */
            contains_real_data: false;
            /**
             * Data Snapshot Ref
             * @default synthetic-channel-followup-v1
             * @constant
             */
            data_snapshot_ref: "synthetic-channel-followup-v1";
            /**
             * Data Source
             * @default SYNTHETIC_SNAPSHOT
             * @constant
             */
            data_source: "SYNTHETIC_SNAPSHOT";
            /**
             * Data Version
             * @default synthetic-channel-followup-data/v1
             * @constant
             */
            data_version: "synthetic-channel-followup-data/v1";
            facts: components["schemas"]["ChannelFollowupFacts"];
            /** Filter Hash */
            filter_hash: string;
            /**
             * Hash Version
             * @default channel-followup-filter-hash/v1
             * @constant
             */
            hash_version: "channel-followup-filter-hash/v1";
            /** Limitations */
            limitations: string[];
            /**
             * Metric Id
             * @default channel_first_observed_n_day_repeat
             * @constant
             */
            metric_id: "channel_first_observed_n_day_repeat";
            /**
             * Metric Version
             * @default channel-followup-metric/v1
             * @constant
             */
            metric_version: "channel-followup-metric/v1";
            /**
             * Query Id
             * @default channel_first_observed_followup
             * @constant
             */
            query_id: "channel_first_observed_followup";
            /**
             * Query Version
             * @default channel-followup-query/v1
             * @constant
             */
            query_version: "channel-followup-query/v1";
            resolved_filters: components["schemas"]["ChannelFollowupResolvedFilters"];
            /**
             * Schema Version
             * @default analytics-channel-followup/v1
             * @constant
             */
            schema_version: "analytics-channel-followup/v1";
        };
        /** ChannelFollowupRunBinding */
        ChannelFollowupRunBinding: {
            /**
             * Family
             * @default channel_followup
             * @constant
             */
            family: "channel_followup";
            fixture: components["schemas"]["ChannelFollowupFixtureDescriptor"];
            /** Method Package Digest */
            method_package_digest: string;
            /** Permission Scope */
            permission_scope: string;
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
