export const GRID: { cols: number; minW: number; minH: number; maxH: number; maxY: number; pointerStep: number };
export type LayoutBox = { x: number; y: number; w: number; h: number };
export function clampLayout(layout: LayoutBox, patch?: Partial<LayoutBox>): LayoutBox;
export const LAYOUT_ACTIONS: Record<string, { label: string; shortcut: string; patch: Record<string, number> }>;
export function applyLayoutAction(layout: LayoutBox, action: string): LayoutBox;
export function matchLayoutKeyboard(event: { key: string; altKey: boolean; shiftKey: boolean; ctrlKey?: boolean; metaKey?: boolean }): string | null;
export function pointerDelta(startClient: number, nowClient: number, origin: LayoutBox, axis: 'x' | 'y' | 'w' | 'h'): LayoutBox;
