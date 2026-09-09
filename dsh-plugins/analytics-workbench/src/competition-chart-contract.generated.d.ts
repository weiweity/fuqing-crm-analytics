/** Generated competition chart runtime extension; do not edit. */
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** CompetitionChartPatchRequest */
        CompetitionChartPatchRequest: {
            /** Attempt Id */
            attempt_id: string;
            /** Base Version */
            base_version: number;
            /** Block Id */
            block_id: string;
            /** Board Id */
            board_id: string;
            /**
             * Chart Type
             * @enum {string}
             */
            chart_type: "TABLE" | "BAR" | "LINE" | "METRIC" | "EVIDENCE";
            /** Idempotency Key */
            idempotency_key: string;
            /**
             * Intent
             * @default STYLE_ONLY
             * @constant
             */
            intent: "STYLE_ONLY";
            /**
             * Schema Version
             * @default competition-board-chart-patch/v1
             * @constant
             */
            schema_version: "competition-board-chart-patch/v1";
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
