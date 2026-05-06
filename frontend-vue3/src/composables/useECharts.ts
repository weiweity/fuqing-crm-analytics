import { shallowRef, onUnmounted } from 'vue'
import type { ECharts, EChartsOption } from 'echarts'
import { useChartTheme } from './useChartTheme'

export function useECharts() {
  const { baseTheme } = useChartTheme()
  const chartInstance = shallowRef<ECharts | null>(null)

  onUnmounted(() => {
    chartInstance.value?.dispose()
  })

  function mergeOptions(option: EChartsOption) {
    chartInstance.value?.setOption(option, { notMerge: false })
  }

  function setOption(option: EChartsOption) {
    if (chartInstance.value) {
      chartInstance.value.setOption(option)
    }
  }

  return {
    chartInstance,
    mergeOptions,
    setOption,
    baseTheme,
  }
}
