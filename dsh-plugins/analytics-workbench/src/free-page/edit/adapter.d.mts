export function createFreePageEditAdapter(options: {
  store: object;
  now?: () => number;
  ttl_ms?: number;
  ids?: { preview: () => string; key: (kind: string) => string };
}): object;
