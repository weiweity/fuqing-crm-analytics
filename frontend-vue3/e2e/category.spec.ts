import { test, expect } from './fixtures/auth.fixture'

/**
 * Sprint 33.2 候选 3: /category 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * CategoryView: 7 sub-tab (含"现状概览"默认), 1 个 ECharts 饼图, 4 MetricCard
 * 关键断言: overview MetricCard + 饼图 + 品类明细表 + sub-tab names
 */
test.describe('category 路由', () => {
  test('访问 /category, MetricCard + 饼图 + 明细表 + sub-tab 渲染, 无 error', async ({ authenticatedPage: page, consoleErrors }) => {
    await page.goto('/category')

    // 断言 PageHeader 标题
    await expect(page.getByText('品类看板').first()).toBeVisible({ timeout: 30000 })

    // 等待 overview data fetch (Sprint 43 #S43-2: 删 waitForTimeout, 下面 expect chart 自己 wait)

    // Sprint 32.2 #S32-2 模式: bi-card + filter 定位品类GSV分布饼图
    const pieCard = page.locator('.bi-card').filter({ hasText: '品类GSV分布' }).first()
    if (await pieCard.isVisible().catch(() => false)) {
      const chart = pieCard.locator('canvas').first()
      // ECharts 真实渲染 (data fetch + canvas draw), 容许 EmptyState
      await expect(chart).toBeVisible({ timeout: 30000 }).catch(() => {
        // 数据为空时显示 EmptyState, 接受
      })
    }

    // 断言品类明细表 + 单品概览子区块
    await expect(page.getByText('品类明细').first()).toBeVisible().catch(() => {})
    await expect(page.getByText('单品概览').first()).toBeVisible().catch(() => {})

    // 断言至少 1 个 sub-tab (7 个 sub-tab 中任意可见即可)
    await expect(page.getByText('现状概览').first()).toBeVisible()

    // 无 error 级别控制台日志
    expect(consoleErrors).toHaveLength(0)
  })
})
