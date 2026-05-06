import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/audience' },
  {
    path: '/audience',
    component: () => import('@/views/AudienceView.vue'),
    meta: { title: '人群看板' },
  },
  {
    path: '/category',
    component: () => import('@/views/CategoryView.vue'),
    meta: { title: '品类看板' },
  },
  {
    path: '/category-detail/:categoryId',
    component: () => import('@/views/CategoryDetailView.vue'),
    meta: { title: '品类详情' },
  },
  {
    path: '/customer-health',
    component: () => import('@/views/CustomerHealthView.vue'),
    meta: { title: '老客分析' },
  },
  {
    path: '/churn',
    component: () => import('@/views/ChurnView.vue'),
    meta: { title: '流失分析' },
  },
  {
    path: '/geo',
    component: () => import('@/views/GeoView.vue'),
    meta: { title: '地域分析' },
  },
  {
    path: '/market-focus',
    component: () => import('@/views/MarketFocusView.vue'),
    meta: { title: '市场对焦' },
  },
  {
    path: '/sampling',
    component: () => import('@/views/SamplingView.vue'),
    meta: { title: '派样看板' },
  },
  {
    path: '/breakdown',
    component: () => import('@/views/BreakdownView.vue'),
    meta: { title: '一键拆解' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = (to.meta.title as string) || '芙清CRM'
})

export default router
