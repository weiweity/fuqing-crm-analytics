import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import client from '@/api/index'

export const AUTH_TOKEN_KEY = 'fq_crm_auth_token'
export const AUTH_USER_KEY = 'fq_crm_auth_user'

interface LoginResponse {
  token: string
  username: string
}

export const useAuthStore = defineStore('auth', () => {
  // === State ===
  const token = ref(sessionStorage.getItem(AUTH_TOKEN_KEY) || '')
  const username = ref(sessionStorage.getItem(AUTH_USER_KEY) || '')
  const isLoading = ref(false)
  const isReady = ref(false)

  // === Getters ===
  const isAuthenticated = computed(() => !!token.value)

  // === Actions ===
  async function login(user: string, pwd: string) {
    isLoading.value = true
    try {
      const res = await client.post<LoginResponse>('/v1/auth/login', {
        username: user,
        password: pwd,
      })
      token.value = res.token
      username.value = res.username
      sessionStorage.setItem(AUTH_TOKEN_KEY, res.token)
      sessionStorage.setItem(AUTH_USER_KEY, res.username)
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
      token.value = ''
      username.value = ''
      sessionStorage.removeItem(AUTH_TOKEN_KEY)
      sessionStorage.removeItem(AUTH_USER_KEY)
    }
  }

  return { token, username, isAuthenticated, isLoading, isReady, login, logout }
})
