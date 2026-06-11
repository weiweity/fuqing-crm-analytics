<script setup lang="ts">
/**
 * YOYBadge: YOY 变化值徽章 (Sprint 11+, Sprint 16.5 #92 加守卫, Sprint 18 #124 抽 YOYGuard).
 *
 * Sprint 18 #124 抽 YOYGuard 通用组件:
 * - 异常值守卫 (|v|>1e6 → "数据异常") + pass-through 格式化 (abs + toFixed(2)) 抽到 YOYGuard
 * - YOYBadge 变 thin wrapper, 只负责箭头 (↑/↓) + 颜色 (绿/红) 包装
 *
 * 跟 MetricCard.vue 同步契约: caller 已 *100 传 percentage/pp 数值.
 */
import YOYGuard from './YOYGuard.vue'

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
    +<YOYGuard :value="value" :unit="unit" /> ↑
  </span>
  <span
    v-else
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold"
    style="background-color: rgba(234, 34, 97, 0.08); color: #c41d4e;"
  >
    <YOYGuard :value="value" :unit="unit" /> ↓
  </span>
</template>
