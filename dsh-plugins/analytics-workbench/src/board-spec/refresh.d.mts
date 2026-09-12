export type SpecResult = { ok: true; value: Record<string, object> } | { ok: false; error: { code: string; message: string } };
export function refreshFacts(spec: unknown, catalog: object | null): SpecResult;
export function refreshFactsFromTransport(spec: unknown, transport?: { fetchImpl?: typeof fetch; path?: string; catalog?: object | null }): Promise<SpecResult>;
