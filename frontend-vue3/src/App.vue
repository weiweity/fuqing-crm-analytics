<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { NConfigProvider, NMessageProvider, NNotificationProvider, NDialogProvider, NSpin, zhCN, dateZhCN } from 'naive-ui'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { useFilterSync } from '@/composables/useFilterSync'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()
useFilterSync()

const useDefaultLayout = computed(() => {
  return route.meta.requiresAuth === true
})

// BI Pro theme overrides for Naive UI
const themeOverrides = {
  common: {
    primaryColor: '#533afd',
    primaryColorHover: '#4528d9',
    primaryColorPressed: '#3312c4',
    primaryColorSuppl: '#7c5df5',
    successColor: '#10b981',
    warningColor: '#f59e0b',
    errorColor: '#ef4444',
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
    fontFamilyMono: "'SF Mono', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', monospace",
    fontWeight: '400',
    fontWeightStrong: '600',
    borderRadius: '6px',
    borderRadiusSmall: '4px',
  },
  Button: {
    borderRadiusMedium: '4px',
    borderRadiusSmall: '4px',
    fontWeight: '500',
  },
  Card: {
    borderRadius: '6px',
  },
  Menu: {
    borderRadius: '4px',
    itemHeight: '36px',
    itemBorderRadius: '4px',
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: '4px',
      },
    },
  },
  DatePicker: {
    borderRadius: '4px',
  },
  DataTable: {
    borderRadius: '6px',
    thColor: 'rgba(248, 250, 252, 1)',
    thColorModal: 'rgba(248, 250, 252, 1)',
    thFontWeight: '600',
    tdColor: '#ffffff',
    tdColorModal: '#ffffff',
    tdTextColor: '#0f172a',
    thTextColor: '#334155',
  },
}
</script>

<template>
  <!-- 系统维护遮盖（关闭时删除或设为 false） -->
  <div class="maintenance-overlay">
    <div class="maintenance-box">
      <div class="maintenance-icon">🔧</div>
      <h1>系统正在维护中</h1>
      <p>预计很快恢复，请稍后再试</p>
    </div>
  </div>

  <n-config-provider :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <n-notification-provider>
        <n-dialog-provider>
          <!-- 全局初始加载态 -->
          <div v-if="!authStore.isReady" class="global-loading">
            <n-spin size="large" description="加载中..." />
          </div>

          <template v-else-if="!useDefaultLayout">
            <router-view />
          </template>

          <DefaultLayout v-else>
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
          </DefaultLayout>
        </n-dialog-provider>
      </n-notification-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
.maintenance-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(255, 255, 255, 0.98);
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
}
.maintenance-box {
  text-align: center;
  color: #334155;
}
.maintenance-icon {
  font-size: 64px;
  margin-bottom: 24px;
}
.maintenance-box h1 {
  font-size: 28px;
  font-weight: 600;
  margin: 0 0 12px;
  color: #0f172a;
}
.maintenance-box p {
  font-size: 16px;
  color: #64748b;
  margin: 0;
}

.global-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
  background: #fff;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
