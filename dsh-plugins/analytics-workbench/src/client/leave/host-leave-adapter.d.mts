import type { LeaveIntent, LeaveState } from './leave-coordinator.mjs';
export const OWNED_ENTRIES: readonly ['library', 'conversation', 'panel', 'session', 'close'];
/**
 * The host panel setter. `selectPanel` takes the host's branded panel id, so the
 * parameter is left generic rather than narrowed to a literal: narrowing it here
 * would reject the real `ctx.layout` at the call site.
 */
export type HostPanelLayout = { selectPanel?(panelId: never): void };
export type HostLeaveAdapter = {
  request(entry: string, intent?: LeaveIntent): Promise<'navigated' | 'prompt' | 'busy' | 'stayed'>;
  observe(panelId: string | null, previous?: string | null): Promise<'navigated' | 'prompt' | 'busy' | 'stayed'>;
  useLayout(controller: HostPanelLayout): boolean;
  perform(intent: LeaveIntent): Promise<void>;
  seamAvailable(): boolean;
  dispose(): void;
};
export function createHostLeaveAdapter(options: {
  coordinator: {
    request(intent: LeaveIntent & { external?: boolean; previous?: string | null }): Promise<'navigated' | 'prompt' | 'busy' | 'stayed'>;
    stay(): void;
    getSnapshot(): LeaveState;
  };
  layout?: HostPanelLayout;
  onPanelChange?(listener: (panelId: string | null) => void): (() => void) | void;
  readPanelId?(): string | null;
}): HostLeaveAdapter;
