export const SCHEMA_VERSION: 'free-page-source-index/v1';
export const IDENTITY_PATTERN: RegExp;
export const MAPPING_STALE: { code: 'MAPPING_STALE'; http: 409 };

export type NodeKind = 'static_element' | 'dynamic_region';
export type HtmlRange = {
  start: number;
  inner_start: number;
  inner_end: number;
  end: number;
  inner_text: string;
  outer_text: string;
};
export type IndexedNode = {
  node_id: string;
  kind: NodeKind;
  selector: string;
  tag: string;
  html_range: HtmlRange;
  mapping_token: string;
  unique_selector: boolean;
  css_rules: ReadonlyArray<{ selector: string; body: string; start: number; end: number; text: string }>;
  js_ranges: ReadonlyArray<{ start: number; end: number; needle: string }>;
};
export type SourceIndex = {
  schema_version: 'free-page-source-index/v1';
  version_hash: string;
  nodes: { readonly [nodeId: string]: IndexedNode };
  duplicates: readonly string[];
  untrusted_markers: readonly string[];
  missing_from_dom: readonly string[];
  html: string;
  css: string;
  js: string;
};
export type Selection =
  | { kind: 'static_element'; node_id: string; mapping?: 'valid' | 'stale' | 'forged'; mapping_token?: string; version_hash?: string }
  | { kind: 'dynamic_region'; node_id: string; mapping?: 'valid' | 'stale' | 'forged'; mapping_token?: string; version_hash?: string }
  | { kind: 'whole_page'; user_switched?: boolean };

export function pageIdentity(value: unknown): boolean;
export function buildSourceIndex(pagePackage: object): SourceIndex;
export function rebuildSourceIndex(pagePackage: object): SourceIndex;
export function locateSelection(index: SourceIndex, selection: Selection): object;
export function isSelectorUniqueToNode(selector: string, node_id: string): boolean;
