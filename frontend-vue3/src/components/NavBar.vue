<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BrandMark from '@/components/BrandMark.vue'
import { type NavItem, type NavTab } from '@/config/navigations'
import { useNavItems } from '@/composables/useNavItems'
import { useAuthStore } from '@/stores/auth'
import {
  approveLoginRequest,
  getPendingLoginRequests,
  rejectLoginRequest,
  type PendingLoginRequest,
} from '@/api/loginRequest'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const navItems = useNavItems()

const hoverKey = ref<string | null>(null)
const pendingRequests = ref<PendingLoginRequest[]>([])
const showRequestModal = ref(false)
let showTimer: number | null = null
let hideTimer: number | null = null
let pollingTimer: number | null = null
let pollingInFlight = false
let pollingDisposed = false
let idleTimer: number | null = null
let idleDisposed = false

const IDLE_TIMEOUT_MS = 3 * 60 * 1000
const IDLE_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'scroll', 'touchstart'] as const

const activeKey = computed(() => {
  const activeItem = navItems.value.find((item) => {
    if (item.key === route.path) return true
    return item.key === '/category' && route.path.startsWith('/category-detail')
  })
  return activeItem?.key ?? route.path
})

function clearShowTimer() {
  if (showTimer !== null) window.clearTimeout(showTimer)
  showTimer = null
}

function clearHideTimer() {
  if (hideTimer !== null) window.clearTimeout(hideTimer)
  hideTimer = null
}

function openPopover(key: string) {
  clearShowTimer()
  clearHideTimer()
  showTimer = window.setTimeout(() => {
    hoverKey.value = key
    showTimer = null
  }, 150)
}

function scheduleClosePopover() {
  clearShowTimer()
  clearHideTimer()
  hideTimer = window.setTimeout(() => {
    hoverKey.value = null
    hideTimer = null
  }, 150)
}

function keepPopoverOpen() {
  clearShowTimer()
  clearHideTimer()
}

function closePopover() {
  clearShowTimer()
  clearHideTimer()
  hoverKey.value = null
}

function navigateToTab(item: NavItem, tab: NavTab) {
  closePopover()
  router.push({ path: item.key, hash: tab.key })
}

function isPopoverTabActive(item: NavItem, tab: NavTab) {
  return activeKey.value === item.key && route.hash === tab.key
}

function scheduleNextPoll() {
  if (pollingTimer) window.clearTimeout(pollingTimer)
  pollingTimer = null
  if (pollingDisposed || !authStore.isAuthenticated) return
  pollingTimer = window.setTimeout(() => {
    pollingTimer = null
    void pollPendingRequests()
  }, pendingRequests.value.length > 0 ? 5000 : 10000)
}

async function pollPendingRequests() {
  if (pollingDisposed || !authStore.isAuthenticated || pollingInFlight) return
  pollingInFlight = true
  try {
    const response = await getPendingLoginRequests()
    pendingRequests.value = response.pending || []
  } catch {
    pendingRequests.value = []
  } finally {
    pollingInFlight = false
    if (!pollingDisposed && authStore.isAuthenticated) scheduleNextPoll()
  }
}

function handleVisibilityChange() {
  if (!pollingDisposed && !document.hidden && authStore.isAuthenticated) void pollPendingRequests()
}

async function handleApprove(request: PendingLoginRequest) {
  try {
    await approveLoginRequest(request.request_id)
    pendingRequests.value = []
    showRequestModal.value = false
    authStore.clearSession()
    await router.replace('/login')
  } catch (error: any) {
    alert(`同意失败: ${error?.data?.detail || error?.response?.data?.detail || error?.message || '未知错误'}`)
  }
}

async function handleReject(request: PendingLoginRequest) {
  try {
    await rejectLoginRequest(request.request_id)
    pendingRequests.value = pendingRequests.value.filter((item) => item.request_id !== request.request_id)
  } catch (error: any) {
    alert(`拒绝失败: ${error?.data?.detail || error?.response?.data?.detail || error?.message || '未知错误'}`)
  }
}

