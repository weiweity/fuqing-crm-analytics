<script setup lang="ts">
import { NSkeleton } from 'naive-ui'

/**
 * Sprint 11 修: humanizeChange 把 0-1 ratio 转成可读字符串.
 * - 用 Math.round 替代 toFixed (避免 toFixed 的 IEEE 754 banker's rounding bug, e.g. 0.005 → '0.00' 而非 '0.01')
 * - 自动 trim 整数 trailing zeros: 14.00 → "14%", 14.55 → "14.55%"
 * - 0 显示 "0%" / "0pp" (而非 "0.00%")
 *
 * @param v  0-1 ratio (e.g. 0.1437 = 14.37%)
 * @param unit  '%' (百分比) | 'pp' (百分点差)
 * @returns  e.g. "14%", "14.5%", "14.55%", "10pp", "3.58pp"
 */
function humanizeChange(v: number, unit: '%' | 'pp'): string {
  if (v === 0 || !Number.isFinite(v)) return `0${unit}`
  // 先 * 100 拿到 percentage value, 再 round 到 2 位, 再 toString 自动 trim trailing zeros
  const pct = Math.round(Math.abs(v) * 100 * 100) / 100
  // 0.x → "0.5", 14.55 → "14.55", 14 → "14"
  return `${pct}${unit}`
}

withDefaults(defineProps<{
  title: string
  value: string | number
  change?: number
  suffix?: string
  loading?: boolean
  format?: 'number' | 'currency' | 'percent'
  unit?: '%' | 'pp'   // '%'=百分比变化(默认), 'pp'=百分点差
  subtitle?: string
  formula?: string
}>(), {
  unit: '%',
})
</script>

<template>
  <div class="bi-card bi-card-hover px-4 py-3 transition-all duration-200 h-full">
    <div class="flex items-center justify-between">
      <p class="text-[13px] font-medium text-slate-500">{{ title }}</p>
      <span
        v-if="!loading && change !== undefined"
        :class="[
          'inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold',
          change > 0
            ? ''
            : change < 0
              ? ''
              : 'bg-slate-100 text-slate-400',
        ]"
        :style="change > 0 ? 'background-color: rgba(21, 190, 83, 0.08); color: #108c3d;' : change < 0 ? 'background-color: rgba(234, 34, 97, 0.08); color: #c41d4e;' : undefined"
      >
        {{ change > 0 ? '↑' : change < 0 ? '↓' : '' }}{{ humanizeChange(change, unit) }}
      </span>
    </div>
    <div class="mt-1.5">
      <n-skeleton v-if="loading" :width="90" :height="28" style="border-radius: 4px" />
      <span v-else class="text-[22px] font-semibold text-slate-900 tracking-tight tabular-nums">
        {{ (format === 'currency' && !String(value).startsWith('¥')) ? '¥' : '' }}{{ value }}{{ suffix || '' }}
      </span>
    </div>
    <p v-if="subtitle" class="mt-2 text-[11px] text-slate-400 leading-snug">
      * {{ subtitle }}
    </p>
    <p v-if="formula" class="mt-1 text-[10px] text-slate-300 leading-snug">
      {{ formula }}
    </p>
  </div>
</template>
