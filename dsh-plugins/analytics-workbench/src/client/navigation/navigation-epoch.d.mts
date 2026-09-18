export const EPOCH_DISCARDED_OPERATIONS: readonly ['get', 'list', 'preview'];
export const EPOCH_PRESERVED_OPERATIONS: readonly ['confirm', 'cancel', 'cancel_edit'];
export function isEpochDiscarded(operation: string): boolean;
export class SupersededRead extends Error { readonly superseded: true; readonly epoch: number; }
export function isSupersededRead(error: unknown): boolean;
export type NavigationTicket = { readonly epoch: number; readonly kind: string; readonly signal: AbortSignal; abort(): void };
export type NavigationEpoch = {
  readonly current: number;
  begin(kind?: string): NavigationTicket;
  ticket(): { readonly epoch: number; readonly kind: string; readonly signal: AbortSignal } | null;
  isCurrent(epoch: number): boolean;
  settle(epoch: number): void;
  dispose(): void;
};
export function createNavigationEpoch(): NavigationEpoch;
