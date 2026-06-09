<script setup lang="ts">
/**
 * Sprint 11 修: humanizeChange 把 0-1 ratio 转成可读字符串.
 * - 用 Math.round 替代 toFixed (避免 toFixed 的 IEEE 754 banker's rounding bug)
 * - 自动 trim 整数 trailing zeros: 14.00 → "14", 14.55 → "14.55"
 *
 * @param v  0-1 ratio (e.g. 0.1437 = 14.37%)
 * @param unit  '%' (百分比) | 'pp' (百分点差)
 * @returns  e.g. "14%", "14.5%", "14.55%", "10pp", "3.58pp"
 */
function humanizeChange(v: number, unit: '%' | 'pp'): string {
  if (v === 0 || !Number.isFinite(v)) return `0${unit}`
  const pct = Math.round(Math.abs(v) * 100 * 100) / 100
  return `${pct}${unit}`
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
