<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { NConfigProvider, NMessageProvider, NNotificationProvider, NDialogProvider, NSpin, zhCN, dateZhCN } from 'naive-ui'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import { useFilterSync } from '@/composables/useFilterSync'
import { useAuthStore } from '@/stores/auth'
import { naiveThemeOverrides } from '@/theme'

const route = useRoute()
const authStore = useAuthStore()
useFilterSync()

const useDefaultLayout = computed(() => {
  return route.meta.requiresAuth === true
})

</script>

<template>
  <n-config-provider :theme-overrides="naiveThemeOverrides" :locale="zhCN" :date-locale="dateZhCN">
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
.global-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
  background: var(--sm-bg);
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
