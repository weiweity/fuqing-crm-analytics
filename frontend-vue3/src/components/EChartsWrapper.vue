<script setup lang="ts">
import { NSpin } from 'naive-ui'
import { watch, onMounted, onBeforeUnmount, nextTick, ref } from 'vue'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, BarChart, RadarChart, HeatmapChart, SankeyChart, FunnelChart, ScatterChart, EffectScatterChart, GraphChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  RadarComponent,
  VisualMapComponent,
} from 'echarts/components'
import { useChartTheme } from '@/composables/useChartTheme'

echarts.use([
  CanvasRenderer,
  PieChart,
  LineChart,
  BarChart,
  RadarChart,
  HeatmapChart,
  SankeyChart,
  FunnelChart,
  ScatterChart,
  EffectScatterChart,
  GraphChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  RadarComponent,
  VisualMapComponent,
])

const props = defineProps<{
  option: echarts.EChartsCoreOption
  height?: string
  loading?: boolean
}>()

const emit = defineEmits<{
  chartClick: [params: any]
}>()

const { baseTheme } = useChartTheme()
const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

function initChart() {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value, undefined, { renderer: 'canvas' })
  updateChart()
  // 确保在 DOM 布局完成后 resize
  requestAnimationFrame(() => {
    chartInstance?.resize()
  })
  // 转发 chart click 事件（同时监听 ECharts 内置事件 + 原生 click 事件以支持空白区域点击）
  // 用标志位避免柱体点击时重复触发（ECharts 内置事件 + 原生事件都会触发）
  let _echartsClickTimeout: ReturnType<typeof setTimeout> | null = null
  chartInstance.on('click', (params: any) => {
    emit('chartClick', params)
    // 标记：刚触发了 ECharts 内置 click，原生 click 应跳过
    if (_echartsClickTimeout) clearTimeout(_echartsClickTimeout)
    _echartsClickTimeout = setTimeout(() => { _echartsClickTimeout = null }, 100)
  })
  // 原生 click：仅当 ECharts 内置事件未触发时（即空白区域点击）才转发
  chartRef.value.addEventListener('click', (e: MouseEvent) => {
    if (!chartInstance) return
    // 如果 ECharts 内置 click 刚触发，跳过原生 click（避免重复）
    if (_echartsClickTimeout) return
    const rect = chartRef.value!.getBoundingClientRect()
    const offsetX = e.clientX - rect.left
    const offsetY = e.clientY - rect.top
    // 空白区域点击：传入坐标供父组件 convertFromPixel 使用
    emit('chartClick', { event: { offsetX, offsetY }, name: undefined })
  })
}

function updateChart() {
  if (!chartInstance) return
  const merged = { ...baseTheme, ...props.option } as echarts.EChartsCoreOption
  chartInstance.setOption(merged, { notMerge: true })
}

watch(() => props.option, () => {
  nextTick(() => {
    updateChart()
    chartInstance?.resize()
  })
}, { deep: true })

onMounted(() => {
  nextTick(initChart)
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

// ── 对外暴露方法 ──

/** 获取 ECharts 实例（供父组件调用） */
function getChartInstance(): echarts.ECharts | null {
  return chartInstance
}

/** 导出为 PNG 图片 */
function exportAsPng(filename: string, pixelRatio = 2): void {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({
    type: 'png',
    pixelRatio,
    backgroundColor: '#fff',
  })
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

defineExpose({ getChartInstance, exportAsPng })
</script>

<template>
  <div class="relative w-full" :style="{ height: height || '300px' }">
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-white/60 z-10">
      <n-spin size="large" />
    </div>
    <div ref="chartRef" class="w-full h-full" style="min-height: 80px" />
  </div>
</template>
