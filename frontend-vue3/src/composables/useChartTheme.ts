import type { EChartsOption } from 'echarts'
import { shineMageTheme } from '@/theme'

export const CHART_COLORS = [
  shineMageTheme.color.brandPrimary,
  shineMageTheme.color.brandAccent,
  shineMageTheme.color.brandSecondary,
  shineMageTheme.color.danger,
  shineMageTheme.color.success,
  shineMageTheme.color.brandPrimaryHover,
  shineMageTheme.color.warning,
  shineMageTheme.color.brandPrimaryPressed,
  shineMageTheme.color.muted,
  shineMageTheme.color.ink,
]

export const BRAND_PRIMARY = shineMageTheme.color.brandPrimary
export const BRAND_PRIMARY_LIGHT = shineMageTheme.color.brandPrimaryHover
export const BRAND_SECONDARY = shineMageTheme.color.brandSecondary

export const BRAND_FONT = "'-apple-system', 'BlinkMacSystemFont', 'SF Pro Text', 'SF Pro Display', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"

/**
 * 金额 tooltip formatter — 千分位 + ¥ 前缀
 */
export function fmtCurrencyTooltip(value: number): string {
  return `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}

export function useChartTheme() {
  const baseTheme: EChartsOption = {
    color: CHART_COLORS,
    textStyle: {
      fontFamily: BRAND_FONT,
      color: '#64748d',
    },
    title: {
      textStyle: {
        fontFamily: BRAND_FONT,
        color: '#061b31',
        fontWeight: 600,
        fontSize: 17,
      },
      subtextStyle: {
        fontFamily: BRAND_FONT,
        color: '#64748d',
        fontSize: 13,
      },
    },
    legend: {
      textStyle: {
        fontFamily: BRAND_FONT,
        color: '#64748d',
        fontSize: 12,
      },
      icon: 'circle',
      itemGap: 20,
    },
    tooltip: {
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e5edf5',
      borderWidth: 1,
      padding: [12, 16],
      textStyle: {
        fontFamily: BRAND_FONT,
        color: '#061b31',
        fontSize: 13,
      },
      extraCssText: 'box-shadow: rgba(50,50,93,0.25) 0px 13px 27px -5px, rgba(0,0,0,0.1) 0px 8px 16px -8px; border-radius: 6px;',
    },
    xAxis: {
      axisLabel: {
        fontFamily: BRAND_FONT,
        color: '#64748d',
        fontSize: 11,
        margin: 12,
      },
      axisLine: {
        lineStyle: { color: '#e5edf5' },
      },
      axisTick: { show: false },
      splitLine: {
        lineStyle: {
          color: '#f6f9fc',
          type: [4, 4],
        },
      },
    },
    yAxis: {
      axisLabel: {
        fontFamily: BRAND_FONT,
        color: '#64748d',
        fontSize: 11,
        margin: 12,
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: {
        lineStyle: {
          color: '#e5edf5',
          type: [4, 4],
        },
      },
    },
    grid: {
      left: 48,
      right: 24,
      top: 32,
      bottom: 32,
    },
  }

  return { baseTheme, CHART_COLORS, BRAND_FONT }
}
