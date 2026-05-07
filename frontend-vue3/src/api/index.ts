import axios from 'axios'
import { AUTH_TOKEN_KEY, AUTH_USER_KEY } from '@/stores/auth'

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

// 请求拦截器：注入登录 token
client.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一错误处理 + 401 自动清理并派发事件（由 main.ts 统一跳转）
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      const isLoginRequest = error.config?.url?.includes('/auth/login')
      const msg = isLoginRequest
        ? (error.response?.data?.detail || '账号或密码错误')
        : '登录已过期，请重新登录'
      if (!isLoginRequest) {
        if (_isRedirecting) {
          return Promise.reject(new Error(msg))
        }
        _isRedirecting = true
        sessionStorage.removeItem(AUTH_TOKEN_KEY)
        sessionStorage.removeItem(AUTH_USER_KEY)
        window.dispatchEvent(new CustomEvent('auth:expired'))
      }
      return Promise.reject(new Error(msg))
    }
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default client
