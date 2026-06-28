<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAV_ITEMS, type NavItem, type NavTab } from '@/config/navigations'

const route = useRoute()
const router = useRouter()

const hoverKey = ref<string | null>(null)
let showTimer: number | null = null
let hideTimer: number | null = null

const activeKey = computed(() => {
  const activeItem = NAV_ITEMS.find((item) => {
    if (item.key === route.path) return true
    return item.key === '/category' && route.path.startsWith('/category-detail')
  })

  return activeItem?.key ?? route.path
})

function clearShowTimer() {
  if (showTimer !== null) {
    window.clearTimeout(showTimer)
    showTimer = null
  }
}

function clearHideTimer() {
  if (hideTimer !== null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }
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

onBeforeUnmount(() => {
  clearShowTimer()
  clearHideTimer()
})
</script>

<template>
  <div class="navbar-shell">
    <header class="navbar-header">
      <div class="navbar-header-row">
        <div class="navbar-brand">
          <div class="navbar-logo-placeholder">天</div>
          <div class="min-w-0">
            <h1 class="text-base font-semibold leading-tight text-white">天猫CRM</h1>
            <p class="mt-0.5 text-[11px] font-medium leading-tight text-white/70">数据分析平台</p>
          </div>
        </div>

        <nav class="navbar-main" aria-label="主导航">
          <div class="navbar-tabs">
            <div
              v-for="item in NAV_ITEMS"
              :key="item.key"
              class="relative"
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
                :aria-controls="`navbar-popover-${item.key.replace('/', '')}`"
                @click="closePopover"
              >
                <span>{{ item.label }}</span>
                <span aria-hidden="true" class="navbar-tab-chevron">▾</span>
              </router-link>

              <Transition name="navbar-popover">
                <div
                  v-if="hoverKey === item.key && item.tabs.length"
                  :id="`navbar-popover-${item.key.replace('/', '')}`"
                  class="navbar-popover"
                  role="menu"
                  @mouseenter="keepPopoverOpen"
                  @mouseleave="scheduleClosePopover"
                >
                  <button
                    v-for="tab in item.tabs"
                    :key="tab.key"
                    type="button"
                    class="navbar-popover-item"
                    :class="{ 'navbar-popover-item--active': isPopoverTabActive(item, tab) }"
                    role="menuitem"
                    @click="navigateToTab(item, tab)"
                  >
                    {{ tab.label }}
                  </button>
                </div>
              </Transition>
            </div>
          </div>
        </nav>
      </div>
    </header>
  </div>
</template>

<style scoped>
.navbar-shell {
  position: relative;
  z-index: 30;
  background: #f1f5f9;
}

.navbar-header {
  max-width: 1600px;
  margin: 0 auto;
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.navbar-header-row {
  display: flex;
  align-items: center;
  gap: 26px;
  min-height: 64px;
  padding: 0 20px;
}

.navbar-brand {
  display: flex;
  min-width: 180px;
  align-items: center;
  gap: 12px;
}

/* Sprint 158: logo 改文字占位符 (避免 png 走 LFS filter 推送失败) */
.navbar-logo-placeholder {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  border: 1.5px solid rgba(255, 255, 255, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 15px;
  color: #fff;
}

.navbar-main {
  min-width: 0;
  flex: 1;
}

.navbar-tabs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.navbar-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 48px;
  padding: 0 14px;
  border-bottom: 2px solid transparent;
  border-radius: 6px 6px 0 0;
  color: rgba(255, 255, 255, 0.78);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.16s ease, border-color 0.16s ease, background-color 0.16s ease;
  white-space: nowrap;
}

.navbar-tab:hover,
.navbar-tab:focus-visible {
  color: #ffffff;
  background-color: rgba(255, 255, 255, 0.12);
  outline: none;
}

.navbar-tab--active {
  color: #ffffff;
  border-bottom-color: #ffffff;
  font-weight: 600;
}

.navbar-tab-chevron {
  color: rgba(255, 255, 255, 0.55);
  font-size: 10px;
  line-height: 1;
}

.navbar-popover {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 236px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(18px);
  overflow: hidden;
}

.navbar-popover::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  content: "";
  background: linear-gradient(180deg, #2563eb 0%, #38bdf8 100%);
}

.navbar-popover-item {
  position: relative;
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  min-height: 36px;
  padding: 0 13px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 13px;
  font-weight: 500;
  text-align: left;
  box-shadow: 4px 4px 10px rgba(148, 163, 184, 0.28), -4px -4px 10px rgba(255, 255, 255, 0.9);
  cursor: pointer;
  overflow: hidden;
  z-index: 1;
  transition: color 0.2s ease-in, border-color 0.2s ease-in, box-shadow 0.2s ease-in, transform 0.2s ease-in;
}

.navbar-popover-item + .navbar-popover-item {
  margin-top: 8px;
}

.navbar-popover-item::before,
.navbar-popover-item::after {
  position: absolute;
  display: block;
  border-radius: 50%;
  content: "";
  z-index: -1;
}

.navbar-popover-item::before {
  top: 100%;
  left: 50%;
  width: 140%;
  height: 180%;
  background-color: rgba(0, 0, 0, 0.05);
  transform: translateX(-50%) scaleY(1) scaleX(1.25);
  transition: all 0.5s 0.1s cubic-bezier(0.55, 0, 0.1, 1);
}

.navbar-popover-item::after {
  top: 180%;
  left: 55%;
  width: 160%;
  height: 190%;
  background-color: #2563eb;
  transform: translateX(-50%) scaleY(1) scaleX(1.45);
  transition: all 0.5s 0.1s cubic-bezier(0.55, 0, 0.1, 1);
}

.navbar-popover-item:hover,
.navbar-popover-item:focus-visible {
  color: #ffffff;
  border-color: #2563eb;
  outline: none;
  transform: translateY(-1px);
}

.navbar-popover-item:hover::before,
.navbar-popover-item:focus-visible::before {
  top: -35%;
  background-color: #2563eb;
  transform: translateX(-50%) scaleY(1.3) scaleX(0.8);
}

.navbar-popover-item:hover::after,
.navbar-popover-item:focus-visible::after {
  top: -45%;
  background-color: #2563eb;
  transform: translateX(-50%) scaleY(1.3) scaleX(0.8);
}

.navbar-popover-item:active {
  color: #e2e8f0;
  box-shadow: inset 3px 3px 8px rgba(148, 163, 184, 0.34), inset -3px -3px 8px rgba(255, 255, 255, 0.78);
  transform: translateY(0);
}

.navbar-popover-item--active {
  color: #1d4ed8;
  border-color: rgba(37, 99, 235, 0.38);
  font-weight: 600;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.18), 4px 4px 10px rgba(148, 163, 184, 0.24), -4px -4px 10px rgba(255, 255, 255, 0.9);
}

.navbar-popover-item--active::before {
  top: 50%;
  left: 10px;
  width: 6px;
  height: 6px;
  background-color: #2563eb;
  transform: translateY(-50%);
  transition: none;
}

.navbar-popover-item--active {
  padding-left: 22px;
}

.navbar-popover-enter-active,
.navbar-popover-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.navbar-popover-enter-from,
.navbar-popover-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 640px) {
  .navbar-header-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
    padding: 10px 14px 0;
  }

  .navbar-brand {
    min-width: 0;
  }

  .navbar-tab {
    min-height: 42px;
    padding: 0 10px;
    font-size: 13px;
  }

  .navbar-popover {
    min-width: 190px;
  }
}
</style>
