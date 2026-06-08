<script setup lang="ts">
withDefaults(defineProps<{
  value: number | null | undefined
  unit?: '%' | 'pp'   // '%'=百分比变化(默认), 'pp'=百分点差
}>(), {
  unit: '%',
})
</script>

<template>
  <span v-if="value == null" class="text-slate-400">—</span>
  <span
    v-else-if="value >= 0"
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold"
    style="background-color: rgba(21, 190, 83, 0.08); color: #108c3d;"
  >
    <template v-if="unit === '%'">+{{ (value * 100).toFixed(2) }}% ↑</template>
    <template v-else>+{{ value.toFixed(2) }}pp ↑</template>
  </span>
  <span
    v-else
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold"
    style="background-color: rgba(234, 34, 97, 0.08); color: #c41d4e;"
  >
    <template v-if="unit === '%'">{{ (value * 100).toFixed(2) }}% ↓</template>
    <template v-else>{{ value.toFixed(2) }}pp ↓</template>
  </span>
</template>
