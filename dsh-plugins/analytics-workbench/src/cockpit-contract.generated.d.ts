/** Generated cockpit HTTP contract; do not edit. OpenAPI SHA-256: 478c7ab035fcbb6354c13b2027022008d2b096c6708d79a63a593688968d113a */
export interface paths {
    "/api/v1/analytics/dashboards": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Dashboards */
        get: operations["analytics_dashboard_list"];
        put?: never;
        /** Create Dashboard */
        post: operations["analytics_dashboard_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/dashboards/{dashboard_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Dashboard */
        get: operations["analytics_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/dashboards/{dashboard_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Dashboard */
        post: operations["analytics_dashboard_preview"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/dashboards/{dashboard_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apply Dashboard */
        post: operations["analytics_dashboard_apply"];
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
        /** AnalyticsCockpitAddOp */
        AnalyticsCockpitAddOp: {
            analysis_ref: components["schemas"]["AnalyticsCockpitAnalysisRef"];
            display_overrides?: components["schemas"]["AnalyticsCockpitDisplayOverrides"] | null;
            layout?: components["schemas"]["AnalyticsCockpitLayout"] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "add";
            plugin_ref?: components["schemas"]["AnalyticsCockpitTablePlugin"] | null;
        };
        /** AnalyticsCockpitAnalysisRef */
        AnalyticsCockpitAnalysisRef: {
            /** Analysis Id */
            analysis_id: string;
            /** Version */
            version: number;
        };
        /** AnalyticsCockpitCardError */
        AnalyticsCockpitCardError: {
            /** Code */
            code: string;
            /** Message */
            message: string;
        };
        /** AnalyticsCockpitCardOk */
        AnalyticsCockpitCardOk: {
            analysis_ref: components["schemas"]["AnalyticsCockpitAnalysisRef"];
            /** Card Id */
            card_id: string;
            /**
             * Data Mode
             * @constant
             */
            data_mode: "SNAPSHOT";
            /** Display Overrides */
            display_overrides: {
                [key: string]: string;
            };
            /** Effective Spec Hash */
            effective_spec_hash: string;
            facts: components["schemas"]["ChannelFollowupFacts"];
            /** Filter Hash */
            filter_hash: string;
            /** Filter Mapping */
            filter_mapping: {
                [key: string]: string;
            };
            /**
             * Freshness
             * @constant
             */
            freshness: "PINNED";
            layout: components["schemas"]["AnalyticsCockpitLayout"];
            /** Limitations */
            limitations: string[];
            /** Local Filters */
            local_filters: {
                [key: string]: string[];
            };
            plugin_ref: components["schemas"]["AnalyticsCockpitTablePlugin"];
            snapshot: components["schemas"]["AnalyticsSavedSnapshot"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source_status: "OK";
        };
        /** AnalyticsCockpitCardUnavailable */
        AnalyticsCockpitCardUnavailable: {
            analysis_ref?: components["schemas"]["AnalyticsCockpitAnalysisRef"] | null;
            /** Card Id */
            card_id: string;
            /**
             * Data Mode
             * @default SNAPSHOT
             * @constant
             */
            data_mode: "SNAPSHOT";
            error: components["schemas"]["AnalyticsCockpitCardError"];
            /**
             * Freshness
             * @default PINNED
             * @constant
             */
            freshness: "PINNED";
            layout: components["schemas"]["AnalyticsCockpitLayout"];
            plugin_ref?: components["schemas"]["AnalyticsCockpitTablePlugin"] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source_status: "UNAVAILABLE";
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
        /** AnalyticsCockpitCreateRequest */
        AnalyticsCockpitCreateRequest: {
            /** Title */
            title?: string | null;
        };
        /** AnalyticsCockpitDisplayOverrides */
        AnalyticsCockpitDisplayOverrides: {
            /** Title */
            title: string;
        };
        /** AnalyticsCockpitFilters */
        AnalyticsCockpitFilters: {
            /** Channel Ids */
            channel_ids: string[];
            /**
             * Schema Version
             * @default analytics-cockpit-filters/v1
             * @constant
             */
            schema_version: "analytics-cockpit-filters/v1";
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
        /** AnalyticsDashboard */
        AnalyticsDashboard: {
            /** Affected Card Ids */
            affected_card_ids: string[];
            /** Base Version */
            base_version: number;
            /** Cards */
            cards: (components["schemas"]["AnalyticsCockpitCardOk"] | components["schemas"]["AnalyticsCockpitCardUnavailable"])[];
            /** Created At */
            created_at: string;
            /** Dashboard Id */
            dashboard_id: string;
            /**
             * Finite Mock
             * @constant
             */
            finite_mock: true;
            global_filters: components["schemas"]["AnalyticsCockpitFilters"];
            /**
             * Http Api
             * @default CONNECTED
             * @constant
             */
            http_api: "CONNECTED";
            /** Owner Id */
            owner_id: string;
            /** Persisted */
            persisted: boolean;
            /** Preview */
            preview: boolean;
            /**
             * Schema Version
             * @default analytics-cockpit/v1
             * @constant
             */
            schema_version: "analytics-cockpit/v1";
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
        /** AnalyticsDashboardList */
        AnalyticsDashboardList: {
            /** Items */
            items: components["schemas"]["AnalyticsDashboardListItem"][];
            /**
             * Schema Version
             * @default analytics-cockpit/v1
             * @constant
             */
            schema_version: "analytics-cockpit/v1";
        };
        /** AnalyticsDashboardListItem */
        AnalyticsDashboardListItem: {
            /** Card Count */
            card_count: number;
            /** Dashboard Id */
            dashboard_id: string;
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
             * Schema Version
             * @default analytics-cockpit/v1
             * @constant
             */
            schema_version: "analytics-cockpit/v1";
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
    analytics_dashboard_list: {
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
                    "application/json": components["schemas"]["AnalyticsDashboardList"];
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
    analytics_dashboard_create: {
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
                "application/json": components["schemas"]["AnalyticsCockpitCreateRequest"];
            };
        };
        responses: {
            /** @description Owner already has a private dashboard. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsDashboard"];
                };
            };
            /** @description Created the owner's private dashboard. */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsDashboard"];
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
    analytics_dashboard_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dashboard_id: string;
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
                    "application/json": components["schemas"]["AnalyticsDashboard"];
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
    analytics_dashboard_preview: {
        parameters: {
            query?: never;
            header: {
                "If-Match": string;
            };
            path: {
                dashboard_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalyticsCockpitAddOp"] | components["schemas"]["AnalyticsCockpitCopyOp"] | components["schemas"]["AnalyticsCockpitRemoveOp"] | components["schemas"]["AnalyticsCockpitLayoutOp"] | components["schemas"]["AnalyticsCockpitUndoOp"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsDashboard"];
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
    analytics_dashboard_apply: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "If-Match": string;
            };
            path: {
                dashboard_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalyticsCockpitAddOp"] | components["schemas"]["AnalyticsCockpitCopyOp"] | components["schemas"]["AnalyticsCockpitRemoveOp"] | components["schemas"]["AnalyticsCockpitLayoutOp"] | components["schemas"]["AnalyticsCockpitUndoOp"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsDashboard"];
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
