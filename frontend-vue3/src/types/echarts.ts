/**
 * 共享 ECharts 类型定义
 * 用于 tooltip/formatter 等回调函数参数类型化，替代 any[]
 */

export interface EChartTooltipParam {
  name: string
  color: string
  seriesName: string
  value: number | string
  dataIndex?: number
  seriesIndex?: number
}

export interface EChartLabelParam {
  name: string
  value: number | string
  dataIndex?: number
}
