export type SpecResult = { ok: true; value: object } | { ok: false; error: { code: string; message: string } };
export function parseBoardSpec(raw: unknown): SpecResult;
export function parsePatchBlock(raw: unknown): SpecResult;
export function parseRollback(raw: unknown): SpecResult;
export function applyPatch(spec: object, patch: object): SpecResult;
