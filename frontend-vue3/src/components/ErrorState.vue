<script setup lang="ts">
/**
 * ErrorState - 错误状态展示 (Sprint 146 增强 401 区分)
 *
 * - 401: 会话过期, 显示 "重新登录" 按钮 (emit 'login')
 * - 其他: 显示 "重试" 按钮 (emit 'retry')
 */
import { NButton } from 'naive-ui'

withDefaults(defineProps<{
  message?: string
  status?: number
}>(), {
  status: 0,
})

const emit = defineEmits<{
  retry: []
  login: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 gap-4">
    <div class="text-4xl">{{ status === 401 ? '🔒' : '⚠️' }}</div>
    <p class="text-sm" :class="status === 401 ? 'text-amber-600' : 'text-red-500'">
      {{ status === 401 ? '会话已过期, 请重新登录' : (message || '加载失败, 请稍后重试') }}
    </p>
    <n-button v-if="status === 401" size="small" type="primary" @click="emit('login')">
      重新登录
    </n-button>
    <n-button v-else size="small" @click="emit('retry')">重试</n-button>
  </div>
</template>
