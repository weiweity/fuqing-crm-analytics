<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CHART_COLORS } from '@/composables/useChartTheme'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent, DataZoomComponent])

/** ECharts tooltip params 类型（避免 any） */
interface TooltipParams {
  axisValue: string
  seriesName: string
  value: number | string
  color: string
  seriesIndex: number
  dataIndex: number
}

interface SeriesItem {
  name: string
  data: number[]
  color?: string
  yAxisIndex?: number
  areaStyle?: boolean
  lineStyle?: { width?: number; type?: 'solid' | 'dashed' }
}

interface YAxisConfig {
  name?: string
  position?: 'left' | 'right'
  min?: number
  max?: number
  formatter?: (v: number) => string
}

const props = defineProps<{
  xAxisData: string[]
  series: SeriesItem[]
  yAxis?: YAxisConfig | YAxisConfig[]
  height?: string
}>()

/** 解析十六进制颜色为 rgba */
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** 为系列颜色生成渐变 areaStyle */
function buildAreaStyle(color: string) {
  return {
    color: {
      type: 'linear',
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: hexToRgba(color, 0.10) },
        { offset: 1, color: hexToRgba(color, 0) },
      ],
    },
  }
}

const hasDualYAxis = computed(() => Array.isArray(props.yAxis) && props.yAxis.length >= 2)

const yAxisConfig = computed(() => {
  if (Array.isArray(props.yAxis)) {
    return props.yAxis.map((y, i) => ({
      type: 'value' as const,
      name: y.name || '',
      position: y.position || (i === 0 ? 'left' : 'right'),
      min: y.min,
      max: y.max,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: i === 0 ? '#64748b' : '#94a3b8',
        fontSize: 11,
        formatter: y.formatter || ((v: number) => String(v)),
      },
      splitLine: i === 0
        ? { lineStyle: { color: '#e2e8f0', type: [4, 4] } }
        : { show: false },
    }))
  }
  const y = props.yAxis || {}
  return [{
    type: 'value' as const,
    name: y.name || '',
    position: 'left',
    min: y.min,
    max: y.max,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#64748b',
      fontSize: 11,
      formatter: y.formatter || ((v: number) => String(v)),
    },
    splitLine: { lineStyle: { color: '#e2e8f0', type: [4, 4] } },
  }]
})

const option = computed(() => ({
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(255, 255, 255, 0.98)',
    borderColor: '#e2e8f0',
    borderWidth: 1,
    padding: [10, 12],
    textStyle: { color: '#0f172a', fontSize: 12 },
    extraCssText: 'box-shadow: 0 4px 12px -2px rgba(0,0,0,0.08); border-radius: 4px;',
    formatter: (params: TooltipParams[]) => {
      let html = `<div style="font-weight:600;margin-bottom:6px;font-size:13px">${params[0].axisValue}</div>`
      params.forEach((p) => {
        const marker = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>`
        html += `<div style="display:flex;align-items:center;gap:4px;margin-top:3px">
          ${marker}
          <span style="flex:1;color:#64748b;font-size:12px">${p.seriesName}</span>
          <span style="font-weight:600;color:#0f172a;font-size:12px">${p.value}</span>
        </div>`
      })
      return html
    },
  },
  legend: {
    top: 0,
    type: 'scroll',
    icon: 'circle',
    itemGap: 16,
    itemWidth: 10,
    itemHeight: 10,
    textStyle: { color: '#64748b', fontSize: 11 },
  },
  grid: {
    left: 12,
    right: hasDualYAxis.value ? 48 : 12,
    top: 36,
    bottom: 8,
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    data: props.xAxisData,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#64748b', fontSize: 11, margin: 10 },
  },
  yAxis: yAxisConfig.value,
  series: props.series.map((s, i) => {
    const color = s.color || CHART_COLORS[i % CHART_COLORS.length]
    return {
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: s.lineStyle?.width ?? 2.5, color, type: s.lineStyle?.type ?? 'solid' },
      itemStyle: { color },
      areaStyle: s.areaStyle !== false ? buildAreaStyle(color) : undefined,
      emphasis: { focus: 'series' },
      yAxisIndex: s.yAxisIndex ?? 0,
    }
  }),
}))
</script>

<template>
  <VChart
    class="w-full"
    :style="{ height: height || '300px' }"
    :option="option"
    autoresize
  />
</template>
