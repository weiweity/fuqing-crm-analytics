export type CancelKind = 'edit' | 'layout' | 'preview';
export type CancelReceiptResult = { ok: true; value: unknown } | { ok: false; reason: 'missing_receipt' | 'mismatched_receipt' };
export function verifyCancelReceipt(reply: unknown, idField: string, expectedId: string): CancelReceiptResult;
export function cancelledPatch(kind: CancelKind): Record<string, unknown>;
export const CANCEL_MESSAGES: Readonly<{ edit: string; layout: string; preview: string; retained: string }>;
export function cancelDraft(options: {
  kind: CancelKind; id: string | null; idField: string | null;
  request(operation: string, payload: unknown): Promise<unknown>;
  emit(patch: Record<string, unknown>): void; message?: string;
}): Promise<unknown>;
export function cancelTarget(state: { editContext?: { edit_context_id: string } | null; layoutDraft?: unknown; preview?: { preview_id: string } | null; confirmationUncertain?: boolean } | null | undefined,
  options?: { forLeave?: boolean }): { kind: CancelKind; id: string | null; idField: string | null } | null;
