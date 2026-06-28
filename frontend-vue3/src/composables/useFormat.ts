/**
 * useFormat - 统一数字/百分比/货币格式化 (Sprint 146 P0.2)
 *
 * 替换散落的 toFixed/toLocaleString/手动除以 10000 等不一致模式,
 * 让 5 section + 5 metric + 4 桶柱状图全用统一 formatter。
 *
 * 关联 L4.7 精准修改 + Sprint 144 后续 UX 治本 (YOYBadge 降级配套)
 */
export function useFormat() {
  /** 千分位整数 (e.g. 1700 → "1,700") */
  const formatNumber = (value: number | null | undefined, fallback = '—'): string => {
    if (value == null || !Number.isFinite(value)) return fallback
    return Math.round(value).toLocaleString('zh-CN')
  }

  /** 百分比 (0-1 decimal → "12.3%"). scale=1000 显示 千分位 (1.234% → "1.2%") */
  const formatPercent = (value: number | null | undefined, decimals = 1, fallback = '—'): string => {
    if (value == null || !Number.isFinite(value)) return fallback
    return `${(value * 100).toFixed(decimals)}%`
  }

  /** 货币 (元 → ¥1,234 or ¥1.2万). scale='yuan' 显示原始元, 'wan' 显示万元 */
  const formatCurrency = (
    value: number | null | undefined,
    scale: 'yuan' | 'wan' = 'wan',
    decimals = 1,
    fallback = '—',
  ): string => {
    if (value == null || !Number.isFinite(value)) return fallback
    if (scale === 'wan') {
      const wan = value / 10000
      return wan >= 100
        ? `¥${wan.toFixed(0)}万`
        : `¥${wan.toFixed(decimals)}万`
    }
    return `¥${Math.round(value).toLocaleString('zh-CN')}`
  }

  /** YOY/MOM delta 文本 (e.g. "+5.2% ↑" / "-1.3% ↓"). 用于 YOYBadge 降级版 */
  const formatDelta = (
    value: number | null | undefined,
    unit: '%' | 'pp' = '%',
    fallback = '',
  ): string => {
    if (value == null || !Number.isFinite(value)) return fallback
    const sign = value > 0 ? '+' : value < 0 ? '−' : ''
    const arrow = value > 0 ? '↑' : value < 0 ? '↓' : '·'
    const num = Math.abs(value)
    return unit === 'pp' ? `${sign}${num.toFixed(2)}${unit} ${arrow}` : `${sign}${num.toFixed(1)}${unit} ${arrow}`
  }

  return { formatNumber, formatPercent, formatCurrency, formatDelta }
}