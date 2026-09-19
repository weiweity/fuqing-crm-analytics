import type { components } from '../board-spec-contract.generated.js';
export type LibrarySnapshot = components['schemas']['BoardSnapshot'];
export type LibraryPreview = components['schemas']['BoardPreview'];
export type LibraryEditContext = components['schemas']['BoardEditContext'];
export type LibraryState = { busy: boolean; message: string; confirmationUncertain: boolean;
  boards: { board_id: string; title: string; version: number; session_id: string }[];
  saved: LibrarySnapshot | null; preview: LibraryPreview | null;
  layoutDraft: LibrarySnapshot | null;
  editContext: LibraryEditContext | null;
  incoming: { kind: 'board' | 'preview' | 'edit'; id: string; contextId?: string } | null;
  fieldDraft: { title?: string; kind?: string; source_result_id?: string; props?: Record<string, unknown> } | null;
  history: components['schemas']['BoardRevision'][];
};
/** The outcome of a leave-driven save or discard; a failure keeps the draft. */
export type LeaveReceipt = { ok: true } | { ok: false; reason?: string; message?: string };
export type LibraryBoardClient = {
  getSnapshot(): LibraryState;
  setFieldDraft(changes: LibraryState['fieldDraft']): void;
  subscribe(listener: () => void): () => void;
  dispose(): void;
  /** Dirty-draft predicate (D42): only real unsaved work blocks leaving. */
  hasUnsavedChanges(): boolean;
  /** Selection/focus context (D42): never a reason to block leaving. */
  hasActiveEditContext(): boolean;
  unsavedReasons(): ('layout_changed' | 'pending_patch_preview' | 'confirmationUncertain' | 'field_draft')[];
  /** Advance navigation ownership for a leave intent (D43). */
  beginNavigation(kind: string): { epoch: number; kind: string; signal: AbortSignal; abort(): void };
  navigationEpoch(): number;
  refresh(): Promise<void>;
  openBoard(id: string): Promise<void>;
  openPreview(id: string, contextId?: string): Promise<void>;
  beginEdit(blockId: string): Promise<void>;
  /** Establish edit context only. Does not call editNative or send a chat message. */
  selectComponent(blockId: string): Promise<void>;
  describeSelectedPatch(): {
    supported: boolean;
    reason?: string;
    kind?: string | null;
    title?: boolean;
    props?: string[];
    source_result_id?: boolean;
    source_result_options?: string[];
    layout?: string;
    requires_result?: boolean;
  };
  previewBlockPatch(changes: {
    title?: string;
    props?: Record<string, unknown>;
    kind?: string;
    source_result_id?: string;
  }): Promise<void>;
  resumeEdit(): Promise<void>;
  inspectEdit(): Promise<void>;
  keepDraft(): void;
  /** Save the pending draft for a leave; never throws. */
  saveForLeave(): Promise<LeaveReceipt>;
  /** Drop the draft without navigating; never throws. */
  discardDraft(): Promise<LeaveReceipt>;
  discardAndNavigate(): Promise<void>;
  cancel(): Promise<void>;
  confirm(): Promise<void>;
  inspectConfirmation(): Promise<void>;
  loadHistory(): Promise<void>;
  rollback(version: number): Promise<void>;
  rollbackPrevious(): Promise<void>;
  beginLayout(): void;
  updateLayout(blockId: string, box: { x: number; y: number; w: number; h: number }): void;
  previewLayout(): Promise<void>;
};
export function createLibraryBoardClient(call: (channel: string, operation: string, payload: unknown, signal?: AbortSignal) => Promise<unknown>,
  options?: { editNative?(context: LibraryEditContext): Promise<void> }): LibraryBoardClient;
