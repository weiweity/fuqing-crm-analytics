import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock('@/api/index', () => ({
  default: { post: apiMocks.post },
}))

import {
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  AUTH_IS_ADMIN_KEY,
  useAuthStore,
} from './auth'

describe('auth store session SSOT', () => {
  beforeEach(() => {
    sessionStorage.clear()
    apiMocks.post.mockReset()
    setActivePinia(createPinia())
  })

  it('setSession writes token + username + isAdmin and three sessionStorage keys atomically', () => {
    const store = useAuthStore()
    store.setSession('token-b', 'admin', true)

    expect(store.token).toBe('token-b')
    expect(store.username).toBe('admin')
    expect(store.isAdmin).toBe(true)
    expect(store.isAuthenticated).toBe(true)
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('token-b')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe('admin')
    expect(sessionStorage.getItem(AUTH_IS_ADMIN_KEY)).toBe('true')
  })

  it('setSession with is_admin=false stores literal string "false" (no implicit truthy coercion)', () => {
    const store = useAuthStore()
    store.setSession('token-c', 'fqsw', false)

    expect(store.isAdmin).toBe(false)
    expect(sessionStorage.getItem(AUTH_IS_ADMIN_KEY)).toBe('false')
  })

  it('clearSession clears token + username + isAdmin and three sessionStorage keys atomically', () => {
    const store = useAuthStore()
    store.setSession('token-a', 'admin', true)
    store.clearSession()

    expect(store.token).toBe('')
    expect(store.username).toBe('')
    expect(store.isAdmin).toBe(false)
    expect(store.isAuthenticated).toBe(false)
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBeNull()
    expect(sessionStorage.getItem(AUTH_IS_ADMIN_KEY)).toBeNull()
  })

  it('login uses LoginResponse.is_admin=true and writes three sessionStorage keys', async () => {
    apiMocks.post.mockResolvedValueOnce({
      token: 'login-token',
      username: 'admin',
      is_admin: true,
    })
    const store = useAuthStore()
    await store.login('admin', '123456')

    expect(store.token).toBe('login-token')
    expect(store.username).toBe('admin')
    expect(store.isAdmin).toBe(true)
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('login-token')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe('admin')
    expect(sessionStorage.getItem(AUTH_IS_ADMIN_KEY)).toBe('true')
  })

  it('login uses LoginResponse.is_admin=false for non-admin user', async () => {
    apiMocks.post.mockResolvedValueOnce({
      token: 'login-token-2',
      username: 'fqsw',
      is_admin: false,
    })
    const store = useAuthStore()
    await store.login('fqsw', 'fqsw888')

    expect(store.token).toBe('login-token-2')
    expect(store.username).toBe('fqsw')
    expect(store.isAdmin).toBe(false)
    expect(sessionStorage.getItem(AUTH_IS_ADMIN_KEY)).toBe('false')
  })

  it('setIdentity updates username + isAdmin and two sessionStorage keys without touching token', () => {
    const store = useAuthStore()
    store.setSession('existing-token', 'old-user', false)
    store.setIdentity('new-user', true)

    expect(store.token).toBe('existing-token')
    expect(store.username).toBe('new-user')
    expect(store.isAdmin).toBe(true)
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('existing-token')
    expect(sessionStorage.getItem(AUTH_USER_KEY)).toBe('new-user')
    expect(sessionStorage.getItem(AUTH_IS_ADMIN_KEY)).toBe('true')
  })

  it('rehydrates isAdmin=true from sessionStorage on store init', () => {
    sessionStorage.setItem(AUTH_TOKEN_KEY, 'pre-token')
    sessionStorage.setItem(AUTH_USER_KEY, 'pre-user')
    sessionStorage.setItem(AUTH_IS_ADMIN_KEY, 'true')

    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.isAdmin).toBe(true)
    expect(store.isAuthenticated).toBe(true)
  })

  it('rehydrates isAdmin=false from sessionStorage on store init (no implicit truthy coercion)', () => {
    sessionStorage.setItem(AUTH_TOKEN_KEY, 'pre-token')
    sessionStorage.setItem(AUTH_USER_KEY, 'pre-user')
    sessionStorage.setItem(AUTH_IS_ADMIN_KEY, 'false')

    setActivePinia(createPinia())
    const store = useAuthStore()
    expect(store.isAdmin).toBe(false)
    expect(store.isAuthenticated).toBe(true)
  })
})
