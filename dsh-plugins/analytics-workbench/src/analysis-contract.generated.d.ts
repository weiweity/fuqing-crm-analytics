/** Generated saved-analysis HTTP contract; do not edit. OpenAPI SHA-256: 805ba7ead5de1b881b8550947063b63bddcf877b3264f7f6b15f10a6dac56c4d */
export interface paths {
    "/api/v1/analytics/analyses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Analyses */
        get: operations["analytics_analysis_list"];
        put?: never;
        /** Create Analysis */
        post: operations["analytics_analysis_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/analyses/{analysis_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Analysis */
        get: operations["analytics_analysis_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/analyses/{analysis_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish Title */
        post: operations["analytics_analysis_publish_title"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AnalyticsAnalysisCreateRequest */
        AnalyticsAnalysisCreateRequest: {
            /** Created From Run Id */
            created_from_run_id: string;
            /** Title */
            title: string;
            visual_spec?: components["schemas"]["AnalyticsVisualSpec"] | null;
        };
        /** AnalyticsAnalysisTitleRequest */
        AnalyticsAnalysisTitleRequest: {
            /** Title */
            title: string;
        };
        /** AnalyticsErrorDetail */
        AnalyticsErrorDetail: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** Recovery Url */
            recovery_url?: string | null;
            /** Request Id */
            request_id: string;
            /** Retryable */
            retryable: boolean;
        };
        /** AnalyticsErrorResponse */
        AnalyticsErrorResponse: {
            error: components["schemas"]["AnalyticsErrorDetail"];
        };
        /** AnalyticsMetricRef */
        AnalyticsMetricRef: {
            /**
             * Metric Id
             * @constant
             */
            metric_id: "channel_first_observed_n_day_repeat";
            /**
             * Metric Version
             * @constant
             */
            metric_version: "channel-followup-metric/v1";
        };
        /** AnalyticsQueryRef */
        AnalyticsQueryRef: {
            /**
             * Query Id
             * @constant
             */
            query_id: "channel_first_observed_followup";
            /**
             * Query Version
             * @constant
             */
            query_version: "channel-followup-query/v1";
        };
        /** AnalyticsRefreshCandidate */
        AnalyticsRefreshCandidate: {
            /** Evidence Digest */
            evidence_digest: string;
            /** Run Id */
            run_id: string;
        };
        /** AnalyticsSavedAnalysis */
        AnalyticsSavedAnalysis: {
            /** Analysis Id */
            analysis_id: string;
            /** Created At */
            created_at: string;
            /** Created From Run Id */
            created_from_run_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "SNAPSHOT";
            /**
             * Data Version
             * @constant
             */
            data_version: "synthetic-channel-followup-data/v1";
            /**
             * Endorsement
             * @constant
             */
            endorsement: "PERSONAL";
            facts: components["schemas"]["ChannelFollowupFacts"];
            /** Filter Hash */
            filter_hash: string;
            filters: components["schemas"]["ChannelFollowupQueryRequest"];
            /**
             * Finite Mock
             * @constant
             */
            finite_mock: true;
            /**
             * Http Api
             * @default CONNECTED
             * @constant
             */
            http_api: "CONNECTED";
            /** Limitations */
            limitations: string[];
            /** Metric Refs */
            metric_refs: components["schemas"]["AnalyticsMetricRef"][];
            /** Owner Id */
            owner_id: string;
            query_ref: components["schemas"]["AnalyticsQueryRef"];
            refresh_candidate: components["schemas"]["AnalyticsRefreshCandidate"] | null;
            /**
             * Schema Version
             * @default analytics-saved-analysis/v1
             * @constant
             */
            schema_version: "analytics-saved-analysis/v1";
            snapshot: components["schemas"]["AnalyticsSavedSnapshot"];
            /** Title */
            title: string;
            /** Version */
            version: number;
            /**
             * Visibility
             * @constant
             */
            visibility: "PRIVATE";
            visual_spec: components["schemas"]["AnalyticsVisualSpec"];
        };
        /** AnalyticsSavedAnalysisList */
        AnalyticsSavedAnalysisList: {
            /** Items */
            items: components["schemas"]["AnalyticsSavedAnalysisListItem"][];
            /**
             * Schema Version
             * @default analytics-saved-analysis/v1
             * @constant
             */
            schema_version: "analytics-saved-analysis/v1";
        };
        /** AnalyticsSavedAnalysisListItem */
        AnalyticsSavedAnalysisListItem: {
            /** Analysis Id */
            analysis_id: string;
            /** As Of */
            as_of: string;
            cohort_window: components["schemas"]["ChannelFollowupFixedWindow"];
            /**
             * Data Mode
             * @constant
             */
            data_mode: "SNAPSHOT";
            /**
             * Finite Mock
             * @constant
             */
            finite_mock: true;
            /**
             * Http Api
             * @default CONNECTED
             * @constant
             */
            http_api: "CONNECTED";
            /**
             * Observation Days
             * @enum {integer}
             */
            observation_days: 30 | 60 | 90;
            /**
             * Query Id
             * @constant
             */
            query_id: "channel_first_observed_followup";
            /** Refreshable */
            refreshable: boolean;
            /**
             * Schema Version
             * @default analytics-saved-analysis/v1
             * @constant
             */
            schema_version: "analytics-saved-analysis/v1";
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
        /** AnalyticsSavedSnapshot */
        AnalyticsSavedSnapshot: {
            /** As Of */
            as_of: string;
            /**
             * Data Snapshot Ref
             * @constant
             */
            data_snapshot_ref: "synthetic-channel-followup-v1";
            /** Evidence Digest */
            evidence_digest: string;
            resolved_filters: components["schemas"]["ChannelFollowupResolvedFilters"];
            /** Run Id */
            run_id: string;
        };
        /** AnalyticsVisualSpec */
        AnalyticsVisualSpec: {
            /**
             * Kind
             * @default TABLE
             * @constant
             */
            kind: "TABLE";
            /**
             * Schema Version
             * @default analytics-visual-table/v1
             * @constant
             */
            schema_version: "analytics-visual-table/v1";
        };
        /** ChannelFollowupChannelRow */
        ChannelFollowupChannelRow: {
            /** Channel Cross Channel Count */
            channel_cross_channel_count: number;
            /** Channel Cross Channel Ratio */
            channel_cross_channel_ratio?: number | null;
            /** Channel Empty Reason */
            channel_empty_reason?: "EMPTY_MATURE_COHORT" | null;
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
            /** Channel Repeat Ratio */
            channel_repeat_ratio?: number | null;
            /** Channel Window Net Paid Minor */
            channel_window_net_paid_minor?: number | null;
        };
        /**
         * ChannelFollowupCounts
         * @description Count/ratio block; inherits BaseModel so contract lint sees *_ratio fields.
         */
        ChannelFollowupCounts: {
            /** Channel Cross Channel Count */
            channel_cross_channel_count: number;
            /** Channel Cross Channel Ratio */
            channel_cross_channel_ratio?: number | null;
            /** Channel Empty Reason */
            channel_empty_reason?: "EMPTY_MATURE_COHORT" | null;
            /** Channel Immature Count */
            channel_immature_count: number;
            /** Channel Mature Cohort Count */
            channel_mature_cohort_count: number;
            /** Channel Repeat Count */
            channel_repeat_count: number;
            /** Channel Repeat Ratio */
            channel_repeat_ratio?: number | null;
            /** Channel Window Net Paid Minor */
            channel_window_net_paid_minor?: number | null;
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
        /** ChannelFollowupQueryRequest */
        ChannelFollowupQueryRequest: {
            /** Channel Ids */
            channel_ids?: ("A" | "B")[];
            /** Cohort Ref */
            cohort_ref?: null;
            cohort_window: components["schemas"]["ChannelFollowupFixedWindow"];
            /** Comparison */
            comparison?: null;
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
        /** ChannelFollowupResolvedFilters */
        ChannelFollowupResolvedFilters: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Channel Ids */
            channel_ids: ("A" | "B")[];
            /** Cohort Ref */
            cohort_ref?: null;
            /**
             * Cohort Window Kind
             * @default FIXED
             * @constant
             */
            cohort_window_kind: "FIXED";
            /** Comparison */
            comparison?: null;
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    analytics_analysis_list: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsSavedAnalysisList"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Precondition Required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
        };
    };
    analytics_analysis_create: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalyticsAnalysisCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsSavedAnalysis"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Precondition Required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
        };
    };
    analytics_analysis_get: {
        parameters: {
            query?: {
                version?: number | null;
            };
            header?: never;
            path: {
                analysis_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsSavedAnalysis"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Precondition Required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
        };
    };
    analytics_analysis_publish_title: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "If-Match": string;
            };
            path: {
                analysis_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalyticsAnalysisTitleRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsSavedAnalysis"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Gone */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Precondition Required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsErrorResponse"];
                };
            };
        };
    };
}
