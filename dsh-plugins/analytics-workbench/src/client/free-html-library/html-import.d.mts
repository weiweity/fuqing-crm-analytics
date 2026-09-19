export const DEFAULT_IMPORT_RESOURCE_MAX: 16;
export const DEFAULT_IMPORT_RESOURCE_BYTES: number;

export type HtmlImportError = {
  code: string;
  message: string;
  status?: number;
  recoverable?: boolean;
  missing?: Array<{ path?: string; url?: string; reason: string }>;
  unsupported?: Array<{ path?: string; url?: string; reason: string }>;
};

export type ConvertedHtmlPackage = {
  ok: true;
  package: {
    html: string;
    css: string;
    js: string;
    resources: unknown[];
    node_map: Array<{ node_id: string; kind: string; selector: string }>;
  };
  origin: { session_id: string; path: string };
  binding_manifest: { bindings: unknown[]; result_refs: unknown[] };
  binding_state: 'UNBOUND_SAMPLE';
  missing: unknown[];
  unsupported: unknown[];
};

export function resolveImportResourcePath(fromPath: string, href: string): string | null;

export function convertWorkspaceHtml(input: {
  html: string;
  path: string;
  sessionId: string;
  readResource?: (rel: string) => Promise<{ bytes?: Uint8Array; text?: string; content_type?: string } | null>;
  maxResources?: number;
  maxResourceBytes?: number;
}): Promise<ConvertedHtmlPackage | { ok: false; error: HtmlImportError }>;

export function createHtmlImporter(options: {
  documents: {
    generatePreview(draft: Record<string, unknown>): Promise<{ ok: boolean; body?: any; reason?: string }>;
    confirmPreview(previewId: string, idempotencyKey: string): Promise<{ ok: boolean; body?: any; reason?: string }>;
    cancelPreview(previewId: string): Promise<{ ok: boolean; body?: any; reason?: string }>;
    pullPage?(pageId: string): Promise<{ ok: boolean; page_id?: string; reason?: string }>;
  };
}): {
  convert: typeof convertWorkspaceHtml;
  createCandidate(input: Parameters<typeof convertWorkspaceHtml>[0] & { title?: string }): Promise<any>;
  confirm(previewId: string, idempotencyKey: string): Promise<any>;
  cancel(previewId: string): Promise<any>;
  reopen(pageId: string): Promise<any>;
};
