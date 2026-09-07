export const COPY: Readonly<Record<string, string>>;
type Input = { analysis?: unknown; list?: unknown[] | null; error?: { status: number; code: string; message: string } | null; runStatus?: string | null; saveState?: 'idle' | 'saved' | 'disabled'; sessionId?: string | null; modelAvailable?: boolean };
type Base = { heading: string; sessionId: string | null; modelAvailable: boolean; noSession?: string; http?: string };
type EmptyReason = { code: string | null; text: string };
export type SavedAnalysisViewModel = Base & (
  { kind: 'error' | 'empty'; message: string } |
  { kind: 'list'; items: { analysis_id: string; title: string; version: number; badge: string; summary: string }[] } |
  { kind: 'detail'; title: string; badge: string; version: number; condition: string; totals: string; empty: EmptyReason; evidence: string; refreshCandidate: { run_id: string; evidence_digest: string } | null; snapshotRunId: string; saveState: 'idle' | 'saved'; joinHint: string; synthetic: string } |
  { kind: 'save-panel'; saveState: 'idle' | 'saved'; saveHint: string; canSave: boolean }
);
export function buildSavedAnalysisView(input?: Input): SavedAnalysisViewModel;

