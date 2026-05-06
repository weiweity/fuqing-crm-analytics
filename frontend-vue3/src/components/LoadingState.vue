<script setup lang="ts">
import { NSpin } from 'naive-ui'

defineProps<{
  description?: string
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 gap-4">
    <n-spin size="large" />
    <p v-if="description" class="text-sm text-gray-400">{{ description }}</p>
    <p v-else class="text-sm text-gray-400">加载中...</p>
  </div>
</template>
