/** Generated first-purchase HTTP contract; do not edit. OpenAPI SHA-256: f9fb8927bf11127d19c848d2683cdf4edcf66dde5b57f8c13c13d6c21a39ab66 */
export interface paths {
    "/api/v1/analytics-first-purchase/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Run */
        post: operations["analytics_first_purchase_create_run"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics-first-purchase/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["analytics_first_purchase_get_run"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics-first-purchase/runs/{run_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Run */
        post: operations["analytics_first_purchase_cancel_run"];
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
        /** AnalyticsCancelRequest */
        AnalyticsCancelRequest: {
            /**
             * Reason
             * @default USER_REQUEST
             * @constant
             */
            reason: "USER_REQUEST";
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
        /** AnalyticsRunDiagnostics */
        AnalyticsRunDiagnostics: {
            /** Attempt Id */
            attempt_id: string;
            /** Dispatch Attempts */
            dispatch_attempts: number;
            /** Error Code */
            error_code?: string | null;
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
        /** FirstPurchaseKernelSnapshot */
        FirstPurchaseKernelSnapshot: {
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
            result: components["schemas"]["FirstPurchaseResult"] | null;
            /** Run Id */
            run_id: string;
            /**
             * Schema Version
             * @default analytics-run-first-purchase-path/v1
             * @constant
             */
            schema_version: "analytics-run-first-purchase-path/v1";
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
        /** FirstPurchaseResult */
        FirstPurchaseResult: {
            /**
             * Answer Mode
             * @default DETERMINISTIC_TOOL
             * @constant
             */
            answer_mode: "DETERMINISTIC_TOOL";
            /** As Of */
            as_of: string;
            /**
             * Contains Real Data
             * @default false
             * @constant
             */
            contains_real_data: false;
            /**
             * Data Snapshot Ref
             * @default synthetic-first-purchase-v1
             * @constant
             */
            data_snapshot_ref: "synthetic-first-purchase-v1";
            /**
             * Data Source
             * @default SYNTHETIC_SNAPSHOT
             * @constant
             */
            data_source: "SYNTHETIC_SNAPSHOT";
            /**
             * Data Version
             * @default synthetic-first-purchase-data/v1
             * @constant
             */
            data_version: "synthetic-first-purchase-data/v1";
            facts?: components["schemas"]["FirstPurchaseFacts"] | null;
            /** Filter Hash */
            filter_hash: string;
            /**
             * Hash Version
             * @default first-purchase-path-filter-hash/v1
             * @constant
             */
            hash_version: "first-purchase-path-filter-hash/v1";
            /** Limitations */
            limitations: string[];
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
            /** Missing Product Ids */
            missing_product_ids?: string[];
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
            /** Reason Code */
            reason_code?: "MISSING_PRODUCT_ROLE" | null;
            resolved_filters: components["schemas"]["FirstPurchaseResolvedFilters"];
            /**
             * Schema Version
             * @default analytics-first-purchase-path/v1
             * @constant
             */
            schema_version: "analytics-first-purchase-path/v1";
            /**
             * Status
             * @enum {string}
             */
            status: "OK" | "REJECTED";
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
    analytics_first_purchase_create_run: {
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
                "application/json": components["schemas"]["FirstPurchaseQueryRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseKernelSnapshot"];
                };
            };
            /** @description Accepted */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseKernelSnapshot"];
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
    analytics_first_purchase_get_run: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
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
                    "application/json": components["schemas"]["FirstPurchaseKernelSnapshot"];
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
    analytics_first_purchase_cancel_run: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
                "If-Match": string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalyticsCancelRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FirstPurchaseKernelSnapshot"];
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
