export type BoardHttpResult = { ok: true; value: unknown } | { ok: false; error: { code: string; message: string; details: { status: number } } };
export function boardServerConfigured(): boolean;
export function boardServerRequest(path: string, options?: { method?: string; body?: unknown; key?: string; signal?: AbortSignal }): Promise<BoardHttpResult>;
