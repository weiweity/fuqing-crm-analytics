<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BrandMark from '@/components/BrandMark.vue'
import { HOME_PATH, type NavItem, type NavTab } from '@/config/navigations'
import { useNavItems } from '@/composables/useNavItems'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const navItems = useNavItems()

const hoverKey = ref<string | null>(null)
let showTimer: number | null = null
let hideTimer: number | null = null
let idleTimer: number | null = null
let idleDisposed = false

// 0 disables the frontend idle logout. Ghost sessions are reclaimed by
// backend FQ_AUTH_IDLE_SECONDS (default 8h).
const IDLE_TIMEOUT_MS = 0
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

function resetIdleTimer() {
  if (IDLE_TIMEOUT_MS <= 0) return
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

watch(() => authStore.isAuthenticated, (isAuthenticated) => {
  if (isAuthenticated) {
    idleDisposed = false
    registerIdleListeners()
    resetIdleTimer()
  } else {
    idleDisposed = true
    if (idleTimer !== null) window.clearTimeout(idleTimer)
    idleTimer = null
    unregisterIdleListeners()
  }
})

onMounted(() => {
  if (authStore.isAuthenticated) {
    idleDisposed = false
    registerIdleListeners()
    resetIdleTimer()
  }
})

onBeforeUnmount(() => {
  clearShowTimer()
  clearHideTimer()
  idleDisposed = true
  if (idleTimer !== null) window.clearTimeout(idleTimer)
  idleTimer = null
  unregisterIdleListeners()
})
</script>

<template>
  <header class="navbar-shell">
    <div class="navbar-row">
      <router-link :to="HOME_PATH" class="navbar-brand" aria-label="SHINE MAGE 首页">
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
    </div>
  </header>
</template>

<style scoped>
.navbar-shell { position: relative; z-index: 30; border-bottom: var(--sm-dimension-px-1) solid var(--sm-line); color: var(--sm-ink); background: var(--sm-nav); backdrop-filter: var(--sm-blur-nav); -webkit-backdrop-filter: var(--sm-blur-nav); }
.navbar-row { display: flex; width: min(var(--sm-dimension-px-1800), 100%); min-height: var(--sm-dimension-px-48); align-items: center; gap: var(--sm-dimension-px-16); margin: 0 auto; padding: var(--sm-dimension-px-4) var(--sm-dimension-px-22); }
.navbar-brand { flex: 0 0 auto; color: inherit; text-decoration: none; }
.navbar-main { min-width: 0; flex: 1; overflow: visible; }
.navbar-tabs { display: flex; min-width: max-content; align-items: center; gap: var(--sm-dimension-px-3); }
.navbar-item { position: relative; }
.navbar-tab { display: inline-flex; min-height: var(--sm-dimension-px-28); align-items: center; gap: var(--sm-dimension-px-5); padding: 0 var(--sm-dimension-px-12); border: var(--sm-dimension-px-1) solid transparent; border-radius: var(--sm-radius-pill); color: var(--sm-muted); font-size: var(--sm-dimension-px-12); font-weight: 520; text-decoration: none; white-space: nowrap; transition: color var(--sm-motion-fast), border-color var(--sm-motion-fast), background var(--sm-motion-fast), box-shadow var(--sm-motion-fast); }
.navbar-tab:hover, .navbar-tab:focus-visible { border-color: var(--sm-line); color: var(--sm-ink); background: var(--sm-white-faint); }
.navbar-tab--active { border-color: var(--sm-line); color: var(--sm-signal); background: var(--sm-nav-active); box-shadow: var(--sm-shadow-nav-active); }
.navbar-tab span { color: var(--sm-faint); font-size: var(--sm-dimension-px-10); }
.navbar-popover { position: absolute; top: calc(100% + var(--sm-dimension-px-8)); left: 0; display: grid; min-width: var(--sm-dimension-px-214); gap: var(--sm-dimension-px-4); padding: var(--sm-dimension-px-8); border: var(--sm-dimension-px-1) solid var(--sm-line-strong); border-radius: var(--sm-radius-control); background: var(--sm-glass-strong); box-shadow: var(--sm-shadow-panel); backdrop-filter: var(--sm-blur-nav); }
.navbar-popover button { min-height: var(--sm-dimension-px-32); padding: 0 var(--sm-dimension-px-11); border: var(--sm-dimension-px-1) solid transparent; border-radius: var(--sm-dimension-px-8); color: var(--sm-copy); background: transparent; font-size: var(--sm-dimension-px-11); text-align: left; cursor: pointer; }
.navbar-popover button:hover, .navbar-popover button:focus-visible, .navbar-popover button.active { border-color: var(--sm-line); color: var(--sm-ink); background: var(--sm-purple-soft); }
.navbar-popover-enter-active, .navbar-popover-leave-active { transition: opacity .14s ease, transform .14s ease; }
.navbar-popover-enter-from, .navbar-popover-leave-to { opacity: 0; transform: translateY(var(--sm-dimension-px-minus-4)); }

@media (max-width: 900px) {
  .navbar-row { flex-wrap: wrap; gap: var(--sm-dimension-px-8); padding: var(--sm-dimension-px-8) var(--sm-dimension-px-12); }
  .navbar-main { position: relative; flex-basis: 100%; order: 3; }
  .navbar-tabs { min-width: 0; flex-wrap: wrap; }
  .navbar-item { position: static; }
  .navbar-popover { right: 0; min-width: 0; }
  .navbar-tab { padding: 0 var(--sm-dimension-px-8); font-size: var(--sm-dimension-px-11); }
}
</style>
