import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import { useAuthStore, AUTH_TOKEN_KEY, AUTH_USER_KEY, AUTH_IS_ADMIN_KEY } from '@/stores/auth'
import './styles/tailwind.css'
import './styles/globals.css'

// === /auth/me bootstrap: Sprint 3A 身份状态 ===
type BootstrapUserInfo = { username: string; is_admin: boolean }
let bootstrapUser: BootstrapUserInfo | null = null

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
        sessionStorage.removeItem(AUTH_IS_ADMIN_KEY)
        router.replace('/login')
      } else {
        // 解析 JSON 并暂存 username + is_admin (在 createApp + use(pinia) 之后调用 setIdentity)
        const data = (await res.json()) as BootstrapUserInfo
        bootstrapUser = { username: data.username, is_admin: !!data.is_admin }
      }
    } catch {
      // 网络异常时不清除 token，避免离线误判
    }
  }

  const app = createApp(App)

  app.use(createPinia())

  // 创建 app + pinia 后调用 authStore.setIdentity(username, is_admin)
  if (bootstrapUser) {
    const authStore = useAuthStore()
    authStore.setIdentity(bootstrapUser.username, bootstrapUser.is_admin)
    bootstrapUser = null  // 释放临时变量
  }

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
        // token 已过期，触发过期事件 (auth:expired 监听器走 authStore.clearSession() 清理三件套)
        sessionStorage.removeItem(AUTH_TOKEN_KEY)
        sessionStorage.removeItem(AUTH_USER_KEY)
        sessionStorage.removeItem(AUTH_IS_ADMIN_KEY)
        window.dispatchEvent(new CustomEvent('auth:expired'))
      }
    } catch {
      // 网络异常时不做处理，避免离线误判
    }
  }, 30 * 60 * 1000) // 30分钟

  // L4.85.6 方案 A: Cmd+Q / 关页前踢会话，避免 B 端 login 409
  // 安全: token 禁止出现在 URL/query（access log / 浏览器历史泄露）。
  // 优先 sendBeacon + JSON body；失败则 fetch keepalive + Authorization（仍不走 query）。
  // 配套: 方案 D background task evict idle token > 60s (backend/services/auth_token_evictor.py)
  window.addEventListener('beforeunload', () => {
    // Playwright page.goto 会触发 beforeunload；若此时 beacon logout，
    // 下一页 bootstrap /auth/me 401 → 清 token → 永远停在登录页（e2e 全红真因 2026-07-19）。
    // L4.85.6 Cmd+Q 用例单独测 beacon，不设 fq_crm_e2e。
    if (sessionStorage.getItem('fq_crm_e2e') === '1') return
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) return
    const url = '/api/v1/auth/logout'
    const body = JSON.stringify({ token })
    try {
      // sendBeacon 不能设 Authorization header → token 放 JSON body（Content-Type: application/json）
      const blob = new Blob([body], { type: 'application/json' })
      const ok = navigator.sendBeacon(url, blob)
      if (!ok) throw new Error('sendBeacon returned false')
    } catch {
      // 兜底: fetch keepalive（可带 Bearer，仍禁止 query token）
      try {
        void fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body,
          keepalive: true,
        })
      } catch {
        // 网络/浏览器限制 → background task D 方案兜底
      }
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
