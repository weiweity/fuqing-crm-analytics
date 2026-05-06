<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NNotificationProvider, NDialogProvider } from 'naive-ui'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { useFilterSync } from '@/composables/useFilterSync'

useFilterSync()

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
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-notification-provider>
        <n-dialog-provider>
          <DefaultLayout>
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
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
