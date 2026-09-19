import type { NavigationTicket } from '../navigation/navigation-epoch.mjs';
import type { UnsavedReason } from './dirty-predicate.mjs';
export type LeaveChoice = 'save_and_leave' | 'discard' | 'stay';
export type LeaveIntent = { kind: string; id?: string | null; sessionId?: string | null; performLocal?(): void | Promise<void> };
export type PendingLeaveIntent = LeaveIntent & { epoch: number; performed: boolean };
export type LeaveState = {
  status: 'idle' | 'prompting' | 'saving' | 'discarding';
  intent: PendingLeaveIntent | null;
  reasons: UnsavedReason[];
  message: string;
};
export const LEAVE_CHOICES: readonly LeaveChoice[];
export type LeaveCoordinator = {
  getSnapshot(): LeaveState;
  subscribe(listener: () => void): () => void;
  request(intent: LeaveIntent): Promise<'navigated' | 'prompt' | 'busy' | 'stayed'>;
  choose(choice: LeaveChoice): Promise<'navigated' | 'stayed'>;
  stay(): void;
  dispose(): void;
};
export function createLeaveCoordinator(deps: {
  snapshot(): { layoutDraft?: unknown; saved?: unknown; preview?: unknown; confirmationUncertain?: boolean; editContext?: unknown } | null | undefined;
  beginEpoch(kind: string): NavigationTicket;
  save(): Promise<{ ok: boolean; reason?: string }>;
  discard(): Promise<{ ok: boolean; message?: string }>;
  navigate(intent: PendingLeaveIntent, context: { epoch: number }): void | Promise<void>;
  onLeaveRequest?(intent: PendingLeaveIntent, reasons: UnsavedReason[]): void;
}): LeaveCoordinator;