function resetIdleTimer() {
  if (idleTimer !== null) window.clearTimeout(idleTimer)
  idleTimer = window.setTimeout(() => void handleIdleTimeout(), IDLE_TIMEOUT_MS)
}

async function handleIdleTimeout() {
  if (idleDisposed || !authStore.isAuthenticated) return
  console.info('[idle] 3 分钟无操作，自动登出')
  try {
    await authStore.logout()
  } finally {
    idleDisposed = true
    await router.replace('/login')
  }
}

function registerIdleListeners() {
  for (const eventName of IDLE_EVENTS) document.addEventListener(eventName, resetIdleTimer, { passive: true })
}

function unregisterIdleListeners() {
  for (const eventName of IDLE_EVENTS) document.removeEventListener(eventName, resetIdleTimer)
}

watch(pendingRequests, (requests) => {
  if (requests.length > 0 && !showRequestModal.value) showRequestModal.value = true
})

watch(() => authStore.isAuthenticated, (isAuthenticated) => {
  if (isAuthenticated) {
    idleDisposed = false
    registerIdleListeners()
    resetIdleTimer()
    void pollPendingRequests()
  } else {
    idleDisposed = true
    if (idleTimer !== null) window.clearTimeout(idleTimer)
    idleTimer = null
    unregisterIdleListeners()
  }
})

onMounted(() => {
  pollingDisposed = false
  document.addEventListener('visibilitychange', handleVisibilityChange)
  if (authStore.isAuthenticated) {
    void pollPendingRequests()
    idleDisposed = false
    registerIdleListeners()
    resetIdleTimer()
  }
})

onBeforeUnmount(() => {
  clearShowTimer()
  clearHideTimer()
  pollingDisposed = true
  if (pollingTimer) window.clearTimeout(pollingTimer)
  pollingTimer = null
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  idleDisposed = true
  if (idleTimer !== null) window.clearTimeout(idleTimer)
  idleTimer = null
  unregisterIdleListeners()
})
</script>

<template>
  <header class="navbar-shell">
    <div class="navbar-row">
      <router-link to="/growth-board" class="navbar-brand" aria-label="伸美集团 CRM 增长分析平台首页">
        <BrandMark />
      </router-link>

      <nav class="navbar-main" aria-label="主导航">
        <div class="navbar-tabs">
          <div
            v-for="item in navItems"
            :key="item.key"
            class="navbar-item"
            @mouseenter="openPopover(item.key)"
            @mouseleave="scheduleClosePopover"
            @focusin="openPopover(item.key)"
            @focusout="scheduleClosePopover"
            @keydown.esc.stop="closePopover"
          >
            <router-link
              :to="{ path: item.key }"
              class="navbar-tab"
              :class="{ 'navbar-tab--active': activeKey === item.key }"
              :aria-current="activeKey === item.key ? 'page' : undefined"
              :aria-expanded="hoverKey === item.key"
              @click="closePopover"
            >
              {{ item.label }}<span v-if="item.tabs.length" aria-hidden="true">⌄</span>
            </router-link>

            <Transition name="navbar-popover">
              <div
                v-if="hoverKey === item.key && item.tabs.length"
                class="navbar-popover"
                role="menu"
                @mouseenter="keepPopoverOpen"
                @mouseleave="scheduleClosePopover"
              >
                <button
                  v-for="tab in item.tabs"
                  :key="tab.key"
                  type="button"
                  :class="{ active: isPopoverTabActive(item, tab) }"
                  role="menuitem"
                  @click="navigateToTab(item, tab)"
                >{{ tab.label }}</button>
              </div>
            </Transition>
          </div>
        </div>
      </nav>

      <button
        v-if="authStore.isAuthenticated"
        type="button"
        class="notify-button"
        :class="{ pending: pendingRequests.length > 0 }"
        :aria-label="`${pendingRequests.length} 个待处理申请`"
        @click="showRequestModal = true"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>
        </svg>
        <span v-if="pendingRequests.length">{{ pendingRequests.length }}</span>
      </button>
    </div>
  </header>

  <div v-if="showRequestModal" class="request-modal-overlay" @click.self="showRequestModal = false">
    <section class="request-modal" role="dialog" aria-modal="true" aria-labelledby="request-modal-title">
      <header>
        <div><span>ACCESS CONTROL</span><h2 id="request-modal-title">账号登录申请</h2></div>
        <button type="button" aria-label="关闭" @click="showRequestModal = false">×</button>
      </header>
      <div class="request-list">
        <p v-if="pendingRequests.length === 0" class="request-empty">暂无待处理申请</p>
        <article v-for="request in pendingRequests" :key="request.request_id" class="request-item">
          <div><strong>来自 IP：{{ request.requester_ip }}</strong><small>预计 {{ request.estimated_wait_seconds }} 秒后超时</small></div>
          <div class="request-actions">
            <button type="button" class="approve" @click="handleApprove(request)">同意</button>
            <button type="button" @click="handleReject(request)">拒绝</button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.navbar-shell { position: relative; z-index: 30; border-bottom: var(--sm-dimension-px-1) solid var(--sm-line); color: var(--sm-ink); background: var(--sm-nav); backdrop-filter: var(--sm-blur-nav); -webkit-backdrop-filter: var(--sm-blur-nav); }
