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
};

export function classifyWorkspaceFile(path: string): CockpitFileKind | null;
export function fileResourceAddress(sessionId: string, path: string): string;
export function joinWorkspacePath(dir: string, name: string): string;
export function workspaceEntriesToProducts(
  sessionId: string,
  listing: { path?: string; entries?: Array<{ name?: string; type?: string; size?: number }> } | null | undefined,
  options?: { depth?: number },
): CockpitProduct[];
export function mergeCockpitProducts(input?: {
  files?: readonly Record<string, unknown>[];
  boards?: readonly { board_id?: string; title?: string; version?: number }[];
  pages?: readonly { page_id?: string; title?: string; version?: number }[];
}): CockpitProduct[];
export function collectWorkspaceProducts(
  listDir: (sessionId: string, path: string, signal?: AbortSignal) => Promise<unknown>,
  sessionId: string,
  options?: { signal?: AbortSignal; max?: number },
): Promise<CockpitProduct[]>;
