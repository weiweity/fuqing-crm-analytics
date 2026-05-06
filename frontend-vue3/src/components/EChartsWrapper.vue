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
