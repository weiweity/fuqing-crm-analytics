import type { FreeHtmlLibraryStore } from './store.d.mts';

export function createHostPageStore(options?: {
  now?: () => number;
  actorId?: string;
  viewportWidth?: number;
}): FreeHtmlLibraryStore;
