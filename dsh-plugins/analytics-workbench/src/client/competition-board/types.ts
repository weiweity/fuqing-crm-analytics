import type { components } from '../../competition-c0-contract.generated.d.ts';
import type { components as chartComponents } from '../../competition-chart-contract.generated.d.ts';
import type { components as computedComponents } from '../../competition-computed-contract.generated.d.ts';

export type CompetitionBoardSpec = components['schemas']['CompetitionBoardSpec'] & {
  blocks?: Array<{
    block_id: string;
    result_id?: string;
    result?: CompetitionResultRef;
    layout: LayoutBox;
    display_overrides?: { title?: string };
    source_status?: string;
    plugin?: RegisteredPlugin;
  }>;
};
export type CompetitionPatchRequest = components['schemas']['CompetitionPatchRequest'];
export type CompetitionChartPatchRequest = chartComponents['schemas']['CompetitionChartPatchRequest'];
export type BoardPatchRequest = CompetitionPatchRequest | CompetitionChartPatchRequest;
export type CompetitionBoardBatchRequest = components['schemas']['CompetitionBoardBatchRequest'];
export type CompetitionBoardBatchReceipt = components['schemas']['CompetitionBoardBatchReceipt'];
export type CompetitionResultRef = components['schemas']['CompetitionResultRef'] | computedComponents['schemas']['CompetitionComputedResult'];
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
  previewPatch(principal: Principal, payload: BoardPatchRequest, headers?: Record<string, string>):
    Promise<TransportResult<CompetitionBoardSpec>>;
  applyPatch(principal: Principal, payload: BoardPatchRequest, headers?: Record<string, string>):
    Promise<TransportResult<CompetitionBoardSpec>>;
  undo(principal: Principal, payload: BoardPatchRequest, headers?: Record<string, string>):
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

export type RegisteredPlugin = CompetitionChartPatchRequest['chart_type'];

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
  initialPanel?: 'endorse' | 'board';
  transport?: BoardTransport;
  modelAvailable?: boolean;
  principal?: Principal;
  createRoot?: CreateRoot;
  onSelectedEdit?: (event: SelectedEditEvent) => void;
  onDispose?: () => void;
};
