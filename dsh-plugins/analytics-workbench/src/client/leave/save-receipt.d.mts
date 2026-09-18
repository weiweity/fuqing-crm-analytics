export type SaveReceiptReason = 'uncertain' | 'missing_receipt' | 'malformed_receipt' | 'page_mismatch'
  | 'session_mismatch' | 'cas_mismatch' | 'version_mismatch' | 'conflict' | 'forbidden' | 'failed'
  | 'layout_unsaved' | 'idempotency_mismatch';
export type SaveReceiptResult = { ok: true } | { ok: false; reason: SaveReceiptReason };
export function confirmIdempotencyKey(previewId: string): string;
export function verifySaveReceipt(input: {
  draft: { preview_id: string; base_version: number; snapshot: { spec: { board_id: string; session_id: string; version: number } } } | null;
  saved: { spec: { board_id: string; session_id: string; version: number } } | null;
  key?: string;
  confirmationUncertain?: boolean;
}): SaveReceiptResult;
export const SAVE_FAILURE_MESSAGES: Readonly<Record<string, string>>;
export function saveFailureMessage(reason: string): string;
