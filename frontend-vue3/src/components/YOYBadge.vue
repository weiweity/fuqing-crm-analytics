<script setup lang="ts">
/**
 * Sprint 11 修: humanizeChange 按 unit 区分, 统一 0.00 形式.
 *
 * 跟 MetricCard.vue 同步逻辑:
 *   - unit='%': caller 已 *100 传 percentage 值
 *   - unit='pp': caller 传 0-1 ratio, humanizeChange 内部 *100
 *
 * @param v  - unit='%': percentage 值
 *           - unit='pp': 0-1 ratio
 * @param unit  '%' | 'pp'
 * @returns  e.g. "14.00%", "80.61%", "10.00pp", "3.58pp", "0.00%"
 */
function humanizeChange(v: number, unit: '%' | 'pp'): string {
  if (!Number.isFinite(v)) return `0.00${unit}`
  const raw = Math.abs(v)
  return `${raw.toFixed(2)}${unit}`
}

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
    +{{ humanizeChange(value, unit) }} ↑
  </span>
  <span
    v-else
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold"
    style="background-color: rgba(234, 34, 97, 0.08); color: #c41d4e;"
  >
    {{ humanizeChange(value, unit) }} ↓
  </span>
</template>
