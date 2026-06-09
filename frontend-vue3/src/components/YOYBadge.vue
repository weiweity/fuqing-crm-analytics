<script setup lang="ts">
/**
 * humanizeChange: 格式化变化值, 统一 0.00 形式.
 *
 * Caller 已 *100 传 percentage/pp 数值, humanizeChange 只做 abs + toFixed(2).
 * 跟 MetricCard.vue 同步契约.
 *
 * @param v  - 变化值 (caller 已 *100 后的 percentage 或 pp 数值)
 * @param unit  '%' (百分比) | 'pp' (百分点差)
 * @returns  e.g. "14.00%", "5.00pp", "0.00%"
 */
function humanizeChange(v: number | null | undefined, unit: '%' | 'pp'): string {
  if (v == null) return '—'
  if (!Number.isFinite(v)) return `0.00${unit}`
  const display = Math.abs(v)
  return `${display.toFixed(2)}${unit}`
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
