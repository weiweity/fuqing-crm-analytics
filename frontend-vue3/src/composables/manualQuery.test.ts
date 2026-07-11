import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { triggerManualQuery } from './manualQuery'

describe('triggerManualQuery', () => {
  it('first click only enables the query instead of double-fetching', () => {
    const enabled = ref(false)
    const fetching = ref(false)
    const refetch = vi.fn()

    expect(triggerManualQuery(enabled, fetching, refetch)).toBe(true)
    expect(enabled.value).toBe(true)
    expect(refetch).not.toHaveBeenCalled()
  })

  it('ignores repeated clicks while the backend query is in flight', () => {
    const enabled = ref(true)
    const fetching = ref(true)
    const refetch = vi.fn()

    for (let i = 0; i < 5; i += 1) {
      expect(triggerManualQuery(enabled, fetching, refetch)).toBe(false)
    }
    expect(refetch).not.toHaveBeenCalled()
  })

  it('refreshes once without cancelling an existing request', () => {
    const enabled = ref(true)
    const fetching = ref(false)
    const refetch = vi.fn()

    expect(triggerManualQuery(enabled, fetching, refetch)).toBe(true)
    expect(refetch).toHaveBeenCalledTimes(1)
    expect(refetch).toHaveBeenCalledWith({ cancelRefetch: false })
  })
})
