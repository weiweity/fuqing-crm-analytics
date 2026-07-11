import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import { useAuthStore, AUTH_TOKEN_KEY, AUTH_USER_KEY } from '@/stores/auth'
import './styles/tailwind.css'
import './styles/globals.css'

// === 启动前校验 token 有效性（防止后端重启后旧 token 残留导致白屏）===
async function bootstrap() {
  const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
  if (token) {
    try {
      const res = await fetch('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        // token 已失效（后端重启或过期），立即跳转登录页，不再挂载应用
        sessionStorage.removeItem(AUTH_TOKEN_KEY)
        sessionStorage.removeItem(AUTH_USER_KEY)
        router.replace('/login')
      }
    } catch {
      // 网络异常时不清除 token，避免离线误判
    }
  }

  const app = createApp(App)

  app.use(createPinia())
  app.use(router)
  app.use(VueQueryPlugin, {
    queryClientConfig: {
      defaultOptions: {
        queries: {
          // Fix P1-2: Limit retry to 1 with fixed 1s delay instead of exponential backoff
          retry: 1,
          retryDelay: 1000,
          staleTime: 60_000,
          refetchOnWindowFocus: false,
        },
      },
    },
  })

  // 监听认证过期事件，统一清理状态并跳转
  window.addEventListener('auth:expired', () => {
    const authStore = useAuthStore()
    authStore.clearSession()
    if (router.currentRoute.value.path !== '/login') {
      router.replace('/login')
    }
  })

  // 定期续期 token（每30分钟），防止长时间操作后 token 过期
  setInterval(async () => {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) return
    try {
      const res = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        // token 已过期，触发过期事件
        sessionStorage.removeItem(AUTH_TOKEN_KEY)
        sessionStorage.removeItem(AUTH_USER_KEY)
        window.dispatchEvent(new CustomEvent('auth:expired'))
      }
    } catch {
      // 网络异常时不做处理，避免离线误判
    }
  }, 30 * 60 * 1000) // 30分钟

  // L4.85.6 方案 A 治本: user 7/11 报 "Cmd+Q 退出浏览器后, 变成需要申请登录"
  // 真根因: A Cmd+Q → frontend JS 全停 → backend ACTIVE_TOKENS 仍有 A token → B login 409
  // 修复: beforeunload 钩子 + navigator.sendBeacon POST /api/v1/auth/logout?token=xxx
  //       (sendBeacon 是异步非阻塞, 浏览器关掉也能发出去; 不能设 Authorization header, 所以 token via query param)
  // 配套: 方案 D background task evict idle token > 60s 兜底 (backend/services/auth_token_evictor.py)
  // 跟 L4.85.4 idle timer 1:1 stable 永久规则化沿用 (user 主动 idle / Cmd+Q / 网络断 全覆盖)
  window.addEventListener('beforeunload', () => {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) return
    // sendBeacon 是浏览器关掉前最后一刻还能发的请求, 跟 L4.85.4 logout API 1:1 stable 兼容
    try {
      navigator.sendBeacon(`/api/v1/auth/logout?token=${encodeURIComponent(token)}`)
    } catch {
      // sendBeacon 失败 (移动 Safari 不稳) → background task D 方案兜底
    }
  })

  // 等待初始路由解析完成（含导航守卫重定向）后再挂载，防止未登录时闪一下看板布局
  await router.isReady()

  app.mount('#app')

  // 标记认证状态已就绪
  const authStore = useAuthStore()
  authStore.isReady = true
}

bootstrap()
