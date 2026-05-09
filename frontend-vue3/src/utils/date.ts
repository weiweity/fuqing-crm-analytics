/**
 * Parse date range from query string (e.g., "2026-01-01,2026-01-31")
 */
export function parseDateRange(dateStr: string | null | undefined): [string, string] | null {
  if (!dateStr || typeof dateStr !== 'string') return null
  const parts = dateStr.split(',')
  if (parts.length === 2) {
    return [parts[0], parts[1]]
  }
  return null
}

/**
 * Format date to YYYY-MM-DD string
 */
export function formatDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Get quick date range presets
 */
export const QUICK_RANGES = [
  { label: '近7天', value: 'last7days' },
  { label: '近30天', value: 'last30days' },
  { label: '近90天', value: 'last90days' },
  { label: '近180天', value: 'last180days' },
  { label: '本月', value: 'thisMonth' },
  { label: '上月', value: 'lastMonth' },
  { label: '今年', value: 'thisYear' },
]

export function getQuickDateRange(preset: string): [string, string] | null {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const fmt = formatDate

  switch (preset) {
    case 'last7days': {
      const d = new Date(yesterday)
      d.setDate(d.getDate() - 6)
      return [fmt(d), fmt(yesterday)]
    }
    case 'last30days': {
      const d = new Date(yesterday)
      d.setDate(d.getDate() - 29)
      return [fmt(d), fmt(yesterday)]
    }
    case 'last90days': {
      const d = new Date(yesterday)
      d.setDate(d.getDate() - 89)
      return [fmt(d), fmt(yesterday)]
    }
    case 'last180days': {
      const d = new Date(yesterday)
      d.setDate(d.getDate() - 179)
      return [fmt(d), fmt(yesterday)]
    }
    case 'thisMonth': {
      const start = new Date(today.getFullYear(), today.getMonth(), 1)
      return [fmt(start), fmt(yesterday)]
    }
    case 'lastMonth': {
      const start = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      const end = new Date(today.getFullYear(), today.getMonth(), 0)
      return [fmt(start), fmt(end)]
    }
    case 'thisYear': {
      const start = new Date(today.getFullYear(), 0, 1)
      return [fmt(start), fmt(yesterday)]
    }
    default:
      return null
  }
}

/**
 * Get WTD/MTD/YTD/Q1-Q4 date range
 */
export type PeriodType = 'WTD' | 'MTD' | 'YTD' | 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'custom' | 'yesterday' | 'last180days' | 'last365days'

/**
 * 对比模式
 */
export type CompareMode = 'auto_yoy' | 'auto_mom' | 'custom'

/**
 * 根据对比模式返回列标题对 { current, compare, change }
 * auto_yoy → "{year}年" / "{year-1}年" / "YOY"
 * auto_mom → "当期" / "上期" / "环比"
 * custom   → "当期" / "对比期" / "对比"
 */
export function getCompareLabels(mode: CompareMode, yearLabel?: string, compYearLabel?: string): {
  current: string
  compare: string
  change: string
} {
  const yr = yearLabel || String(new Date().getFullYear())
  const yr2 = compYearLabel || String(new Date().getFullYear() - 1)
  if (mode === 'auto_mom') return { current: '当期', compare: '上期', change: '环比' }
  if (mode === 'custom') return { current: '当期', compare: '对比期', change: '对比' }
  return { current: yr, compare: yr2, change: 'YOY' }
}

/**
 * 根据当前日期范围 + 对比模式，计算对比期日期范围
 * auto_yoy: 去年同期（同月日）
 * auto_mom: 上一等长周期
 * custom:   返回 null（由用户自选）
 */
export function computeCompareRange(current: [string, string], mode: CompareMode): [string, string] | null {
  if (mode === 'custom') return null

  const [s, e] = current
  const startDate = new Date(s + 'T00:00:00')
  const endDate = new Date(e + 'T00:00:00')

  if (mode === 'auto_yoy') {
    const compStart = new Date(startDate)
    compStart.setFullYear(compStart.getFullYear() - 1)
    const compEnd = new Date(endDate)
    compEnd.setFullYear(compEnd.getFullYear() - 1)
    return [formatDate(compStart), formatDate(compEnd)]
  }

  if (mode === 'auto_mom') {
    const periodDays = Math.round((endDate.getTime() - startDate.getTime()) / 86400000) + 1
    const momEnd = new Date(startDate)
    momEnd.setDate(momEnd.getDate() - 1)
    const momStart = new Date(startDate)
    momStart.setDate(momStart.getDate() - periodDays)
    return [formatDate(momStart), formatDate(momEnd)]
  }

  return null
}

export function getPeriodDateRange(type: PeriodType): [string, string] | null {
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const year = today.getFullYear()
  const month = today.getMonth()
  const fmt = formatDate

  switch (type) {
    case 'yesterday': {
      return [fmt(yesterday), fmt(yesterday)]
    }
    case 'WTD': {
      const day = today.getDay() || 7 // 周日=7
      const start = new Date(today)
      start.setDate(today.getDate() - day + 1) // 周一
      return [fmt(start), fmt(yesterday)]
    }
    case 'MTD': {
      const start = new Date(year, month, 1)
      return [fmt(start), fmt(yesterday)]
    }
    case 'YTD': {
      const start = new Date(year, 0, 1)
      return [fmt(start), fmt(yesterday)]
    }
    case 'last180days': {
      const start = new Date(yesterday)
      start.setDate(start.getDate() - 179)
      return [fmt(start), fmt(yesterday)]
    }
    case 'last365days': {
      const start = new Date(yesterday)
      start.setDate(start.getDate() - 364)
      return [fmt(start), fmt(yesterday)]
    }
    case 'Q1': {
      const start = new Date(year, 0, 1)
      const end = month <= 2 ? yesterday : new Date(year, 2, 31)
      return [fmt(start), fmt(end)]
    }
    case 'Q2': {
      const start = new Date(year, 3, 1)
      const end = (month >= 3 && month <= 5) ? yesterday : new Date(year, 5, 30)
      return [fmt(start), fmt(end)]
    }
    case 'Q3': {
      const start = new Date(year, 6, 1)
      const end = (month >= 6 && month <= 8) ? yesterday : new Date(year, 8, 30)
      return [fmt(start), fmt(end)]
    }
    case 'Q4': {
      const start = new Date(year, 9, 1)
      const end = month >= 9 ? yesterday : new Date(year, 11, 31)
      return [fmt(start), fmt(end)]
    }
    default:
      return null
  }
}