.navbar-row { display: flex; width: min(var(--sm-dimension-px-1800), 100%); min-height: var(--sm-dimension-px-64); align-items: center; gap: var(--sm-dimension-px-22); margin: 0 auto; padding: 0 var(--sm-dimension-px-22); }
.navbar-brand { flex: 0 0 auto; color: inherit; text-decoration: none; }
.navbar-main { min-width: 0; flex: 1; overflow: visible; }
.navbar-tabs { display: flex; min-width: max-content; align-items: center; gap: var(--sm-dimension-px-3); }
.navbar-item { position: relative; }
.navbar-tab { display: inline-flex; min-height: var(--sm-dimension-px-36); align-items: center; gap: var(--sm-dimension-px-5); padding: 0 var(--sm-dimension-px-13); border: var(--sm-dimension-px-1) solid transparent; border-radius: var(--sm-radius-pill); color: var(--sm-muted); font-size: var(--sm-dimension-px-12); font-weight: 520; text-decoration: none; white-space: nowrap; transition: color var(--sm-motion-fast), border-color var(--sm-motion-fast), background var(--sm-motion-fast), box-shadow var(--sm-motion-fast); }
.navbar-tab:hover, .navbar-tab:focus-visible { border-color: var(--sm-line); color: var(--sm-ink); background: var(--sm-white-faint); }
.navbar-tab--active { border-color: var(--sm-line); color: var(--sm-signal); background: var(--sm-nav-active); box-shadow: var(--sm-shadow-nav-active); }
.navbar-tab span { color: var(--sm-faint); font-size: var(--sm-dimension-px-10); }
.navbar-popover { position: absolute; top: calc(100% + var(--sm-dimension-px-8)); left: 0; display: grid; min-width: var(--sm-dimension-px-214); gap: var(--sm-dimension-px-4); padding: var(--sm-dimension-px-8); border: var(--sm-dimension-px-1) solid var(--sm-line-strong); border-radius: var(--sm-radius-control); background: var(--sm-glass-strong); box-shadow: var(--sm-shadow-panel); backdrop-filter: var(--sm-blur-nav); }
.navbar-popover button { min-height: var(--sm-dimension-px-37); padding: 0 var(--sm-dimension-px-11); border: var(--sm-dimension-px-1) solid transparent; border-radius: var(--sm-dimension-px-8); color: var(--sm-copy); background: transparent; font-size: var(--sm-dimension-px-11); text-align: left; cursor: pointer; }
.navbar-popover button:hover, .navbar-popover button:focus-visible, .navbar-popover button.active { border-color: var(--sm-line); color: var(--sm-ink); background: var(--sm-purple-soft); }
.notify-button { position: relative; display: grid; width: var(--sm-dimension-px-36); height: var(--sm-dimension-px-36); flex: 0 0 auto; place-items: center; border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: 50%; color: var(--sm-muted); background: var(--sm-white-faint); cursor: pointer; }
.notify-button svg { width: var(--sm-dimension-px-17); height: var(--sm-dimension-px-17); }
.notify-button.pending { color: var(--sm-signal); }
.notify-button > span { position: absolute; top: var(--sm-dimension-px-minus-3); right: var(--sm-dimension-px-minus-3); display: grid; min-width: var(--sm-dimension-px-16); height: var(--sm-dimension-px-16); place-items: center; border-radius: var(--sm-radius-soft); color: var(--sm-on-accent); background: var(--sm-signal); font: 700 var(--sm-dimension-px-8)/1 var(--sm-font-display); }
.request-modal-overlay { position: fixed; z-index: 9999; inset: 0; display: grid; place-items: center; padding: var(--sm-dimension-px-20); background: var(--sm-overlay); backdrop-filter: var(--sm-blur-overlay); }
.request-modal { width: min(var(--sm-dimension-px-500), 100%); overflow: hidden; border: var(--sm-dimension-px-1) solid var(--sm-line-strong); border-radius: var(--sm-radius-panel); color: var(--sm-ink); background: var(--sm-glass-strong); box-shadow: var(--sm-shadow-panel); }
.request-modal > header { display: flex; align-items: center; justify-content: space-between; padding: var(--sm-dimension-px-20) var(--sm-dimension-px-22); border-bottom: var(--sm-dimension-px-1) solid var(--sm-line); }
.request-modal > header span { color: var(--sm-lilac); font: 650 var(--sm-dimension-px-8)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-13); }
.request-modal h2 { margin: var(--sm-dimension-px-5) 0 0; font-size: var(--sm-dimension-px-18); }
.request-modal > header button { width: var(--sm-dimension-px-32); height: var(--sm-dimension-px-32); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: 50%; color: var(--sm-muted); background: transparent; font-size: var(--sm-dimension-px-20); cursor: pointer; }
.request-list { display: grid; max-height: var(--sm-dimension-vh-60); gap: var(--sm-dimension-px-8); overflow-y: auto; padding: var(--sm-dimension-px-16) var(--sm-dimension-px-22) var(--sm-dimension-px-22); }
.request-empty { padding: var(--sm-dimension-px-30) 0; color: var(--sm-faint); text-align: center; }
.request-item { display: flex; align-items: center; justify-content: space-between; gap: var(--sm-dimension-px-15); padding: var(--sm-dimension-px-14); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-radius-soft); background: var(--sm-white-faint); }
.request-item > div:first-child { display: grid; gap: var(--sm-dimension-px-4); }
.request-item strong { color: var(--sm-copy-strong); font-size: var(--sm-dimension-px-12); }
.request-item small { color: var(--sm-faint); font-size: var(--sm-dimension-px-9); }
.request-actions { display: flex; gap: var(--sm-dimension-px-6); }
.request-actions button { min-height: var(--sm-dimension-px-34); padding: 0 var(--sm-dimension-px-12); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-dimension-px-8); color: var(--sm-copy); background: transparent; cursor: pointer; }
.request-actions button.approve { border-color: var(--sm-signal); color: var(--sm-on-accent); background: var(--sm-signal); }
.navbar-popover-enter-active, .navbar-popover-leave-active { transition: opacity .14s ease, transform .14s ease; }
.navbar-popover-enter-from, .navbar-popover-leave-to { opacity: 0; transform: translateY(var(--sm-dimension-px-minus-4)); }

@media (max-width: 900px) {
  .navbar-row { flex-wrap: wrap; gap: var(--sm-dimension-px-12); padding: var(--sm-dimension-px-12); }
  .navbar-main { position: relative; flex-basis: 100%; order: 3; }
  .navbar-tabs { min-width: 0; flex-wrap: wrap; }
  .navbar-item { position: static; }
  .navbar-popover { right: 0; min-width: 0; }
  .notify-button { margin-left: auto; }
  .navbar-tab { padding: 0 var(--sm-dimension-px-8); font-size: var(--sm-dimension-px-11); }
}
</style>
