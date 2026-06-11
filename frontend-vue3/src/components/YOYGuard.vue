<script setup lang="ts">
/**
 * YOYGuard: 通用 YOY/同比 守卫 + 格式化组件 (Sprint 18 #124)
 *
 * 设计:
 * - 核心: |v| > threshold → "数据异常" 守卫 (Sprint 16.5 #92 同款)
 * - 格式化: caller 已 *100 传值 (跟 YOYBadge / MetricCard 契约一致),
 *   组件只做 abs + toFixed, 不再内部 *100
 * - 通用: 不耦合 UI 样式, 调用方负责包装颜色/箭头 (避免 4 组件代码复制)
 *
 * Props:
 * - value: 数值 (caller 已 *100 后的 percentage 或 pp 数值)
 * - unit: '%' (百分比) | 'pp' (百分点差) | 'raw' (无后缀, 给自定义场景)
 * - threshold: 异常值阈值, 默认 1e6
 * - empty: null/undefined 时返回的字符串, 默认 '—'
 * - precision: 小数位数, 默认 2
 *
 * 用法 1 (YOYBadge 替换内部 humanizeChange):
 *   <YOYGuard :value="value" :unit="unit" />
 *
 * 用法 2 (RFMSegmentDrilldown 表格单元, 1 位小数 + pp):
 *   <YOYGuard :value="v" unit="pp" :precision="1" />
 *
 * 用法 3 (自定义 fallback, 给 RFMSegmentDrilldown 表格的 '-' 占位):
 *   <YOYGuard :value="v" unit="pp" :precision="1" empty="-" />
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    value: number | null | undefined
    unit?: '%' | 'pp' | 'raw'
    threshold?: number
    empty?: string
    precision?: number
  }>(),
  {
    unit: '%',
    threshold: 1e6,
    empty: '—',
    precision: 2,
  },
)

const formatted = computed(() => {
  const v = props.value
  if (v == null) return props.empty
  // 异常值守卫: |v| > threshold (覆盖 Infinity + 万倍异常值, 跟原 humanizeChange 契约一致)
  if (Math.abs(v) > props.threshold) return '数据异常'
  if (!Number.isFinite(v)) {
    // NaN 走 fallback, 跟原 humanizeChange 契约一致
    return `0.${'0'.repeat(props.precision)}${props.unit === 'raw' ? '' : props.unit}`
  }
  const display = Math.abs(v)
  return `${display.toFixed(props.precision)}${props.unit === 'raw' ? '' : props.unit}`
})
</script>

<template>
  <span class="yoy-guard">{{ formatted }}</span>
</template>
