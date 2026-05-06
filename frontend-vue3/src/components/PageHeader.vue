<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<template>
  <div class="flex items-end justify-between mb-5">
    <div>
      <h2 class="text-lg font-semibold text-slate-900 tracking-tight">{{ title }}</h2>
      <p v-if="subtitle" class="mt-0.5 text-xs text-slate-500">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
