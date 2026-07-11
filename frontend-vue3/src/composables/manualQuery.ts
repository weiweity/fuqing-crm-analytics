type BooleanRef = { value: boolean }
type ManualRefetch = (options?: { cancelRefetch?: boolean }) => unknown

/**
 * Start or refresh one manually-triggered heavy query without multiplying it.
 *
 * The first click only enables TanStack Query; calling refetch in the same tick
 * would start a second request. Later clicks are ignored while a request is in
 * flight and use cancelRefetch=false so the current backend query is never
 * abandoned in favour of another duplicate.
 */
export function triggerManualQuery(
  enabled: BooleanRef,
  fetching: BooleanRef,
  refetch: ManualRefetch,
): boolean {
  if (fetching.value) return false
  if (!enabled.value) {
    enabled.value = true
    return true
  }
  void refetch({ cancelRefetch: false })
  return true
}
