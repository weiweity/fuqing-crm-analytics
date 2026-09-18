export type PagePackage = {
  html: string;
  css: string;
  js: string;
  resources: unknown[];
  node_map: unknown[];
};
export function normalizePagePackage(pkg: unknown): PagePackage | null;
export function extractPagePackage(source: unknown): PagePackage | null;
export function nativeGenerateUnavailable(message?: string): Error & { code: 'NATIVE_GENERATE_UNAVAILABLE' };
export function createNativePageGenerate(options?: {
  submitPrompt?: (prompt: string, extras?: object) => Promise<unknown> | unknown;
}): (prompt: string, extras?: object) => Promise<PagePackage>;
