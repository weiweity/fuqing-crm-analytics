import axios from 'axios'

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

// P0 fix: 不再自动注入 API Key。写操作需从环境变量 VITE_HEALTH_API_KEY 显式传递。

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default client
