import type { ProcessContent, ProcessNode, TimelineEvent, TimelineContent } from './component-view.mjs';
export function validCalendarDate(value: unknown): boolean;
export function structuredContentError(kind: string, props: Record<string, unknown>): string | null;
export function timelineGeometry(events: TimelineEvent[]): TimelineContent;
export function processGeometry(content: ProcessContent): {
  width: number; height: number;
  nodes: (ProcessNode & { number: number; x: number; y: number; w: number; h: number })[];
  edges: { from: string; to: string; label: string; number: number; side: string; lane: number; x: number; y: number; path: string }[];
};
