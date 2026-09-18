import type { FreeHtmlLibraryStore } from './store.d.mts';
import type { PageHttpOptions } from './page-http.d.mts';
import type { PagePackage } from './native-generate.d.mts';

export function createHostPageStore(options?: {
  now?: () => number;
  actorId?: string;
  viewportWidth?: number;
  documentsHttp?: PageHttpOptions | null;
  resultHttp?: PageHttpOptions | null;
  nativeGenerate?: (prompt: string, extras?: object) => Promise<PagePackage> | PagePackage;
}): FreeHtmlLibraryStore;
