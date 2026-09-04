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
      <router-link to="/growth-board" class="navbar-brand" aria-label="伸美 AI 增长董事会首页">
        <BrandMark compact />
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
.navbar-shell { position: relative; z-index: 30; border-bottom: 1px solid var(--sm-line); color: var(--sm-ink); background: rgba(9,5,13,.9); backdrop-filter: blur(24px) saturate(130%); }
.navbar-row { display: flex; width: min(1800px, 100%); min-height: 56px; align-items: center; gap: 22px; margin: 0 auto; padding: 0 22px; }
.navbar-brand { flex: 0 0 auto; color: inherit; text-decoration: none; }
.navbar-main { min-width: 0; flex: 1; overflow: hidden; }
.navbar-tabs { display: flex; min-width: max-content; align-items: center; gap: 3px; }
.navbar-item { position: relative; }
.navbar-tab { display: inline-flex; min-height: 55px; align-items: center; gap: 5px; padding: 0 10px; border-bottom: 1px solid transparent; color: var(--sm-muted); font-size: 12px; font-weight: 520; text-decoration: none; white-space: nowrap; transition: color .16s ease, background .16s ease; }
.navbar-tab:hover, .navbar-tab:focus-visible { color: var(--sm-ink); background: rgba(255,255,255,.025); }
.navbar-tab--active { border-bottom-color: var(--sm-signal); color: var(--sm-ink); }
.navbar-tab span { color: var(--sm-faint); font-size: 10px; }
.navbar-popover { position: absolute; top: calc(100% + 8px); left: 0; display: grid; min-width: 214px; gap: 4px; padding: 8px; border: 1px solid var(--sm-line-strong); border-radius: 14px; background: rgba(24,14,31,.96); box-shadow: 0 20px 54px rgba(0,0,0,.42), inset 0 1px rgba(255,255,255,.06); backdrop-filter: blur(24px); }
.navbar-popover button { min-height: 37px; padding: 0 11px; border: 1px solid transparent; border-radius: 8px; color: var(--sm-copy); background: transparent; font-size: 11px; text-align: left; cursor: pointer; }
.navbar-popover button:hover, .navbar-popover button:focus-visible, .navbar-popover button.active { border-color: var(--sm-line); color: var(--sm-ink); background: rgba(128,93,157,.12); }
.notify-button { position: relative; display: grid; width: 36px; height: 36px; flex: 0 0 auto; place-items: center; border: 1px solid var(--sm-line); border-radius: 50%; color: var(--sm-muted); background: rgba(255,255,255,.025); cursor: pointer; }
.notify-button svg { width: 17px; height: 17px; }
.notify-button.pending { color: var(--sm-signal); }
.notify-button > span { position: absolute; top: -3px; right: -3px; display: grid; min-width: 16px; height: 16px; place-items: center; border-radius: 8px; color: #201426; background: var(--sm-signal); font: 700 8px/1 var(--sm-font-mono); }
.request-modal-overlay { position: fixed; z-index: 9999; inset: 0; display: grid; place-items: center; padding: 20px; background: rgba(5,2,8,.72); backdrop-filter: blur(16px); }
.request-modal { width: min(500px, 100%); overflow: hidden; border: 1px solid var(--sm-line-strong); border-radius: 18px; color: var(--sm-ink); background: rgba(27,15,35,.96); box-shadow: 0 30px 90px rgba(0,0,0,.48), inset 0 1px rgba(255,255,255,.06); }
.request-modal > header { display: flex; align-items: center; justify-content: space-between; padding: 20px 22px; border-bottom: 1px solid var(--sm-line); }
.request-modal > header span { color: var(--sm-lilac); font: 650 8px/1 var(--sm-font-mono); letter-spacing: .13em; }
.request-modal h2 { margin: 5px 0 0; font-size: 18px; }
.request-modal > header button { width: 32px; height: 32px; border: 1px solid var(--sm-line); border-radius: 50%; color: var(--sm-muted); background: transparent; font-size: 20px; cursor: pointer; }
.request-list { display: grid; max-height: 60vh; gap: 8px; overflow-y: auto; padding: 16px 22px 22px; }
.request-empty { padding: 30px 0; color: var(--sm-faint); text-align: center; }
.request-item { display: flex; align-items: center; justify-content: space-between; gap: 15px; padding: 14px; border: 1px solid var(--sm-line); border-radius: 10px; background: rgba(255,255,255,.025); }
.request-item > div:first-child { display: grid; gap: 4px; }
.request-item strong { color: var(--sm-copy-strong); font-size: 12px; }
.request-item small { color: var(--sm-faint); font-size: 9px; }
.request-actions { display: flex; gap: 6px; }
.request-actions button { min-height: 34px; padding: 0 12px; border: 1px solid var(--sm-line); border-radius: 8px; color: var(--sm-copy); background: transparent; cursor: pointer; }
.request-actions button.approve { border-color: var(--sm-signal); color: #201426; background: var(--sm-signal); }
.navbar-popover-enter-active, .navbar-popover-leave-active { transition: opacity .14s ease, transform .14s ease; }
.navbar-popover-enter-from, .navbar-popover-leave-to { opacity: 0; transform: translateY(-4px); }

@media (max-width: 900px) {
  .navbar-row { gap: 12px; padding: 0 12px; }
  .navbar-main { overflow-x: auto; scrollbar-width: none; }
  .navbar-main::-webkit-scrollbar { display: none; }
  .navbar-tab { padding: 0 8px; font-size: 11px; }
}
</style>
