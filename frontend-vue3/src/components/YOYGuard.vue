<script setup lang="ts">
/**
 * YOYGuard: 通用 YOY/同比 守卫 + 格式化组件 (Sprint 18 #124, Sprint 20 P1-2 吸 YOYBadge 风格)
 *
 * 设计 (Sprint 20 P1-2 整合):
 * - 核心: |v| > threshold → "数据异常" 守卫 (Sprint 16.5 #92 同款)
 * - 格式化: caller 已 *100 传值 (跟 YOYBadge / MetricCard 契约一致),
 *   组件只做 abs + toFixed, 不再内部 *100
 * - 通用: 不耦合 UI 样式, 调用方负责包装颜色/箭头 (RFMSegmentDrilldown 表格用法)
 * - styled 模式 (Sprint 20 P1-2 新增): 跟原 YOYBadge 完全一致 — 箭头 (↑/↓) + 颜色 (绿/红),
 *   9 个表格组件 (AudienceView/CategoryView/RFMView/CategoryRepurchaseTab/ProductClassRepurchaseTab/
 *   health/{F,M,R}IntervalTab/ValueTierTab/HealthOverviewTab) 改用 YOYGuard styled=true,
 *   删 YOYBadge.vue wrapper
 *
 * Props:
 * - value: 数值 (caller 已 *100 后的 percentage 或 pp 数值)
 * - unit: '%' (百分比) | 'pp' (百分点差) | 'raw' (无后缀, 给自定义场景)
 * - threshold: 异常值阈值, 默认 1e6, 可由 `VITE_YOY_GUARD_THRESHOLD` env 覆盖
 * - empty: null/undefined 时返回的字符串, 默认 '—'
 * - precision: 小数位数, 默认 2
 * - styled: false (默认, 无样式) | true (YOYBadge 同款箭头+颜色包装, 表格用法)
 *
 * 用法 1 (unstyled, RFMSegmentDrilldown / MetricCard 数字格):
 *   <YOYGuard :value="v" unit="pp" :precision="1" />
 *
 * 用法 2 (styled, 表格 cell 替代 YOYBadge, Sprint 20 P1-2 9 文件迁移):
 *   <YOYGuard :value="row.yoy" unit="%" styled />
 *
 * 用法 3 (自定义 fallback):
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
    styled?: boolean
  }>(),
  {
    unit: '%',
    threshold: Number(import.meta.env.VITE_YOY_GUARD_THRESHOLD ?? 1e6),
    empty: '—',
    precision: 2,
    styled: false,
  },
)

// 守卫 + 格式化逻辑 (Sprint 18 #124 已实现, Sprint 20 P1-2 不变)
const formatted = computed(() => {
  const v = props.value
  if (v == null) return props.empty
  // 异常值守卫: |v| > threshold (覆盖 Infinity + 万倍异常值)
  if (Math.abs(v) > props.threshold) return '数据异常'
  if (!Number.isFinite(v)) {
    // NaN 走 fallback
    return `0.${'0'.repeat(props.precision)}${props.unit === 'raw' ? '' : props.unit}`
  }
  const display = Math.abs(v)
  return `${display.toFixed(props.precision)}${props.unit === 'raw' ? '' : props.unit}`
})

// styled 模式: 复用 formatted (异常/格式化), 外面加箭头+颜色 wrapper
// 跟原 YOYBadge Sprint 16.5 #92 守卫 + Sprint 18 #124 抽组件 后的渲染契约完全一致
const isOutlier = computed(() => {
  const v = props.value
  return v != null && Math.abs(v) > props.threshold
})
const isPositive = computed(() => {
  const v = props.value
  return v != null && v >= 0 && !isOutlier.value
})
const isNull = computed(() => props.value == null)
</script>

<template>
  <!-- styled=false (默认): 纯文本, 数字+单位 -->
  <span v-if="!styled" class="yoy-guard">{{ formatted }}</span>

  <!-- styled=true: YOYBadge 同款渲染 (箭头 + 颜色), 9 文件迁移用 -->
  <span
    v-else-if="isNull"
    class="text-slate-400"
  >—</span>
  <span
    v-else-if="isOutlier"
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold text-slate-400"
    title="数据异常: 变化值超过 1e6 (1 百万%)"
  >数据异常</span>
  <span
    v-else-if="isPositive"
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold"
    style="background-color: rgba(21, 190, 83, 0.08); color: #108c3d;"
  >+<span class="yoy-guard">{{ formatted }}</span> ↑</span>
  <span
    v-else
    class="inline-flex items-center px-1.5 py-0.5 rounded text-[12px] font-semibold"
    style="background-color: rgba(234, 34, 97, 0.08); color: #c41d4e;"
  ><span class="yoy-guard">{{ formatted }}</span> ↓</span>
</template>
