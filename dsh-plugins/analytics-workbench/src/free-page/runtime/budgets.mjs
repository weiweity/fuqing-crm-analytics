/** Initial host-side budgets. Not measured from real AI samples; not a generation whitelist. */

export const DEFAULT_BUDGETS = Object.freeze({
  maxHtmlBytes: 400_000,
  maxCssBytes: 200_000,
  maxJsBytes: 400_000,
  maxSourceBytes: 800_000,
  maxResourceBytes: 2_000_000,
  maxResourcesTotalBytes: 8_000_000,
  maxResourceCount: 64,
  maxNodeMap: 2000,
  maxInstances: 4,
  initTimeoutMs: 5_000,
  unresponsiveTimeoutMs: 8_000,
  handshakeTimeoutMs: 3_000,
});

export function mergeBudgets(override) {
  if (!override || typeof override !== 'object') return { ...DEFAULT_BUDGETS };
  const next = { ...DEFAULT_BUDGETS };
  for (const key of Object.keys(DEFAULT_BUDGETS)) {
    if (Number.isSafeInteger(override[key]) && override[key] > 0) next[key] = override[key];
  }
  return next;
}
