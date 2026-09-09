/** Generated first-purchase saved-analysis HTTP contract; do not edit. OpenAPI SHA-256: f913d2a669597d8e493b0d85e86b34b411aa35d67ceb3a6bec6382ddcc837d40 */
export interface paths {
    "/api/v1/analytics-first-purchase/analyses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Analyses */
        get: operations["analytics_first_purchase_analysis_list"];
        put?: never;
        /** Create Analysis */
        post: operations["analytics_first_purchase_analysis_create"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics-first-purchase/analyses/{analysis_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Analysis */
        get: operations["analytics_first_purchase_analysis_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics-first-purchase/analyses/{analysis_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish Title */
        post: operations["analytics_first_purchase_analysis_publish_title"];
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
        /** FirstPurchaseAnalysisCreateRequest */
        FirstPurchaseAnalysisCreateRequest: {
            /** Created From Run Id */
            created_from_run_id: string;
            /** Title */
            title: string;
            visual_spec?: components["schemas"]["FirstPurchaseVisualSpec"] | null;
        };
        /** FirstPurchaseAnalysisTitleRequest */
        FirstPurchaseAnalysisTitleRequest: {
            /** Title */
            title: string;
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
        /** FirstPurchaseFixedWindow */
        FirstPurchaseFixedWindow: {
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
        /** FirstPurchaseMetricRef */
        FirstPurchaseMetricRef: {
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
        /** FirstPurchaseQueryRef */
        FirstPurchaseQueryRef: {
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
        };
        /** FirstPurchaseQueryRequest */
        FirstPurchaseQueryRequest: {
            /** Channel Ids */
            channel_ids?: ("A" | "B")[];
            /** Cohort Ref */
            cohort_ref?: null;
            cohort_window: components["schemas"]["FirstPurchaseFixedWindow"];
            /** Comparison */
            comparison?: null;
            /**
             * Data Snapshot Ref
             * @default synthetic-first-purchase-v1
             * @constant
             */
            data_snapshot_ref: "synthetic-first-purchase-v1";
            /**
             * Exclude Low Price
             * @default false
             * @constant
             */
            exclude_low_price: false;
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
        /** FirstPurchaseSavedAnalysis */
        FirstPurchaseSavedAnalysis: {
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
             * @default synthetic-first-purchase-data/v1
             * @constant
             */
            data_version: "synthetic-first-purchase-data/v1";
            /**
             * Endorsement
             * @constant
             */
            endorsement: "PERSONAL";
            facts: components["schemas"]["FirstPurchaseFacts"];
            /** Filter Hash */
            filter_hash: string;
            filters: components["schemas"]["FirstPurchaseQueryRequest"];
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
            metric_refs: components["schemas"]["FirstPurchaseMetricRef"][];
            /** Owner Id */
            owner_id: string;
            query_ref: components["schemas"]["FirstPurchaseQueryRef"];
            /**
             * Schema Version
             * @default analytics-first-purchase-saved-analysis/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-saved-analysis/v1";
            snapshot: components["schemas"]["FirstPurchaseSavedSnapshot"];
            /** Title */
            title: string;
            /** Version */
            version: number;
            /**
             * Visibility
             * @constant
             */
            visibility: "PRIVATE";
            visual_spec: components["schemas"]["FirstPurchaseVisualSpec"];
        };
        /** FirstPurchaseSavedAnalysisList */
        FirstPurchaseSavedAnalysisList: {
            /** Items */
            items: components["schemas"]["FirstPurchaseSavedAnalysisListItem"][];
            /**
             * Schema Version
             * @default analytics-first-purchase-saved-analysis/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-saved-analysis/v1";
        };
        /** FirstPurchaseSavedAnalysisListItem */
        FirstPurchaseSavedAnalysisListItem: {
            /** Analysis Id */
            analysis_id: string;
            /** As Of */
            as_of: string;
            cohort_window: components["schemas"]["FirstPurchaseFixedWindow"];
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
             * @default first_purchase_product_path
             * @constant
             */
            query_id: "first_purchase_product_path";
            /**
             * Schema Version
             * @default analytics-first-purchase-saved-analysis/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-saved-analysis/v1";
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
        /** FirstPurchaseVisualSpec */
        FirstPurchaseVisualSpec: {
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    analytics_first_purchase_analysis_list: {
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
                    "application/json": components["schemas"]["FirstPurchaseSavedAnalysisList"];
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
    analytics_first_purchase_analysis_create: {
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
                "application/json": components["schemas"]["FirstPurchaseAnalysisCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseSavedAnalysis"];
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
    analytics_first_purchase_analysis_get: {
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
                    "application/json": components["schemas"]["FirstPurchaseSavedAnalysis"];
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
    analytics_first_purchase_analysis_publish_title: {
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
                "application/json": components["schemas"]["FirstPurchaseAnalysisTitleRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseSavedAnalysis"];
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
