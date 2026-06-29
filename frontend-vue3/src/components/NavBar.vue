<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAV_ITEMS, type NavItem, type NavTab } from '@/config/navigations'

// Sprint 159: base64 inline png, avoid committing PNG assets through LFS.
const logoPngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAGQAAAA0CAYAAAB8bJ2jAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAylpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDkuMS1jMDAxIDc5LjE0NjI4OTk3NzcsIDIwMjMvMDYvMjUtMjM6NTc6MTQgICAgICAgICI+IDxyZGY6UkRGIHhtbG5zOnJkZj0iaHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+IDxyZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PSIiIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bXBNTTpEb2N1bWVudElEPSJ4bXAuZGlkOjlCQ0JFODEyODVFODExRjBBMkZGQzY2NjBDNTUzQTY3IiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOjlCQ0JFODExODVFODExRjBBMkZGQzY2NjBDNTUzQTY3IiB4bXA6Q3JlYXRvclRvb2w9IkFkb2JlIFBob3Rvc2hvcCAyNS45IChNYWNpbnRvc2gpIj4gPHhtcE1NOkRlcml2ZWRGcm9tIHN0UmVmOmluc3RhbmNlSUQ9InhtcC5paWQ6RjNFRTg5NDIzNUZFMTFFRjkxNjA5NUNGOEREM0I0QzAiIHN0UmVmOmRvY3VtZW50SUQ9InhtcC5kaWQ6RjNFRTg5NDMzNUZFMTFFRjkxNjA5NUNGOEREM0I0QzAiLz4gPC9yZGY6RGVzY3JpcHRpb24+IDwvcmRmOlJERj4gPC94OnhtcG1ldGE+IDw/eHBhY2tldCBlbmQ9InIiPz7s/UHNAAAIZUlEQVR4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'
const logoDataUri = `data:image/png;base64,${logoPngBase64}`

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
          <img class="navbar-logo" :src="logoDataUri" alt="天猫CRM" />
          <div class="min-w-0">
            <h1 class="text-lg font-semibold leading-tight text-white">天猫CRM</h1>
            <p class="mt-0.5 text-xs font-medium leading-tight text-white/70">数据分析平台</p>
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
  gap: 28px;
  min-height: 64px;
  padding: 0 20px;
}

.navbar-brand {
  display: flex;
  min-width: 214px;
  align-items: center;
  gap: 14px;
}

.navbar-logo {
  width: 68px;
  height: 36px;
  flex-shrink: 0;
  object-fit: contain;
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
  padding: 0 15px;
  border-bottom: 2px solid transparent;
  border-radius: 6px 6px 0 0;
  color: rgba(255, 255, 255, 0.78);
  /* Sprint 159.5: 15px → 18px 跟 Sprint 159 NavBar h1 text-lg (18px) 字号对齐, user 试看 amend */
  font-size: 18px;
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
  font-size: 11px;
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
  min-height: 38px;
  padding: 0 13px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 14px;
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
