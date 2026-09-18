/**
 * Production page store. Imported from the plugin host (index.tsx), not from
 * FreeHtmlLibraryApp, so DOM tests that bundle the App stay on mock adapters.
 */
import { createLivePageAdapters } from './live-adapters.mjs';
import { createFreeHtmlLibraryStore } from './store.mjs';

export function createHostPageStore(options = {}) {
  return createFreeHtmlLibraryStore({
    adapters: createLivePageAdapters({
      now: options.now,
      actorId: options.actorId,
      documentsHttp: options.documentsHttp ?? null,
    }),
    now: options.now,
    viewportWidth: options.viewportWidth,
  });
}
