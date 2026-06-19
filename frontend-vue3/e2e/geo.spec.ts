import { test, expect } from './fixtures/auth.fixture'

/**
 * Sprint 33.2 候选 3: /geo 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * 注意: GeoView 顶部有 "待优化更新" 重构遮罩 (跟 ChurnView 同根因),
 *       e2e 断言 PageHeader + 遮罩文字, 跳过 chart 断言 (被遮罩挡住)
 */
test.describe('geo 路由', () => {
  test('访问 /geo, PageHeader + 重构遮罩存在, 无控制台 error', async ({ authenticatedPage: page, consoleErrors }) => {
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
