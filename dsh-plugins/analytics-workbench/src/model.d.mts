/** Type face for the dependency-free logic module used by Host and browser. */
export const TOOL_NAME: 'analytics_b0_query';
export const TITLE_STORAGE_KEY: string;
export const DEFAULT_TITLE: string;
export const MAX_TITLE_LENGTH: 40;
export interface Fixture {
  schema_version: 'analytics-b0/v1';
  answer_mode: 'STUB';
  data_source: 'SYNTHETIC_FIXTURE';
  fixture_id: 'b0-channel-repeat-2026-09-01';
  data_as_of: '2026-09-01';
  channel: '合成渠道 A';
  customers: 100;
  repeat_customers: 25;
  repeat_rate: 0.25;
}
export const FIXTURE: Readonly<Fixture>;
export interface Editor {
  title: string;
  draft: string;
  revision: number;
  preview: { title: string; baseRevision: number } | null;
}
export function decodeFixture(meta: unknown): Fixture | null;
export function normalizeTitle(value: unknown): string;
export function createEditor(title?: string): Editor;
export function changeDraft(editor: Editor, draft: string): Editor;
export function previewTitle(editor: Editor): Editor;
export function applyTitle(editor: Editor): Editor;
export function serializeTitle(title: string): string;
export function restoreTitle(raw: string | null): { title: string; restored: boolean; invalid: boolean };
export function executeFixture(query: string, signal: AbortSignal): Promise<Fixture>;
