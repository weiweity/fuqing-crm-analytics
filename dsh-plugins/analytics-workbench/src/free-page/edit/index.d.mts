export function hasActiveEditContext(state: object | null | undefined): boolean;
export function isDirty(state: object | null | undefined): boolean;
export function createEditController(options: {
  store: object;
  now?: () => number;
  ttl_ms?: number;
  ids?: { preview: () => string; key: (kind: string) => string };
}): object;
export function makeIds(): { preview: () => string; key: (kind: string) => string };
export const ERRORS: Record<string, { code: string; http: number }>;
