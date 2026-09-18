import type { LeaveChoice, LeaveIntent, LeaveState } from './leave-coordinator.mjs';
export const OWNED_ENTRIES: readonly ['library', 'conversation', 'panel', 'session', 'close'];
export function createHostLeaveAdapter(options: {
  coordinator: {
    request(intent: LeaveIntent & { external?: boolean; previous?: string | null }): Promise<'navigated' | 'prompt' | 'busy' | 'stayed'>;
    stay(): void;
    getSnapshot(): LeaveState;
  };
  layout?: { selectPanel?(id: 'cockpit' | null): void };
  onPanelChange?(listener: (panelId: string | null) => void): (() => void) | void;
  readPanelId?(): string | null;
}): {
  request(entry: string, intent?: LeaveIntent): Promise<'navigated' | 'prompt' | 'busy' | 'stayed'>;
  useLayout(controller: { selectPanel?(id: 'cockpit' | null): void }): boolean;
  perform(intent: LeaveIntent): Promise<void>;
  seamAvailable(): boolean;
  dispose(): void;
};
