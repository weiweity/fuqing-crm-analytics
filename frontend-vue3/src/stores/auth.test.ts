import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock('@/api/index', () => ({
  default: { post: apiMocks.post },
}))

import {
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  useAuthStore,
} from './auth'

describe('auth store session SSOT', () => {
  beforeEach(() => {
    sessionStorage.clear()
    apiMocks.post.mockReset()
    setActivePinia(createPinia())
  })

  it('setSession updates Pinia and sessionStorage atomically', () => {
    const store = useAuthStore()
    store.setSession('token-b', 'admin')

    expect(store.token).toBe('token-b')
    expect(store.username).toBe('admin')
    expect(store.isAuthenticated).toBe(true)
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('token-b')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe('admin')
  })

  it('clearSession clears Pinia and sessionStorage atomically', () => {
    const store = useAuthStore()
    store.setSession('token-a', 'admin')
    store.clearSession()

    expect(store.token).toBe('')
    expect(store.username).toBe('')
    expect(store.isAuthenticated).toBe(false)
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBeNull()
  })
})
