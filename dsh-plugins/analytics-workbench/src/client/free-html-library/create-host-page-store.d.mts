import type { FreeHtmlLibraryStore } from './store.d.mts';

export function createHostPageStore(options?: {
  now?: () => number;
  actorId?: string;
  viewportWidth?: number;
  documentsHttp?: { base: string; token?: string; fetchImpl: (url: string, init?: object) => Promise<{ ok: boolean; status?: number; json(): Promise<unknown> }> } | null;
}): FreeHtmlLibraryStore;
