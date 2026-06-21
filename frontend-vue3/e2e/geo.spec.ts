import { test, expect } from './fixtures/auth.fixture'

/**
 * Sprint 33.2 候选 3: /geo 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * 注意: GeoView 顶部有 "待优化更新" 重构遮罩 (跟 ChurnView 同根因),
 *       e2e 断言 PageHeader + 遮罩文字, 跳过 chart 断言 (被遮罩挡住)
 */
test.describe('geo 路由', () => {
  test('访问 /geo, PageHeader + 重构遮罩存在, 无控制台 error', async ({ authenticatedPage: page, consoleErrors }) => {
    // Sprint 60.3+ C+: CI 用 schema-only DB，geo 接口在空数据下会 500 或缺字段；mock 成合法空响应
    await page.route('/api/v1/geo/**', async (route) => {
      const url = route.request().url()
      let body = '{}'
      if (url.includes('/distribution')) {
        body = JSON.stringify({ date: '', level: 'province', total_users: 0, total_gmv: 0, distribution: [] })
      } else if (url.includes('/trend')) {
        body = JSON.stringify({ time_points: [], top_provinces: [], trends: {} })
      } else if (url.includes('/segment-matrix')) {
        body = JSON.stringify({ date: '', matrix: {}, segments: [] })
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body })
    })

    await page.goto('/geo')

    // 断言 PageHeader 标题
    await expect(page.getByText('地域分析').first()).toBeVisible({ timeout: 30000 })

    // 断言重构遮罩 (跟 ChurnView 相同的 "待优化更新" 文案)
    await expect(page.getByText('待优化更新').first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('该模块正在重构中').first()).toBeVisible()

    // 无 error 级别控制台日志
    expect(consoleErrors).toHaveLength(0)
  })
})
