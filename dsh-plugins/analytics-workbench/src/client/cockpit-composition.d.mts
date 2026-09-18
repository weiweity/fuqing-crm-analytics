import type { ISessions } from '@deepseek-ai/dsh-api-session-controller/client';
export const COMPOSITION_PIN: string;
export const CHAT_MIN: 400;
export const CANVAS_MIN: 560;
export const SPLIT_GAP: 8;
export const COMPACT_FRAME_MAX: number;
export type CompositionState = { open: boolean; fallback: boolean; showChat: boolean; narrowView: string;
  width: number; sessionId: string | null; sessionAvailable: boolean };
export type CockpitComposition = {
  subscribe(listener: () => void): () => void;
  getSnapshot(): CompositionState;
  open(sessionId?: string | null): void;
  bindSession(sessionId: string | null): void;
  revealChat(): void; toggleChat(): void; showCanvas(): void; setWidth(width: number): void;
  toggleSidebar(): void; close(): void; fallback(): void; dispose(): void;
};
export function compositionGeometry(width: number, preferred?: number, showChat?: boolean, narrowView?: string): {
  mode: string; canvas: number; chat: number;
};
export function createCockpitComposition(options: {
  sessions: Pick<ISessions, 'list' | 'retain'>;
  layout: { selectPanel(id: never): void; toggleSidebar?(): void };
}): CockpitComposition;
export function nativeCompositionTarget(anchor: HTMLElement): { frame: HTMLElement; center: HTMLElement; native: HTMLElement } | null;
export function leaseNativeComposition(native: HTMLElement): { update(width: number, hidden: boolean): void; dispose(): void };
export function leaseCompactNavigation(frame: HTMLElement, center: HTMLElement): { update(width: number): boolean; dispose(): void };
