export const COCKPIT_CSS: string;
export const COPY: Readonly<Record<string, string>>;
type Input = { dashboard?: unknown; list?: unknown[] | null; error?: { status: number; code: string; message: string } | null; sessionId?: string | null; modelAvailable?: boolean; selectedCardId?: string | null };
type KeyboardBinding = { action: string; key: string; altKey: boolean; shiftKey: boolean; shortcut: string; label: string };
type Base = { heading: string; sessionId: string | null; modelAvailable: boolean; keyboard: Record<'add' | 'copy' | 'remove', KeyboardBinding>; preview?: boolean; version?: number; http: string };
type Card = { kind: 'error'; card_id: string | null; message: string; affected: false } | {
  kind: 'ok'; card_id: string; title: string; badge: string; plugin: string; selected: boolean; affected: boolean;
  layout: { x: number; y: number; w: number; h: number }; condition: string; totals: string;
  empty: { code: string | null; text: string }; evidence: string; localFilterNote: string | null;
};
export type CockpitViewModel = Base & (
  { kind: 'error' | 'empty' | 'empty-board'; message: string } |
  { kind: 'list'; items: { dashboard_id: string; title: string; version: number; summary: string }[] } |
  { kind: 'board'; previewHint: string | null; cards: Card[]; synthetic: string }
);
export function buildCockpitView(input?: Input): CockpitViewModel;

