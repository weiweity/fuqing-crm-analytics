import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/audience' },
  {
    path: '/login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/audience',
    component: () => import('@/views/AudienceView.vue'),
    meta: { title: '人群看板', requiresAuth: true },
  },
  {
    path: '/category',
    component: () => import('@/views/CategoryView.vue'),
    meta: { title: '品类看板', requiresAuth: true },
  },
  {
    path: '/category-detail/:categoryId',
    component: () => import('@/views/CategoryDetailView.vue'),
    meta: { title: '品类详情', requiresAuth: true },
  },
  {
    path: '/customer-health',
    component: () => import('@/views/CustomerHealthView.vue'),
    meta: { title: '老客分析', requiresAuth: true },
  },
  {
    path: '/churn',
    component: () => import('@/views/ChurnView.vue'),
    meta: { title: '流失分析', requiresAuth: true },
  },
  {
    path: '/geo',
    component: () => import('@/views/GeoView.vue'),
    meta: { title: '地域分析', requiresAuth: true },
  },
  {
    path: '/market-focus',
    component: () => import('@/views/MarketFocusView.vue'),
    meta: { title: '市场对焦', requiresAuth: true },
  },
  {
    path: '/sampling',
    component: () => import('@/views/SamplingView.vue'),
    meta: { title: '派样看板', requiresAuth: true },
  },
  {
    path: '/breakdown',
    component: () => import('@/views/BreakdownView.vue'),
    meta: { title: '一键拆解', requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 导航守卫：未登录 → 登录页；已登录访问登录页 → 看板首页
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // 认证状态未就绪时，先放行，由 App.vue 的 loading 态兜底
  if (!authStore.isReady) {
    next()
    return
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    const redirect = to.query.redirect as string
    next(redirect || '/audience')
  } else {
    next()
  }
})

router.afterEach((to) => {
  document.title = (to.meta.title as string) || '芙清CRM'
})

export default router
