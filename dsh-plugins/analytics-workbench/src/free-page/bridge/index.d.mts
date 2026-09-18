export const PROTOCOL: 'free-page-bridge/v1';
export const SCHEMA_VERSION: 'free-page/v1';
export const TRANSPORT: 'MessageChannel';
export const DATA_SCOPE: 'free-page-result-fixture';
export const BINDING_STATES: readonly ['UNBOUND_SAMPLE', 'BOUND_VERIFIED', 'BOUND_STALE'];
export const HANDSHAKE_FIELDS: readonly ['protocol', 'instance_id', 'page_id', 'version', 'nonce'];
export const PAGE_TO_HOST_OPS: readonly ['data.read', 'data.cancel'];
export const HOST_TO_PAGE_EVENTS: readonly ['data.chunk', 'data.end', 'data.error', 'binding.state'];
export const FORBIDDEN_OPS: readonly ['sql', 'save', 'http.fetch', 'credential.read'];
export const SUMMARY_FIELDS: readonly ['unit', 'time_range', 'queried_at', 'source', 'row_count'];
export const ERRORS: Readonly<Record<string, number>>;
export const MESSAGES: Readonly<Record<string, string>>;

export type BindingState = 'UNBOUND_SAMPLE' | 'BOUND_VERIFIED' | 'BOUND_STALE';
export type BridgeEventName = 'data.chunk' | 'data.end' | 'data.error' | 'binding.state';

export interface BridgeActor {
  actor_id: string;
  capabilities: Set<string>;
  data_scopes: Set<string>;
}

export interface BindingManifest {
  result_refs: string[];
  bindings: Array<Record<string, unknown>>;
}

export interface SyntheticAccess {
  putSnapshot(payload: Record<string, unknown>): unknown;
  read(request: Record<string, unknown>, options?: { actor?: BridgeActor; manifest?: BindingManifest }): Promise<Record<string, unknown>>;
  cancel(request: Record<string, unknown>, actor?: BridgeActor): { request_id: string; status: string };
  revoke(resultRef: string, actor?: BridgeActor): void;
  bindingState(actor?: BridgeActor, manifest?: BindingManifest): Record<string, unknown>;
  authorize(actor: BridgeActor, request: Record<string, unknown>, manifest: BindingManifest): unknown;
}

export function defaultSyntheticSnapshot(overrides?: Record<string, unknown>): Record<string, unknown>;
export const UNBOUND_MANIFEST: BindingManifest;
export const BOUND_MANIFEST: BindingManifest;
export function createSyntheticAccess(options?: { clock?: () => number; actor?: BridgeActor }): SyntheticAccess;

export interface BridgeHost {
  handshake(message: Record<string, unknown>): Record<string, unknown>;
  dispatch(message: Record<string, unknown>): Promise<Array<Record<string, unknown>>>;
  attach(port: MessagePort): () => void;
  expireInstance(): void;
  readonly session: Record<string, unknown> | null;
  readonly events: readonly BridgeEventName[];
}

export function createBridgeHost(options: {
  access: SyntheticAccess;
  actor: BridgeActor;
  pageId: string;
  version: number;
  manifest: BindingManifest;
}): BridgeHost;

export function createPageBridge(port: MessagePort, handshakeMessage: Record<string, unknown>): {
  handshake: Promise<Record<string, unknown>>;
  onEvent(listener: (message: Record<string, unknown>) => void): () => void;
  read(request: Record<string, unknown>): Promise<{ chunks: Array<Record<string, unknown>>; end: Record<string, unknown> }>;
  cancel(requestId: string): void;
};
