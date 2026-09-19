export type TextNode = { node_id: string; kind: string; mapping: string; mapping_token: string; version_hash: string; text: string; tag: string };
export function editableTextNodes(pkg: any, manifest?: any): TextNode[];
export function selectionSrcdoc(pkg: any, options: { channel: string; pageId: string; version: number; nodes?: TextNode[]; selected?: string | null; editing?: boolean }): string;
export function acceptSelection(event: MessageEvent, context: { source: Window | null; channel: string; pageId: string; version: number; nodes: TextNode[] }): TextNode | null | undefined;
