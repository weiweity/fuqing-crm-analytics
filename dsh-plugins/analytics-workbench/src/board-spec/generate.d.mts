export type SpecResult = { ok: true; value: { spec: object; facts: object | null } } | { ok: false; error: { code: string; message: string } };
export function specFromGsvFacts(facts: unknown, meta?: { board_id?: string; session_id?: string }):
  { ok: true; value: object } | { ok: false; error: { code: string; message: string } };
export function generateBoard(spec: unknown, facts?: object | null): SpecResult;
export function applyGenerate(draft: { boardSpec?: object | null; boardFacts?: object | null; boardError?: string }, spec: unknown, facts?: object | null): SpecResult;
export function summarizeGenerate(spec: unknown): string;
export function specWithLink(spec: unknown, link: object): { ok: true; value: object } | { ok: false; error: { code: string; message: string } };
