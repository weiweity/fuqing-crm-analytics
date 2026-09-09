/** Generated first-purchase cockpit HTTP contract; do not edit. OpenAPI SHA-256: 512e5b41006202bb49d05021fc6f5dd84007fbe1713ac38545d3edac80e9db05 */
export interface paths {
    "/api/v1/analytics-first-purchase/dashboards": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Dashboards */
        get: operations["analytics_first_purchase_dashboard_list"];
        put?: never;
        /** Create Dashboard */
        post: operations["analytics_first_purchase_dashboard_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics-first-purchase/dashboards/{dashboard_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Dashboard */
        get: operations["analytics_first_purchase_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics-first-purchase/dashboards/{dashboard_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Dashboard */
        post: operations["analytics_first_purchase_dashboard_preview"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics-first-purchase/dashboards/{dashboard_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apply Dashboard */
        post: operations["analytics_first_purchase_dashboard_apply"];
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
        /** FirstPurchaseCockpitAddOp */
        FirstPurchaseCockpitAddOp: {
            analysis_ref: components["schemas"]["FirstPurchaseCockpitAnalysisRef"];
            display_overrides?: components["schemas"]["FirstPurchaseCockpitDisplayOverrides"] | null;
            layout?: components["schemas"]["FirstPurchaseCockpitLayout"] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "add";
            plugin_ref?: components["schemas"]["FirstPurchaseCockpitTablePlugin"] | null;
        };
        /** FirstPurchaseCockpitAnalysisRef */
        FirstPurchaseCockpitAnalysisRef: {
            /** Analysis Id */
            analysis_id: string;
            /** Version */
            version: number;
        };
        /** FirstPurchaseCockpitCardError */
        FirstPurchaseCockpitCardError: {
            /** Code */
            code: string;
            /** Message */
            message: string;
        };
        /** FirstPurchaseCockpitCardOk */
        FirstPurchaseCockpitCardOk: {
            analysis_ref: components["schemas"]["FirstPurchaseCockpitAnalysisRef"];
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
            facts: components["schemas"]["FirstPurchaseFacts"];
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
            layout: components["schemas"]["FirstPurchaseCockpitLayout"];
            /** Limitations */
            limitations: string[];
            /** Local Filters */
            local_filters: {
                [key: string]: string[];
            };
            plugin_ref: components["schemas"]["FirstPurchaseCockpitTablePlugin"];
            snapshot: components["schemas"]["FirstPurchaseSavedSnapshot"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source_status: "OK";
        };
        /** FirstPurchaseCockpitCardUnavailable */
        FirstPurchaseCockpitCardUnavailable: {
            analysis_ref?: components["schemas"]["FirstPurchaseCockpitAnalysisRef"] | null;
            /** Card Id */
            card_id: string;
            /**
             * Data Mode
             * @default SNAPSHOT
             * @constant
             */
            data_mode: "SNAPSHOT";
            error: components["schemas"]["FirstPurchaseCockpitCardError"];
            /**
             * Freshness
             * @default PINNED
             * @constant
             */
            freshness: "PINNED";
            layout: components["schemas"]["FirstPurchaseCockpitLayout"];
            plugin_ref?: components["schemas"]["FirstPurchaseCockpitTablePlugin"] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source_status: "UNAVAILABLE";
        };
        /** FirstPurchaseCockpitCopyOp */
        FirstPurchaseCockpitCopyOp: {
            /** Card Id */
            card_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "copy";
        };
        /** FirstPurchaseCockpitCreateRequest */
        FirstPurchaseCockpitCreateRequest: {
            /** Title */
            title?: string | null;
        };
        /** FirstPurchaseCockpitDisplayOverrides */
        FirstPurchaseCockpitDisplayOverrides: {
            /** Title */
            title: string;
        };
        /** FirstPurchaseCockpitFilters */
        FirstPurchaseCockpitFilters: {
            /** Channel Ids */
            channel_ids: string[];
            /**
             * Schema Version
             * @default analytics-first-purchase-cockpit-filters/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-cockpit-filters/v1";
        };
        /** FirstPurchaseCockpitLayout */
        FirstPurchaseCockpitLayout: {
            /** H */
            h: number;
            /** W */
            w: number;
            /** X */
            x: number;
            /** Y */
            y: number;
        };
        /** FirstPurchaseCockpitLayoutOp */
        FirstPurchaseCockpitLayoutOp: {
            /** Card Id */
            card_id: string;
            layout: components["schemas"]["FirstPurchaseCockpitLayout"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "layout";
        };
        /** FirstPurchaseCockpitRemoveOp */
        FirstPurchaseCockpitRemoveOp: {
            /** Card Id */
            card_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            op: "remove";
        };
        /** FirstPurchaseCockpitTablePlugin */
        FirstPurchaseCockpitTablePlugin: {
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
        /** FirstPurchaseCockpitUndoOp */
        FirstPurchaseCockpitUndoOp: {
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
        /** FirstPurchaseDashboard */
        FirstPurchaseDashboard: {
            /** Affected Card Ids */
            affected_card_ids: string[];
            /** Base Version */
            base_version: number;
            /** Cards */
            cards: (components["schemas"]["FirstPurchaseCockpitCardOk"] | components["schemas"]["FirstPurchaseCockpitCardUnavailable"])[];
            /** Created At */
            created_at: string;
            /** Dashboard Id */
            dashboard_id: string;
            /**
             * Finite Mock
             * @constant
             */
            finite_mock: true;
            global_filters: components["schemas"]["FirstPurchaseCockpitFilters"];
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
             * @default analytics-first-purchase-cockpit/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-cockpit/v1";
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
        /** FirstPurchaseDashboardList */
        FirstPurchaseDashboardList: {
            /** Items */
            items: components["schemas"]["FirstPurchaseDashboardListItem"][];
            /**
             * Schema Version
             * @default analytics-first-purchase-cockpit/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-cockpit/v1";
        };
        /** FirstPurchaseDashboardListItem */
        FirstPurchaseDashboardListItem: {
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
             * @default analytics-first-purchase-cockpit/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-cockpit/v1";
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
        /** FirstPurchaseFacts */
        FirstPurchaseFacts: {
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
            /** Cohort Enrolled Count */
            cohort_enrolled_count: number;
            /** Cohort Immature Count */
            cohort_immature_count: number;
            /** Cohort Mature Count */
            cohort_mature_count: number;
            /**
             * Currency
             * @default CNY
             * @constant
             */
            currency: "CNY";
            /**
             * Display Name
             * @default 首购商品路径 / N日正装转化
             * @constant
             */
            display_name: "首购商品路径 / N日正装转化";
            /**
             * Observation Days
             * @enum {integer}
             */
            observation_days: 30 | 60 | 90;
            /** Products */
            products: components["schemas"]["FirstPurchaseProductRow"][];
        };
        /** FirstPurchaseProductRow */
        FirstPurchaseProductRow: {
            /** Empty Reason */
            empty_reason?: "EMPTY_MATURE_COHORT" | null;
            /** Enrolled Count */
            enrolled_count: number;
            /** Finished Conversion Count */
            finished_conversion_count: number;
            /** Finished Conversion Ratio */
            finished_conversion_ratio?: number | null;
            /** Immature Count */
            immature_count: number;
            /** Mature Count */
            mature_count: number;
            /** Product Id */
            product_id: string;
            /**
             * Role
             * @enum {string}
             */
            role: "sample" | "finished";
        };
        /** FirstPurchaseResolvedFilters */
        FirstPurchaseResolvedFilters: {
            /** As Of */
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
             * @default synthetic-first-purchase-v1
             * @constant
             */
            data_snapshot_ref: "synthetic-first-purchase-v1";
            /**
             * Data Version
             * @default synthetic-first-purchase-data/v1
             * @constant
             */
            data_version: "synthetic-first-purchase-data/v1";
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
             * @default first-purchase-path-filter-hash/v1
             * @constant
             */
            hash_version: "first-purchase-path-filter-hash/v1";
            /**
             * Metric Id
             * @default first_purchase_product_n_day_finished
             * @constant
             */
            metric_id: "first_purchase_product_n_day_finished";
            /**
             * Metric Version
             * @default first-purchase-path-metric/v1
             * @constant
             */
            metric_version: "first-purchase-path-metric/v1";
            /**
             * Observation Days
             * @enum {integer}
             */
            observation_days: 30 | 60 | 90;
            /** Permission Scope */
            permission_scope: string;
            /** Product Ids */
            product_ids?: string[];
            /**
             * Query Id
             * @default first_purchase_product_path
             * @constant
             */
            query_id: "first_purchase_product_path";
            /**
             * Query Version
             * @default first-purchase-path-query/v1
             * @constant
             */
            query_version: "first-purchase-path-query/v1";
            /** Resolved Cohort End */
            resolved_cohort_end: string;
            /** Resolved Cohort Start */
            resolved_cohort_start: string;
            /**
             * Schema Version
             * @default analytics-first-purchase-path/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-path/v1";
            /**
             * Timezone
             * @default Asia/Shanghai
             * @constant
             */
            timezone: "Asia/Shanghai";
        };
        /** FirstPurchaseSavedSnapshot */
        FirstPurchaseSavedSnapshot: {
            /** As Of */
            as_of: string;
            /**
             * Data Snapshot Ref
             * @default synthetic-first-purchase-v1
             * @constant
             */
            data_snapshot_ref: "synthetic-first-purchase-v1";
            /** Evidence Digest */
            evidence_digest: string;
            resolved_filters: components["schemas"]["FirstPurchaseResolvedFilters"];
            /** Run Id */
            run_id: string;
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
    analytics_first_purchase_dashboard_list: {
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
                    "application/json": components["schemas"]["FirstPurchaseDashboardList"];
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
    analytics_first_purchase_dashboard_create: {
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
                "application/json": components["schemas"]["FirstPurchaseCockpitCreateRequest"];
            };
        };
        responses: {
            /** @description Owner already has a private dashboard. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseDashboard"];
                };
            };
            /** @description Created the owner's private dashboard. */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseDashboard"];
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
    analytics_first_purchase_dashboard_get: {
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
                    "application/json": components["schemas"]["FirstPurchaseDashboard"];
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
    analytics_first_purchase_dashboard_preview: {
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
                "application/json": components["schemas"]["FirstPurchaseCockpitAddOp"] | components["schemas"]["FirstPurchaseCockpitCopyOp"] | components["schemas"]["FirstPurchaseCockpitRemoveOp"] | components["schemas"]["FirstPurchaseCockpitLayoutOp"] | components["schemas"]["FirstPurchaseCockpitUndoOp"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseDashboard"];
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
    analytics_first_purchase_dashboard_apply: {
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
                "application/json": components["schemas"]["FirstPurchaseCockpitAddOp"] | components["schemas"]["FirstPurchaseCockpitCopyOp"] | components["schemas"]["FirstPurchaseCockpitRemoveOp"] | components["schemas"]["FirstPurchaseCockpitLayoutOp"] | components["schemas"]["FirstPurchaseCockpitUndoOp"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseDashboard"];
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
