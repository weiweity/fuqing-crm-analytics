/** Generated library canvas contract; do not edit. */
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** BlockChanges */
        BlockChanges: {
            /**
             * Kind
             * @default null
             */
            kind: ("METRIC" | "LINE" | "BAR" | "TABLE" | "TEXT" | "EVIDENCE" | "PROCESS" | "TIMELINE" | "WATERFALL" | "FUNNEL") | null;
            /** @default null */
            layout: components["schemas"]["BoardLayout"] | null;
            /**
             * Props
             * @default null
             */
            props: {
                [key: string]: unknown;
            } | null;
            /**
             * Source Result Id
             * @default null
             */
            source_result_id: string | null;
            /**
             * Title
             * @default null
             */
            title: string | null;
        };
        /** BoardBARBlock */
        BoardBARBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "BAR";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardBARProps"];
            /** Source Result Id */
            source_result_id: string;
            /** Title */
            title: string;
        };
        /** BoardBARProps */
        BoardBARProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Orientation
             * @default horizontal
             * @enum {string}
             */
            orientation: "horizontal" | "vertical";
            /**
             * Show Values
             * @default true
             */
            show_values: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardCurrentEdit */
        BoardCurrentEdit: {
            context: components["schemas"]["BoardEditContext"] | null;
        };
        /** BoardDocument */
        BoardDocument: {
            /** Blocks */
            blocks: (components["schemas"]["BoardMETRICBlock"] | components["schemas"]["BoardLINEBlock"] | components["schemas"]["BoardBARBlock"] | components["schemas"]["BoardTABLEBlock"] | components["schemas"]["BoardTEXTBlock"] | components["schemas"]["BoardEVIDENCEBlock"] | components["schemas"]["BoardPROCESSBlock"] | components["schemas"]["BoardTIMELINEBlock"] | components["schemas"]["BoardWATERFALLBlock"] | components["schemas"]["BoardFUNNELBlock"])[];
            /** Board Id */
            board_id: string;
            /**
             * Schema Version
             * @default board-spec/v1
             * @constant
             */
            schema_version: "board-spec/v1";
            /** Session Id */
            session_id: string;
            /** Title */
            title: string;
            /** Version */
            version: number;
        };
        /** BoardDraft */
        BoardDraft: {
            /** Blocks */
            blocks: (components["schemas"]["BoardMETRICBlock"] | components["schemas"]["BoardLINEBlock"] | components["schemas"]["BoardBARBlock"] | components["schemas"]["BoardTABLEBlock"] | components["schemas"]["BoardTEXTBlock"] | components["schemas"]["BoardEVIDENCEBlock"] | components["schemas"]["BoardPROCESSBlock"] | components["schemas"]["BoardTIMELINEBlock"] | components["schemas"]["BoardWATERFALLBlock"] | components["schemas"]["BoardFUNNELBlock"])[];
            /** Session Id */
            session_id: string;
            /** Title */
            title: string;
        };
        /** BoardEditContext */
        BoardEditContext: {
            /** Base Version */
            base_version: number;
            /** Block */
            block: components["schemas"]["BoardMETRICBlock"] | components["schemas"]["BoardLINEBlock"] | components["schemas"]["BoardBARBlock"] | components["schemas"]["BoardTABLEBlock"] | components["schemas"]["BoardTEXTBlock"] | components["schemas"]["BoardEVIDENCEBlock"] | components["schemas"]["BoardPROCESSBlock"] | components["schemas"]["BoardTIMELINEBlock"] | components["schemas"]["BoardWATERFALLBlock"] | components["schemas"]["BoardFUNNELBlock"];
            /** Block Id */
            block_id: string;
            /** Board Id */
            board_id: string;
            /** Edit Context Id */
            edit_context_id: string;
            /** Expires At Ms */
            expires_at_ms: number;
            /** Facts By Result Id */
            facts_by_result_id: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
            /** Preview Id */
            preview_id: string | null;
            /**
             * Schema Version
             * @default board-edit-context/v1
             * @constant
             */
            schema_version: "board-edit-context/v1";
            /** Session Id */
            session_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "OPEN" | "PROPOSED" | "CANCELLED" | "APPLIED";
        };
        /** BoardEditProposal */
        BoardEditProposal: {
            changes: components["schemas"]["BlockChanges"];
            /** Session Id */
            session_id: string;
        };
        /**
         * BoardEditSelection
         * @description Created by the UI, never by a model tool. Session comes from the saved board.
         */
        BoardEditSelection: {
            /** Base Version */
            base_version: number;
            /** Block Id */
            block_id: string;
        };
        /** BoardEVIDENCEBlock */
        BoardEVIDENCEBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "EVIDENCE";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardEVIDENCEProps"];
            /** Source Result Id */
            source_result_id: string;
            /** Title */
            title: string;
        };
        /** BoardEVIDENCEProps */
        BoardEVIDENCEProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Expanded
             * @default true
             */
            expanded: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Summary
             * @default
             */
            summary: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardFUNNELBlock */
        BoardFUNNELBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "FUNNEL";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardFUNNELProps"];
            /** Source Result Id */
            source_result_id: string;
            /** Title */
            title: string;
        };
        /** BoardFUNNELProps */
        BoardFUNNELProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Rate Basis
             * @default previous
             * @enum {string}
             */
            rate_basis: "previous" | "first";
            /**
             * Show Rates
             * @default true
             */
            show_rates: boolean;
            /**
             * Show Values
             * @default true
             */
            show_values: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardLayout */
        BoardLayout: {
            /** H */
            h: number;
            /** W */
            w: number;
            /** X */
            x: number;
            /** Y */
            y: number;
        };
        /** BoardLayoutPreview */
        BoardLayoutPreview: {
            /** Base Version */
            base_version: number;
            /** Layouts */
            layouts: components["schemas"]["LayoutChange"][];
        };
        /** BoardLINEBlock */
        BoardLINEBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "LINE";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardLINEProps"];
            /** Source Result Id */
            source_result_id: string;
            /** Title */
            title: string;
        };
        /** BoardLINEProps */
        BoardLINEProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Line Style
             * @default solid
             * @enum {string}
             */
            line_style: "solid" | "dashed";
            /**
             * Show Legend
             * @default true
             */
            show_legend: boolean;
            /**
             * Show Points
             * @default true
             */
            show_points: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardMETRICBlock */
        BoardMETRICBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "METRIC";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardMETRICProps"];
            /** Source Result Id */
            source_result_id: string;
            /** Title */
            title: string;
        };
        /** BoardMETRICProps */
        BoardMETRICProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Show Comparison
             * @default true
             */
            show_comparison: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
            /**
             * Value Format
             * @default standard
             * @enum {string}
             */
            value_format: "standard" | "compact";
        };
        /** BoardPatchPreview */
        BoardPatchPreview: {
            /** Base Version */
            base_version: number;
            /** Block Id */
            block_id: string;
            changes: components["schemas"]["BlockChanges"];
        };
        /** BoardPreview */
        BoardPreview: {
            /** Base Version */
            base_version: number;
            /** Expires At Ms */
            expires_at_ms: number;
            /**
             * Operation
             * @enum {string}
             */
            operation: "GENERATE" | "PATCH" | "LAYOUT" | "ROLLBACK";
            /** Preview Id */
            preview_id: string;
            snapshot: components["schemas"]["BoardSnapshot"];
            /**
             * Status
             * @enum {string}
             */
            status: "PENDING" | "APPLIED" | "CANCELLED";
        };
        /** BoardPROCESSBlock */
        BoardPROCESSBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "PROCESS";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardPROCESSProps"];
            /**
             * Source Result Id
             * @default null
             */
            source_result_id: null;
            /** Title */
            title: string;
        };
        /** BoardPROCESSEdgesItem */
        BoardPROCESSEdgesItem: {
            /** From */
            from: string;
            /**
             * Label
             * @default
             */
            label: string;
            /** To */
            to: string;
        };
        /** BoardPROCESSNodesItem */
        BoardPROCESSNodesItem: {
            /**
             * Detail
             * @default
             */
            detail: string;
            /** Id */
            id: string;
            /** Label */
            label: string;
            /**
             * Owner
             * @default
             */
            owner: string;
        };
        /** BoardPROCESSProps */
        BoardPROCESSProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Edges
             * @default []
             */
            edges: components["schemas"]["BoardPROCESSEdgesItem"][];
            /**
             * Nodes
             * @default []
             */
            nodes: components["schemas"]["BoardPROCESSNodesItem"][];
            /**
             * Show Details
             * @default true
             */
            show_details: boolean;
            /**
             * Show Owners
             * @default true
             */
            show_owners: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardRevision */
        BoardRevision: {
            /** Created At Ms */
            created_at_ms: number;
            /**
             * Operation
             * @enum {string}
             */
            operation: "GENERATE" | "PATCH" | "LAYOUT" | "ROLLBACK";
            /** Version */
            version: number;
        };
        /** BoardRollbackPreview */
        BoardRollbackPreview: {
            /** Base Version */
            base_version: number;
            /** To Version */
            to_version: number;
        };
        /** BoardSnapshot */
        BoardSnapshot: {
            /** Facts By Result Id */
            facts_by_result_id: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
            spec: components["schemas"]["BoardDocument"];
        };
        /** BoardTABLEBlock */
        BoardTABLEBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "TABLE";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardTABLEProps"];
            /** Source Result Id */
            source_result_id: string;
            /** Title */
            title: string;
        };
        /** BoardTABLEProps */
        BoardTABLEProps: {
            /**
             * Columns
             * @default []
             */
            columns: string[];
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Page Size
             * @default 10
             */
            page_size: number;
            /**
             * Sort Direction
             * @default asc
             * @enum {string}
             */
            sort_direction: "asc" | "desc";
            /**
             * Sort Field
             * @default
             */
            sort_field: string;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardTEXTBlock */
        BoardTEXTBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "TEXT";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardTEXTProps"];
            /**
             * Source Result Id
             * @default null
             */
            source_result_id: string | null;
            /** Title */
            title: string;
        };
        /** BoardTEXTProps */
        BoardTEXTProps: {
            /**
             * Align
             * @default start
             * @enum {string}
             */
            align: "start" | "center";
            /**
             * Content
             * @default
             */
            content: string;
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Text Style
             * @default body
             * @enum {string}
             */
            text_style: "body" | "callout";
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardTIMELINEBlock */
        BoardTIMELINEBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "TIMELINE";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardTIMELINEProps"];
            /**
             * Source Result Id
             * @default null
             */
            source_result_id: null;
            /** Title */
            title: string;
        };
        /** BoardTIMELINEEventsItem */
        BoardTIMELINEEventsItem: {
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Detail
             * @default
             */
            detail: string;
            /** Id */
            id: string;
            /** Label */
            label: string;
        };
        /** BoardTIMELINEProps */
        BoardTIMELINEProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Events
             * @default []
             */
            events: components["schemas"]["BoardTIMELINEEventsItem"][];
            /**
             * Show Details
             * @default true
             */
            show_details: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Timezone
             * @default Asia/Shanghai
             * @enum {string}
             */
            timezone: "Asia/Shanghai" | "UTC";
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** BoardWATERFALLBlock */
        BoardWATERFALLBlock: {
            /** Block Id */
            block_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "WATERFALL";
            layout: components["schemas"]["BoardLayout"];
            /**
             * Library Version
             * @default board-components/v1
             * @constant
             */
            library_version: "board-components/v1";
            props?: components["schemas"]["BoardWATERFALLProps"];
            /** Source Result Id */
            source_result_id: string;
            /** Title */
            title: string;
        };
        /** BoardWATERFALLProps */
        BoardWATERFALLProps: {
            /**
             * Density
             * @default comfortable
             * @enum {string}
             */
            density: "comfortable" | "compact";
            /**
             * Show Table
             * @default true
             */
            show_table: boolean;
            /**
             * Show Values
             * @default true
             */
            show_values: boolean;
            /**
             * Subtitle
             * @default
             */
            subtitle: string;
            /**
             * Tone
             * @default neutral
             * @enum {string}
             */
            tone: "neutral" | "accent" | "muted";
        };
        /** LayoutChange */
        LayoutChange: {
            /** Block Id */
            block_id: string;
            layout: components["schemas"]["BoardLayout"];
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
