<script setup lang="ts">
defineProps<{
  description?: string
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 gap-3">
    <div class="text-4xl">📭</div>
    <p class="text-sm text-gray-400">{{ description || '暂无数据' }}</p>
  </div>
</template>
