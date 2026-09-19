export type CockpitFileKind = 'html' | 'spreadsheet' | 'pdf';

export type CockpitProduct = {
  id: string;
  kind: string;
  title: string;
  path?: string;
  sessionId?: string;
  size?: number;
  page_id?: string;
  board_id?: string;
  subtitle?: string;
  source?: string;
};

export type WorkspaceScanResult = {
  status: 'ready' | 'empty' | 'error' | 'no-session';
  sessionId: string | null;
  files: CockpitProduct[];
  truncated: boolean;
  error: string | null;
  lists: number;
};

export type WorkspaceReadResult = {
  status: 'ok' | 'empty' | 'error' | 'rejected';
  text: string | null;
  reason?: string;
  eof: boolean;
};

export const DEFAULT_WORKSPACE_SCAN_MAX: 80;
export const DEFAULT_WORKSPACE_DIR_DEPTH: 2;
export const DEFAULT_WORKSPACE_LIST_CAP: 40;

export function classifyWorkspaceFile(path: string): CockpitFileKind | null;
export function isSafeWorkspaceRelPath(path: string): boolean;
export function workspaceRelFromEventPath(path: string | null | undefined): string | null;
export function unwrapRemoteValue(result: unknown): Record<string, unknown> | null;
export function fileResourceAddress(sessionId: string, path: string): string;
export function joinWorkspacePath(dir: string, name: string): string;
export function workspaceEntriesToProducts(
  sessionId: string,
  listing: { path?: string; entries?: Array<{ name?: string; type?: string; size?: number }> } | null | undefined,
  options?: { depth?: number; dirDepth?: number },
): CockpitProduct[];
export function cockpitProductIdentity(item: Record<string, unknown> | null | undefined): string;
export function mergeCockpitProducts(input?: {
  files?: readonly Record<string, unknown>[];
  boards?: readonly { board_id?: string; title?: string; version?: number }[];
  pages?: readonly { page_id?: string; title?: string; version?: number }[];
}): CockpitProduct[];
export function collectWorkspaceScan(
  listDir: (sessionId: string, path: string, signal?: AbortSignal) => Promise<unknown>,
  sessionId: string,
  options?: { signal?: AbortSignal; max?: number; dirDepth?: number; listCap?: number },
): Promise<WorkspaceScanResult>;
export function collectWorkspaceProducts(
  listDir: (sessionId: string, path: string, signal?: AbortSignal) => Promise<unknown>,
  sessionId: string,
  options?: { signal?: AbortSignal; max?: number; dirDepth?: number; listCap?: number },
): Promise<CockpitProduct[]>;
export function readWorkspaceFileText(
  read: (sessionId: string, path: string, range?: { offset?: number; limit?: number }, signal?: AbortSignal) => Promise<unknown>,
  sessionId: string,
  path: string,
  options?: { signal?: AbortSignal; limit?: number; maxPages?: number },
): Promise<WorkspaceReadResult>;
