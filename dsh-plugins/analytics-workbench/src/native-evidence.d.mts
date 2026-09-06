import type { SessionEvent } from '@deepseek-ai/dsh-session';
export interface NativeBinding { run_id: string; attempt_id: string; session_id: string; request_id: string }
export interface NativeSummary {
  received: boolean; discarded: boolean; targetTurn: number | undefined; currentRequestId: string | undefined;
  reason: { kind: string; reason?: { kind: string } } | undefined;
  ambiguous: boolean; successful_call_ids: string[];
}
export function requestIdOf(message: unknown): string | undefined;
export function requestForStep(events: readonly SessionEvent[], messages: readonly unknown[], turn: number): string | undefined;
export function requestForTool(events: readonly SessionEvent[], callId: string): string | undefined;
export function summarizeRequest(events: readonly SessionEvent[], requestId: string): NativeSummary;
export function evidenceFor(intent: NativeBinding, summary: Partial<NativeSummary>, executionExited: boolean): NativeBinding & {
  execution_exited: boolean; outcome: string; successful_call_ids: string[] | undefined;
};
