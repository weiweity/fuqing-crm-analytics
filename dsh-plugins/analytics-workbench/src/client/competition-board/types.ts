import type { components } from '../../competition-c0-contract.generated.d.ts';

export type CompetitionBoardSpec = components['schemas']['CompetitionBoardSpec'];
export type CompetitionPatchRequest = components['schemas']['CompetitionPatchRequest'];
export type CompetitionBoardBatchRequest = components['schemas']['CompetitionBoardBatchRequest'];
export type CompetitionBoardBatchReceipt = components['schemas']['CompetitionBoardBatchReceipt'];
export type CompetitionResultRef = components['schemas']['CompetitionResultRef'];
export type CompetitionErrorDetail = components['schemas']['CompetitionErrorDetail'];
export type EndorsedResultRef = components['schemas']['EndorsedResultRef'];
export type PatchIntent = components['schemas']['PatchIntent'];
export type BoardLayoutMode = components['schemas']['BoardLayoutMode'];
export type LayoutBox = { x: number; y: number; w: number; h: number };

export type Principal = { actor_id: string; permission_scope: string };

export type TransportResult<T> = { ok: true; status: number; body: T } | {
  ok: false; status: number; body: { error: CompetitionErrorDetail };
};

export type BoardTransport = {
  kind: 'fixture' | 'http';
  listEndorseableResults(principal: Principal): Promise<TransportResult<CompetitionResultRef[]>>;
  previewBatch(principal: Principal, payload: CompetitionBoardBatchRequest): Promise<TransportResult<{
    board?: CompetitionBoardSpec | null;
    receipt?: CompetitionBoardBatchReceipt | null;
  }>>;
  applyBatch(principal: Principal, payload: CompetitionBoardBatchRequest, headers?: Record<string, string>):
    Promise<TransportResult<{ board?: CompetitionBoardSpec | null; receipt?: CompetitionBoardBatchReceipt | null }>>;
  previewPatch(principal: Principal, payload: CompetitionPatchRequest, headers?: Record<string, string>):
    Promise<TransportResult<CompetitionBoardSpec>>;
  applyPatch(principal: Principal, payload: CompetitionPatchRequest, headers?: Record<string, string>):
    Promise<TransportResult<CompetitionBoardSpec>>;
  undo(principal: Principal, payload: CompetitionPatchRequest, headers?: Record<string, string>):
    Promise<TransportResult<CompetitionBoardSpec>>;
  loadBoard(boardId: string): Promise<TransportResult<CompetitionBoardSpec>>;
  listBoards?(): Promise<TransportResult<CompetitionBoardSpec[]>>;
  discardPreview?(): void;
  setScenario?(name: string): void;
};

export type EditScope = {
  board_id: string;
  block_id: string | null;
  base_version: number;
  attempt_id?: string;
};

export type SelectedEditEvent = {
  board_id: string;
  block_id: string | null;
  base_version: number;
  intent: PatchIntent;
  instruction: string;
};

export type RegisteredPlugin = 'TABLE' | 'BAR' | 'LINE' | 'METRIC' | 'EVIDENCE';

export type BlockView = {
  block_id: string;
  title: string;
  plugin: RegisteredPlugin;
  layout: LayoutBox;
  result: CompetitionResultRef | null;
  rows: { label: string; value: string }[];
  summary: string;
};

export type CreateRoot = (el: HTMLElement) => { render(node: unknown): void; unmount(): void };

export type BoardMountProps = {
  transport?: BoardTransport;
  modelAvailable?: boolean;
  principal?: Principal;
  createRoot?: CreateRoot;
  onSelectedEdit?: (event: SelectedEditEvent) => void;
  onDispose?: () => void;
};
