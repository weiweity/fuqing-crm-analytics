export const PAGE_DOCUMENTS_PREFIX: string;
export const PAGE_RESULT_PREFIX: string;
export function refuseLivePort(url: string): string;
export type PageHttpOptions = {
  base: string;
  token: string;
  fetchImpl: (url: string, init?: object) => Promise<{ ok: boolean; status?: number; json(): Promise<unknown> }>;
};
export function pageDocumentsHttpOptions(): PageHttpOptions | null;
export function pageResultHttpOptions(): PageHttpOptions | null;
