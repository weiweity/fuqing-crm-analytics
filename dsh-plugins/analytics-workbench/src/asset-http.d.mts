export const ASSET_HTTP: 'CONNECTED';
export function assetRequest(path: string, options?: {
  method?: string;
  body?: unknown;
  key?: string;
  etag?: string | number | null;
}): Promise<{ status: number; payload: any; etag: string | null }>;
export function probeAssetHttp(): Promise<boolean>;
export function decodeAssetError(payload: unknown): { code: string; message: string };
export function decodeHttpAnalysisList(payload: unknown): Array<{
  analysis_id: string; version: number; title: string; observation_days?: number; as_of?: string;
}> | null;
export function decodeHttpDashboard(payload: unknown): {
  schema_version: string;
  http_api: string;
  dashboard_id: string;
  version: number;
  preview?: boolean;
  persisted?: boolean;
  cards: unknown[];
} | null;
export function addIntentKey(analysisId: string, analysisVersion: number, boardVersion: number): string | null;
export function dashboardContainsAnalysis(payload: unknown, analysisId: string, version: number): boolean;
export function formatCard(card: unknown): {
  kind: 'error' | 'ok';
  family?: 'first_purchase' | 'channel_followup';
  card_id: string;
  analysis_ref?: { analysis_id: string; version: number } | null;
  layout: { x: number; y: number; w: number; h: number };
  message?: string;
  title?: string;
  days?: number;
  as_of?: string;
  channels?: string;
  run_id?: string;
  limitations?: string[];
  totals?: { channel_mature_cohort_count: number; channel_repeat_count: number } | null;
  products?: unknown[] | null;
  cohortMature?: number | null;
  displayName?: string;
};
