export type ComponentRule = { type: string; enum?: string[]; default?: unknown; minimum?: number; maximum?: number; maxLength?: number };
export type ComponentDefinition = { kind: string; name: string; data_shape: string; requires_result?: boolean; allows_result?: boolean; min_size: { w: number; h: number }; properties: Record<string, ComponentRule> };
export const COMPONENT_CATALOG: { components: ComponentDefinition[]; common_properties: Record<string, ComponentRule> };
export const LIBRARY_KINDS: readonly string[];
export function componentDefinition(kind: string): ComponentDefinition | null;
export function parseComponentProps(kind: string, props: unknown, options?: { defaults?: boolean }): { ok: true; value: Record<string, unknown> } | { ok: false; error: { code: string; message: string } };
