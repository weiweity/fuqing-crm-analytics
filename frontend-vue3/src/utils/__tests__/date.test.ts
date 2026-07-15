// Sprint 173 MTD/WTD 月初/周初边界回归测试
// 锁定历史 bug: 月初 1 号打开 MTD 时, 原代码返 [本月1, 上月最后一天] 即 start > end 倒序窗口, 后端 SQL pay_time BETWEEN 无数据
// 修复后: fallback 上一个完整周期 (上月完整月 / 上周完整周)
// 跟 Sprint 173 用户截图复现 1:1: 当前日期 2026-07-01, MTD 应返 [2026-06-01, 2026-06-30]
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { getPeriodDateRange } from '../date'

describe('Sprint 173 getPeriodDateRange 月初边界回归', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function setToday(iso: string) {
    vi.setSystemTime(new Date(iso + 'T08:00:00'))
  }

  it('today=月中 (2026-06-15) MTD 应返 [2026-06-01, 2026-06-14]', () => {
    setToday('2026-06-15')
    expect(getPeriodDateRange('MTD')).toEqual(['2026-06-01', '2026-06-14'])
  })

  it('today=月初1号 (2026-07-01) MTD 应 fallback 上月完整月 [2026-06-01, 2026-06-30]', () => {
    // Sprint 173 真业务截图复现: 用户 7 月 1 日打开 App, 选月维度, 期望看到 6 月完整数据
    setToday('2026-07-01')
    expect(getPeriodDateRange('MTD')).toEqual(['2026-06-01', '2026-06-30'])
  })

  it('today=月初2号 (2026-07-02) MTD 应返本月 1 日单日 [2026-07-01, 2026-07-01]', () => {
    // 7 月 2 日 → yesterday=7-1, start=7-1, 应返本月 1 日单日窗口
    setToday('2026-07-02')
    expect(getPeriodDateRange('MTD')).toEqual(['2026-07-01', '2026-07-01'])
  })

  it('today=跨年月初 (2026-01-01) MTD 应 fallback 上年12月完整月 [2025-12-01, 2025-12-31]', () => {
    // 跨年边界 case 验证
    setToday('2026-01-01')
    expect(getPeriodDateRange('MTD')).toEqual(['2025-12-01', '2025-12-31'])
  })

  it('today=元旦 (2026-01-01) YTD 应 fallback 上一完整年', () => {
    setToday('2026-01-01')
    expect(getPeriodDateRange('YTD')).toEqual(['2025-01-01', '2025-12-31'])
  })

  it.each([
    ['2026-01-01', 'Q1', ['2025-10-01', '2025-12-31']],
    ['2026-04-01', 'Q2', ['2026-01-01', '2026-03-31']],
    ['2026-07-01', 'Q3', ['2026-04-01', '2026-06-30']],
    ['2026-10-01', 'Q4', ['2026-07-01', '2026-09-30']],
  ] as const)('today=%s %s 应 fallback 上一完整季度', (today, period, expected) => {
    setToday(today)
    expect(getPeriodDateRange(period)).toEqual(expected)
  })

  it('today=周一 (2026-06-15) WTD 应 fallback 上周完整周 [2026-06-08, 2026-06-14]', () => {
    // 2026-06-15 是周一, WTD start = today = 6-15, yesterday = 6-14, start > yesterday → fallback 上周完整周
    setToday('2026-06-15')
    expect(getPeriodDateRange('WTD')).toEqual(['2026-06-08', '2026-06-14'])
  })

  it('today=周二 (2026-06-16) WTD 应正常 [2026-06-15, 2026-06-15] (本周一到昨天=周一=6-15 单日)', () => {
    // 周二打开 WTD: start=本周一=6-15, yesterday=周一=6-15 → 单日窗口, 但昨天=周一 = 6-15 → start=昨天 OK
    setToday('2026-06-16')
    expect(getPeriodDateRange('WTD')).toEqual(['2026-06-15', '2026-06-15'])
  })

  it('today=周三 (2026-06-17) WTD 应正常 [2026-06-15, 2026-06-16]', () => {
    setToday('2026-06-17')
    expect(getPeriodDateRange('WTD')).toEqual(['2026-06-15', '2026-06-16'])
  })
})
