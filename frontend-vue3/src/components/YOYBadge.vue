<script setup lang="ts">
/**
 * humanizeChange: 格式化变化值, 统一 0.00 形式.
 *
 * Caller 已 *100 传 percentage/pp 数值, humanizeChange 只做 abs + toFixed(2).
 * 跟 MetricCard.vue 同步契约.
 *
 * 异常值守卫 (Sprint 16.5 P2 Wave 6): |v| > 1e6 返回 "数据异常",
 * 避免 UI 显示 +1157823.86% 等万倍异常值误导用户.
 * 跟 backend/contracts/types.py PercentageField 注释对齐: "真实值 > 1e6 建议前端 YOYBadge 守卫".
 *
 * @param v  - 变化值 (caller 已 *100 后的 percentage 或 pp 数值)
 * @param unit  '%' (百分比) | 'pp' (百分点差)
 * @returns  e.g. "14.00%", "5.00pp", "0.00%", 或 |v|>1e6 时返 "数据异常"
 */
function humanizeChange(v: number | null | undefined, unit: '%' | 'pp'): string {
  if (v == null) return '—'
  if (!Number.isFinite(v)) return `0.00${unit}`
  // 异常值守卫: |v| > 1e6 (即 > 100 万%) 视为数据异常, 不显示 huge number
  if (Math.abs(v) > 1e6) return '数据异常'
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
    v-else-if="Math.abs(value) > 1e6"
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold text-slate-400"
    title="数据异常: 变化值超过 1e6 (1 百万%)"
  >
    数据异常
  </span>
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
