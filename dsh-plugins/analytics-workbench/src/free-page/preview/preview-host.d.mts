export function mountPreviewHost(root: Element, options?: {
  pageId?: string;
  actorId?: string;
  version?: number;
  savedPackage?: object;
  savedVersion?: number;
  adapter?: { read?: (payload: object) => Promise<unknown>; cancel?: (payload: object) => void };
  budgets?: object;
  cache?: object;
  isolationEvidence?: { cpu_isolation?: string } | null;
  onEvent?: (event: object) => void;
  onError?: (error: object) => void;
  chrome?: boolean;
  frameTestId?: string;
}): {
  loadPackage(pkg: object, version: number): Promise<{ ok: true; instanceId: string; isolation: object } | { ok: false; error: object }>;
  stop(reason?: string): { ok: true };
  restart(): Promise<object>;
  restoreSaved(): Promise<object>;
  rememberSaved(pkg: object, version: number): void;
  getState(): object;
  isolation(): object;
  dispose(): void;
};
