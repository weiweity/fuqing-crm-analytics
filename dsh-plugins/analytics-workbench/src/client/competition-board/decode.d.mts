export function decodeCompetitionError(value: unknown): {
  code: string; message: string; request_id: string; retryable: boolean; http_status: number;
  param?: string | null; maps_to: string; schema_version: string;
} | null;
export function decodeCompetitionResultRef(value: unknown): any | null;
export function canEndorse(result: unknown): boolean;
export function toEndorsedResultRef(result: any): {
  analysis_id: string | null; completeness: 'COMPLETE'; evidence_digest: string; result_id: string; run_id: string;
} | null;
export function decodeCompetitionBoardSpec(value: unknown): any | null;
export function decodeCompetitionPatchRequest(value: unknown): any | null;
export function looksLikeIllegalScript(value: unknown): boolean;
export function decodeCompetitionBatchRequest(value: unknown): any | null;
export function decodeCompetitionBatchReceipt(value: unknown): any | null;
export function formatResultRowCount(result: any): string;
export function formatAmountUnit(result: any): string;
export function conditionChips(result: any): { id: string; label: string; value: string }[];
export function evidenceFields(result: any): {
  asOf?: string; metricVersion?: string; dataVersion?: string; digest?: string; source?: string;
  limitations: string[]; unknowns: string[];
};
export function defaultBlockLayout(index: number): { x: number; y: number; w: number; h: number };
export const INTENTS: Set<string>;
export const LAYOUT_MODES: Set<string>;
