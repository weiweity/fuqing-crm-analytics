/** Generated competition computed runtime extension; do not edit. */
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ComparisonMode
         * @enum {string}
         */
        ComparisonMode: "YOY_SAME_PERIOD" | "LAST_WEEK_SAME_WEEKDAY" | "CUSTOM_DUAL_WINDOW";
        /** CompetitionComputedResult */
        CompetitionComputedResult: {
            /**
             * Analysis Id
             * @default null
             */
            analysis_id: string | null;
            /**
             * Capability Id
             * @enum {string}
             */
            capability_id: "diag.gsv" | "diag.yoy" | "diag.last_week_same_weekday" | "diag.promo_dual_window";
            completeness: components["schemas"]["Completeness"];
            /**
             * Contains Real Data
             * @default false
             * @constant
             */
            contains_real_data: false;
            /** Data Digest */
            data_digest: string;
            /**
             * Data Mode
             * @default SNAPSHOT
             * @constant
             */
            data_mode: "SNAPSHOT";
            /** Empty Reason */
            empty_reason: ("NO_CURRENT_MONTH_DATA" | "PERIOD_AFTER_AS_OF") | null;
            /** Evidence Digest */
            evidence_digest: string;
            /**
             * Execution Kind
             * @default TOOL_COMPUTATION
             * @constant
             */
            execution_kind: "TOOL_COMPUTATION";
            /**
             * Existing Result Schema
             * @default competition-gsv-facts/v1
             * @constant
             */
            existing_result_schema: "competition-gsv-facts/v1";
            facts: components["schemas"]["CompetitionGsvFacts"];
            /**
             * Facts Schema Ref
             * @default backend.contracts.competition_computed.CompetitionGsvFacts
             * @constant
             */
            facts_schema_ref: "backend.contracts.competition_computed.CompetitionGsvFacts";
            /** Limitations */
            limitations: string[];
            /**
             * Metric Id
             * @default gsv
             * @constant
             */
            metric_id: "gsv";
            /**
             * Metric Version
             * @default competition-gsv-metric/v1
             * @constant
             */
            metric_version: "competition-gsv-metric/v1";
            page: components["schemas"]["ResultPage"] | null;
            /** Primary Result Ref */
            primary_result_ref: string;
            /**
             * Query Id
             * @default competition_gsv_comparison
             * @constant
             */
            query_id: "competition_gsv_comparison";
            /**
             * Query Version
             * @default competition-gsv-query/v1
             * @constant
             */
            query_version: "competition-gsv-query/v1";
            resolved_condition: components["schemas"]["CompetitionResolvedCondition"];
            /** Result Id */
            result_id: string;
            /** Row Count */
            row_count: number;
            /** Run Id */
            run_id: string;
            /**
             * Schema Version
             * @default competition-computed-result/v1
             * @constant
             */
            schema_version: "competition-computed-result/v1";
        };
        /** CompetitionGsvFacts */
        CompetitionGsvFacts: {
            /** Change Ratio */
            change_ratio: number | null;
            /** Change Ratio Unavailable Reason */
            change_ratio_unavailable_reason: ("PERIOD_UNAVAILABLE" | "ZERO_COMPARISON_GSV") | null;
            comparison: components["schemas"]["GsvPeriodFacts"];
            current: components["schemas"]["GsvPeriodFacts"];
            /** Difference */
            difference: number | null;
            /**
             * Metric Type
             * @default GSV
             * @constant
             */
            metric_type: "GSV";
            /**
             * Schema Version
             * @default competition-gsv-facts/v1
             * @constant
             */
            schema_version: "competition-gsv-facts/v1";
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
        /**
         * Completeness
         * @enum {string}
         */
        Completeness: "COMPLETE" | "EMPTY" | "INSUFFICIENT" | "UNSUPPORTED" | "FAILED" | "PARTIAL";
        /** FilterScope */
        FilterScope: {
            /** Channel Ids */
            channel_ids?: string[];
            kind: components["schemas"]["ScopeKind"];
            /** Product Ids */
            product_ids?: string[];
        };
        /** GsvPeriodFacts */
        GsvPeriodFacts: {
            /** Customer Count */
            customer_count: number;
            /** Gsv */
            gsv: number | null;
            /** Order Count */
            order_count: number;
            requested_period: components["schemas"]["InclusiveDateRange"];
            /** Through Date */
            through_date: string | null;
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
         * SourceTense
         * @enum {string}
         */
        SourceTense: "PUBLISHED_SNAPSHOT" | "REBUILT_FROM_LATEST_CORRECTIONS";
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
