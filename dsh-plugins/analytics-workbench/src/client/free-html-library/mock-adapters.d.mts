export const IDENTITY: RegExp;
export const BINDING_STATES: readonly string[];
export const OPERATIONS: readonly string[];
export const PREVIEW_STATUS: readonly string[];
export function escapeHtml(value: unknown): string;
export function applyTextToShineNode(html: string, nodeId: string, text: string): string;
export const SAMPLE_PACKAGE: {
  html: string; css: string; js: string; resources: unknown[];
  node_map: { node_id: string; kind: string; selector: string }[];
};
export type LocateResult = {
  ok: boolean; scope?: string; kind?: string; node_id?: string; label?: string;
  error?: Error & { code?: string }; widenToPage?: boolean; requireReselect?: boolean;
};
export type PreviewRecord = {
  preview_id: string; operation: string; status: string; snapshot: typeof SAMPLE_PACKAGE;
  base_package: typeof SAMPLE_PACKAGE; selection: LocateResult & { confirmExpanded?: boolean; affects_shared_css?: boolean };
  expanded_scope: string; shared_impact: string; expires_at_ms: number; idempotency_key: string;
};
export type PageAdapters = {
  kind: string;
  preview: { kind: string; note: string; srcdoc(pkg: { html?: string; css?: string; js?: string } | null): string; pointerEvents(mode: string): 'none' | 'auto' };
  bridge: {
    kind: string; note: string;
    readBinding(page: { binding_state?: string; binding_manifest?: { bindings?: { status?: string }[]; result_refs?: string[] } }): Promise<{
      binding_state: string; partial: boolean; source: string | null; forbidden: string[];
    }>;
    readResult(request: { op?: string }): Promise<Record<string, unknown>>;
  };
  edit: {
    kind: string; note: string;
    locate(pkg: typeof SAMPLE_PACKAGE | { node_map?: typeof SAMPLE_PACKAGE['node_map'] } | null, request: Record<string, unknown>): LocateResult;
    previewPatch(input: { pkg: typeof SAMPLE_PACKAGE; selection: LocateResult; instruction?: string; affectsShared?: boolean; expiresInMs?: number }): PreviewRecord;
    confirmPatch(previewId: string, opts?: { idempotency_key?: string }): PreviewRecord;
    cancelPatch(previewId: string): { status: string; preview_id?: string };
  };
  assets: {
    kind: string; note: string;
    list(): { page_id: string; title: string; version: number; binding_state: string; updated_at: number }[];
    get(pageId: string): FreeHtmlPage | null;
    put(page: FreeHtmlPage): FreeHtmlPage;
  };
  nativeChat: { kind: string; note: string; prompts: unknown[]; submitGeneratePrompt(prompt: string, context?: object): { accepted: boolean; runtime: string; package?: { html: string; css?: string; js?: string } } | Promise<{ accepted: boolean; runtime: string; package?: { html: string; css?: string; js?: string } }>; open(): { reachable: true } };
  samplePackage(): typeof SAMPLE_PACKAGE;
  nextId(prefix: string): string;
};
export type FreeHtmlPage = {
  page_id: string; session_id: string; title: string; version: number; base_version?: number;
  binding_state: string; binding_manifest: { bindings: unknown[]; result_refs: string[] };
  package: typeof SAMPLE_PACKAGE; savedPackage: typeof SAMPLE_PACKAGE; dirty: boolean;
  updated_at: number; history: { version: number; title: string; at: number; package: typeof SAMPLE_PACKAGE }[];
};
export function createMockPageAdapters(opts?: {
  now?: () => number;
  fail?: Record<string, string | boolean>;
  pages?: FreeHtmlPage[];
}): PageAdapters;
