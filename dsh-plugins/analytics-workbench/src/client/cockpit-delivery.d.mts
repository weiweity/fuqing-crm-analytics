import type { CockpitProduct, WorkspaceReadResult, WorkspaceScanResult } from './cockpit-products.mjs';

export type DeliverySessionSource = {
  status: 'captured' | 'no-session';
  sessionId: string | null;
  reason: string | null;
};

export type DeliverySnapshot = {
  status: 'no-session' | 'loading' | 'empty' | 'ready' | 'error';
  sessionId: string | null;
  files: CockpitProduct[];
  truncated: boolean;
  error: string | null;
  epoch: number;
  refreshMode: 'manual' | 'event+manual';
  lists?: number;
};

export type DeliveryHostCapabilities = {
  canListWorkspace: boolean;
  canReadWorkspace: boolean;
  canSubscribeWorkspaceChanges: boolean;
  canSubscribePresented: boolean;
  hasWorkspaceChangesService: boolean;
  hasUiConversation: boolean;
  refreshMode: 'manual' | 'event+manual';
  workspaceChangesReason: string | null;
  presentedReason: string | null;
};

export function captureDeliverySessionSource(
  list: { ids?: string[] } | null | undefined,
  compositionSessionId?: string,
): DeliverySessionSource;

export function inspectDeliveryHostCapabilities(host: unknown): DeliveryHostCapabilities;

export function tryAttachWorkspaceChangeRefresh(
  host: { subscribeWorkspaceChanges?: (listener: (payload: unknown) => void) => (() => void) | void },
  onChange: (payload: unknown) => void,
): { attached: boolean; reason: string | null; unsubscribe(): void };

export function ingestWorkspaceEventFiles(
  sessionId: string,
  files: Array<string | { path?: string }> | null | undefined,
  options?: { existing?: CockpitProduct[] },
): CockpitProduct[];

export function createCockpitDelivery(adapters?: {
  listDir?: (sessionId: string, path: string, signal?: AbortSignal) => Promise<unknown>;
  read?: (sessionId: string, path: string, range?: { offset?: number; limit?: number }, signal?: AbortSignal) => Promise<unknown>;
  max?: number;
  dirDepth?: number;
}): {
  captureSource(list: { ids?: string[] } | null | undefined, compositionSessionId?: string): DeliverySessionSource;
  setSessionId(id: string | null | undefined): DeliverySessionSource;
  getSessionId(): string | null;
  getSnapshot(): DeliverySnapshot;
  subscribe(listener: (snapshot: DeliverySnapshot) => void): () => void;
  inspectHost(host: unknown): DeliveryHostCapabilities;
  attachHostEvents(host: unknown): { attached: boolean; reason: string | null };
  refresh(options?: { sessionId?: string; signal?: AbortSignal }): Promise<DeliverySnapshot>;
  readFile(path: string, options?: { sessionId?: string; signal?: AbortSignal }): Promise<WorkspaceReadResult>;
  ingestEventFiles(files: Array<string | { path?: string }>, options?: { sessionId?: string; existing?: CockpitProduct[] }): CockpitProduct[];
  dispose(): void;
};

export type { WorkspaceScanResult };
