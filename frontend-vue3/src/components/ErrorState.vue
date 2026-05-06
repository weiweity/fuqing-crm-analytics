<script setup lang="ts">
import { NButton } from 'naive-ui'

defineProps<{
  message?: string
}>()

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 gap-4">
    <div class="text-4xl">⚠️</div>
    <p class="text-sm text-red-500">{{ message || '加载失败，请稍后重试' }}</p>
    <n-button size="small" @click="emit('retry')">重试</n-button>
  </div>
</template>
