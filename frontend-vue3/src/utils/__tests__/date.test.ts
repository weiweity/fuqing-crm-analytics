// Sprint 173 MTD/WTD 月初/周初边界回归测试
// 锁定历史 bug: 月初 1 号打开 MTD 时, 原代码返 [本月1, 上月最后一天] 即 start > end 倒序窗口, 后端 SQL pay_time BETWEEN 无数据
// 修复后: fallback 上一个完整周期 (上月完整月 / 上周完整周)
// 跟 Sprint 173 用户截图复现 1:1: 当前日期 2026-07-01, MTD 应返 [2026-06-01, 2026-06-30]
import { describe, it, expect } from 'vitest'
import { getPeriodDateRange } from '../date'

/**
 * vi.setSystemTime mock 当前日期
 * '2026-07-01' 是 Sprint 173 用户报 bug 的当天, 锁定该日期 regression
 */
function withToday(iso: string, fn: () => void) {
  // 简化: 直接调用函数 (不依赖 vi.useFakeTimers)
  // 因为 getPeriodDateRange 内部用 new Date() 读 system time
  // vitest 1.x: vi.setSystemTime() / vi.useFakeTimers() — 我们用 useFakeTimers 模式
  const original = Date
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const MockDate: any = class extends Date {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    constructor(...args: any[]) {
      if (args.length === 0) {
        super(iso + 'T08:00:00')
      } else {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        super(...(args as any))
      }
    }
    static now() {
      return new Date(iso + 'T08:00:00').getTime()
    }
  }
  // @ts-expect-error 替换全局 Date 用于本次测试
  globalThis.Date = MockDate
  try {
    fn()
  } finally {
    globalThis.Date = original
  }
}

describe('Sprint 173 getPeriodDateRange 月初边界回归', () => {
  it('today=月中 (2026-06-15) MTD 应返 [2026-06-01, 2026-06-14]', () => {
    withToday('2026-06-15', () => {
      const range = getPeriodDateRange('MTD')
      expect(range).toEqual(['2026-06-01', '2026-06-14'])
    })
  })

  it('today=月初1号 (2026-07-01) MTD 应 fallback 上月完整月 [2026-06-01, 2026-06-30]', () => {
    // Sprint 173 真业务截图复现: 用户 7 月 1 日打开 App, 选月维度, 期望看到 6 月完整数据
    withToday('2026-07-01', () => {
      const range = getPeriodDateRange('MTD')
      expect(range).toEqual(['2026-06-01', '2026-06-30'])
    })
  })

  it('today=月初2号 (2026-07-02) MTD 应返本月 1 日单日 [2026-07-01, 2026-07-01]', () => {
    // 7 月 2 日 → yesterday=7-1, start=7-1, 应返本月 1 日单日窗口
    withToday('2026-07-02', () => {
      const range = getPeriodDateRange('MTD')
      expect(range).toEqual(['2026-07-01', '2026-07-01'])
    })
  })

  it('today=跨年月初 (2026-01-01) MTD 应 fallback 上年12月完整月 [2025-12-01, 2025-12-31]', () => {
    // 跨年边界 case 验证
    withToday('2026-01-01', () => {
      const range = getPeriodDateRange('MTD')
      expect(range).toEqual(['2025-12-01', '2025-12-31'])
    })
  })

  it('today=年中 WTD (2026-06-15 周一) 应返 [2026-06-15, 2026-06-14] ... 等等, WTD start > end', () => {
    // WTD 月内周一打开: start=今天=周一, yesterday=周日(=6-14) → start > yesterday
    // 修复后应 fallback 上周完整周
    withToday('2026-06-15', () => {
      const range = getPeriodDateRange('WTD')
      // 2026-06-15 是周一, 上周完整 = [2026-06-08, 2026-06-14]
      expect(range).toEqual(['2026-06-08', '2026-06-14'])
    })
  })

  it('today=月内周二 (2026-06-16) WTD 应正常 [2026-06-15, 2026-06-15] (本周一到昨天=周一=6-15 单日)', () => {
    // 周二打开 WTD: start=周一=6-15, yesterday=周一=6-15 → 单日窗口, 但昨天=周一 = 6-15 → start=昨天 OK
    withToday('2026-06-16', () => {
      const range = getPeriodDateRange('WTD')
      expect(range).toEqual(['2026-06-15', '2026-06-15'])
    })
  })

  it('today=月内周三 (2026-06-17) WTD 应正常 [2026-06-15, 2026-06-16]', () => {
    withToday('2026-06-17', () => {
      const range = getPeriodDateRange('WTD')
      expect(range).toEqual(['2026-06-15', '2026-06-16'])
    })
  })
})
