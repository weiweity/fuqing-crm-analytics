<script setup lang="ts">
import { NSkeleton } from 'naive-ui'

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
        <template v-if="unit === '%'">{{ change > 0 ? '▲' : change < 0 ? '▼' : '' }}{{ change !== 0 ? Math.abs(change).toFixed(1) + '%' : '0.0%' }}</template>
        <template v-else>{{ change > 0 ? '▲' : change < 0 ? '▼' : '' }}{{ change !== 0 ? Math.abs(change * 100).toFixed(1) + 'pp' : '0.0pp' }}</template>
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
