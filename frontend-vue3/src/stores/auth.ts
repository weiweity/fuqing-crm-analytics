import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import client from '@/api/index'

export const AUTH_TOKEN_KEY = 'fq_crm_auth_token'
export const AUTH_USER_KEY = 'fq_crm_auth_user'
export const AUTH_IS_ADMIN_KEY = 'fq_crm_is_admin'

interface LoginResponse {
  token: string
  username: string
  is_admin: boolean
}

export const useAuthStore = defineStore('auth', () => {
  // === State ===
  const token = ref(sessionStorage.getItem(AUTH_TOKEN_KEY) || '')
  const username = ref(sessionStorage.getItem(AUTH_USER_KEY) || '')
  const isAdmin = ref(sessionStorage.getItem(AUTH_IS_ADMIN_KEY) === 'true')
  const isLoading = ref(false)
  const isReady = ref(false)

  // === Getters ===
  const isAuthenticated = computed(() => !!token.value)

  // === Actions ===
  function setIdentity(nextUsername: string, nextIsAdmin: boolean) {
    username.value = nextUsername
    isAdmin.value = nextIsAdmin
    sessionStorage.setItem(AUTH_USER_KEY, nextUsername)
    sessionStorage.setItem(AUTH_IS_ADMIN_KEY, String(nextIsAdmin))
  }

  function setSession(nextToken: string, nextUsername: string, nextIsAdmin: boolean) {
    token.value = nextToken
    sessionStorage.setItem(AUTH_TOKEN_KEY, nextToken)
    setIdentity(nextUsername, nextIsAdmin)
  }

  function clearSession() {
    token.value = ''
    username.value = ''
    isAdmin.value = false
    sessionStorage.removeItem(AUTH_TOKEN_KEY)
    sessionStorage.removeItem(AUTH_USER_KEY)
    sessionStorage.removeItem(AUTH_IS_ADMIN_KEY)
  }

  async function login(user: string, pwd: string) {
    isLoading.value = true
    try {
      const res = await client.post<LoginResponse>('/v1/auth/login', {
        username: user,
        password: pwd,
      }) as unknown as LoginResponse
      setSession(res.token, res.username, res.is_admin)
    } finally {
      isLoading.value = false
    }
  }

  async function logout() {
    try {
      await client.post('/v1/auth/logout')
    } catch {
      // 忽略注销接口异常（token 已过期时后端也可能返回 401）
    } finally {
      clearSession()
    }
  }

  return {
    token,
    username,
    isAdmin,
    isAuthenticated,
    isLoading,
    isReady,
    setIdentity,
    setSession,
    clearSession,
    login,
    logout,
  }
})
