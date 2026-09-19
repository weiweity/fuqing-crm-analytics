export function escapeReplacementText(value: string | null | undefined): string;
export function boundNodeIds(manifest: { bindings?: Array<{ node_id?: string }> } | null | undefined): Set<string>;

export function previewLiteralText(input: {
  pkg: { html: string; css?: string; js?: string; resources?: unknown[]; node_map?: unknown[] };
  selection: Record<string, unknown>;
  replacementText?: string;
  instruction?: string;
  page_id?: string;
  session_id?: string;
  base_version?: number;
  preview_id?: string;
  idempotency_key?: string;
  now_ms?: number;
  binding_manifest?: { bindings?: Array<{ node_id?: string }>; result_refs?: string[] } | null;
}): { ok: true; package: Record<string, unknown>; located: unknown; preview: unknown; replacementText: string }
  | { ok: false; error: { code: string; message: string; [key: string]: unknown } };

export function submitHtmlPatchPreview(
  documents: { patchPreview(input: Record<string, unknown>): Promise<{ ok: boolean; body?: any; reason?: string }> },
  input: { page_id: string; base_version: number; package: Record<string, unknown>; title?: string },
): Promise<{ ok: true; preview_id?: string; body?: unknown } | { ok: false; error: { code: string; message: string; [key: string]: unknown } }>;
