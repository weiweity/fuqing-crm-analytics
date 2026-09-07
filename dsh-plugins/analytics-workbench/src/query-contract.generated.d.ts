/** Generated query contract; do not edit. Not an HTTP API. OpenAPI SHA-256: 38b72d2728131084e8038a16f958e6d245aa035cfbcf44bb49d32cc28b6c2f17 */
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
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
        /** ChannelFollowupFixedWindow */
        ChannelFollowupFixedWindow: {
            /**
             * End Date
             * Format: date
             */
            end_date: string;
            /**
             * Kind
             * @constant
             */
            kind: "FIXED";
            /**
             * Start Date
             * Format: date
             */
            start_date: string;
        };
        /** ChannelFollowupOrderHeader */
        ChannelFollowupOrderHeader: {
            /**
             * Channel
             * @enum {string}
             */
            channel: "A" | "B";
            /** Gross Paid Minor */
            gross_paid_minor: number;
            /** Order Id */
            order_id: string;
            /**
             * Paid At
             * Format: date-time
             */
            paid_at: string;
            /**
             * Status
             * @enum {string}
             */
            status: "PAID" | "CANCELLED";
            /** Synthetic User Id */
            synthetic_user_id: string;
        };
        /** ChannelFollowupOrderLine */
        ChannelFollowupOrderLine: {
            /** Line Id */
            line_id: string;
            /** Order Id */
            order_id: string;
            /** Product Id */
            product_id: string;
            /** Quantity */
            quantity: number;
            /** Synthetic User Id */
            synthetic_user_id: string;
        };
        /** ChannelFollowupQueryRequest */
        ChannelFollowupQueryRequest: {
            /** Channel Ids */
            channel_ids?: ("A" | "B")[];
            /**
             * Cohort Ref
             * @default null
             */
            cohort_ref: null;
            cohort_window: components["schemas"]["ChannelFollowupFixedWindow"];
            /**
             * Comparison
             * @default null
             */
            comparison: null;
            /**
             * Data Snapshot Ref
             * @default synthetic-channel-followup-v1
             * @constant
             */
            data_snapshot_ref: "synthetic-channel-followup-v1";
            /**
             * Exclude Low Price
             * @default false
             * @constant
             */
            exclude_low_price: false;
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
        /** ChannelFollowupRefund */
        ChannelFollowupRefund: {
            /** Order Id */
            order_id: string;
            /** Refund Id */
            refund_id: string;
            /** Refund Minor */
            refund_minor: number;
            /**
             * Refunded At
             * Format: date-time
             */
            refunded_at: string;
            /** Synthetic User Id */
            synthetic_user_id: string;
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
        /** ChannelFollowupSnapshot */
        ChannelFollowupSnapshot: {
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
             * Currency
             * @default CNY
             * @constant
             */
            currency: "CNY";
            /**
             * Data Version
             * @default synthetic-channel-followup-data/v1
             * @constant
             */
            data_version: "synthetic-channel-followup-data/v1";
            /** Lines */
            lines: components["schemas"]["ChannelFollowupOrderLine"][];
            /** Orders */
            orders: components["schemas"]["ChannelFollowupOrderHeader"][];
            /** Refunds */
            refunds: components["schemas"]["ChannelFollowupRefund"][];
            /**
             * Schema Version
             * @default analytics-channel-followup/v1
             * @constant
             */
            schema_version: "analytics-channel-followup/v1";
            /**
             * Scope
             * @default synthetic
             * @constant
             */
            scope: "synthetic";
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
