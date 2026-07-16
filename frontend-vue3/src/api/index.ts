import axios from 'axios'
import { AUTH_TOKEN_KEY } from '@/stores/auth'

const client = axios.create({
  baseURL: '/api',
  timeout: 30_000,
  paramsSerializer: (params) => {
    const searchParams = new URLSearchParams()
    for (const key in params) {
      if (params[key] == null) continue
      if (Array.isArray(params[key])) {
        params[key].forEach((v: any) => searchParams.append(key, String(v)))
      } else {
        searchParams.append(key, String(params[key]))
      }
    }
    return searchParams.toString()
  },
})

// 全局锁：防止并发 401 触发多次跳转
let _isRedirecting = false

// 防止并发 refresh
let _refreshPromise: Promise<boolean> | null = null

export type ApiError = Error & {
  status?: number
  headers?: Record<string, string>
  data?: unknown
}

export function isCredentialAuthRequest(url?: string): boolean {
  const path = (url || '').split('?', 1)[0].replace(/\/+$/, '')
  return path.endsWith('/v1/auth/login') || path.endsWith('/v1/auth/login-request')
}

function toApiError(error: any, fallbackMessage = '请求失败'): ApiError {
  const wrapped = new Error(
    error.response?.data?.detail || error.message || fallbackMessage,
  ) as ApiError
  wrapped.status = error.response?.status
  wrapped.headers = error.response?.headers
  wrapped.data = error.response?.data
  return wrapped
}

async function _tryRefreshToken(): Promise<boolean> {
  if (_refreshPromise) return _refreshPromise
  _refreshPromise = (async () => {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) return false
    try {
      const res = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return false
      return true
    } catch {
      return false
    } finally {
      _refreshPromise = null
    }
  })()
  return _refreshPromise
}

// 请求拦截器：注入登录 token + 重置过期锁
client.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
    // 有有效 token 时重置 401 跳转锁（登录成功后的请求会触发这里）
    _isRedirecting = false
  }
  return config
})

// 响应拦截器：统一错误处理 + 401 先尝试 refresh 再跳转
client.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    // 取消异常原样返回 (per Codex Stage 3 review [P2-1]):
    // axios.isCancel 检测 CanceledError (signal.abort() 触发),
    // 不包装成普通 Error (否则会丢失 name/code/identity, 还会触发 auth:expired).
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }
    if (error.response?.status === 401) {
      const requestUrl = error.config?.url || ''
      const isLoginRequest = isCredentialAuthRequest(requestUrl)
      const isRefreshRequest = requestUrl.split('?', 1)[0].replace(/\/+$/, '').endsWith('/v1/auth/refresh')
      const msg = isLoginRequest
        ? (error.response?.data?.detail || '账号或密码错误')
        : '登录已过期，请重新登录'

      if (isLoginRequest || isRefreshRequest) {
        // 登录失败或 refresh 失败，直接拒绝
        return Promise.reject(toApiError(error, msg))
      }

      // 非登录请求遇到 401，先尝试 refresh
      const refreshed = await _tryRefreshToken()
      if (refreshed) {
        // refresh 成功，用新 token 重试原请求
        const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
        if (token && error.config) {
          error.config.headers.Authorization = `Bearer ${token}`
          return client.request(error.config)
        }
      }

      // refresh 失败或无法重试，触发过期流程
      if (_isRedirecting) {
        return Promise.reject(toApiError(error, msg))
      }
      _isRedirecting = true
      // auth store 是认证状态唯一写入口；事件监听器会同步清理 Pinia + sessionStorage。
      window.dispatchEvent(new CustomEvent('auth:expired'))
      return Promise.reject(toApiError(error, msg))
    }
    return Promise.reject(toApiError(error))
  }
)

export default client
