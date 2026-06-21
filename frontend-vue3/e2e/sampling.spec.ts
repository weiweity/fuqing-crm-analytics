import { test, expect } from './fixtures/auth.fixture'

/**
 * Sprint 33.2 候选 3: /sampling 路由 smoke 验证 — Sprint 32.3 a9b1d91 教训核心
 * Sprint 60.3 C+: 降级为纯 UI smoke。CI runner 无 production DuckDB，
 * 去掉 /api/v1/sampling/roi 业务断言，只验证路由/关键文案/无报错。
 */
test.describe('sampling 路由 (Sprint 32.3 治根重点)', () => {
  test.setTimeout(30000)

  test('访问 /sampling, PageHeader + ROI 文案渲染, 无控制台/API error (回归 a9b1d91)', async ({ authenticatedPage: page, consoleErrors }) => {
    await page.goto('/sampling')

    // 关键断言 1: PageHeader 标题可见 (a9b1d91 误清空后这块会空白)
    await expect(page.getByText('派样看板').first()).toBeVisible({ timeout: 30000 })

    // 关键断言 2: PageHeader subtitle 可见
    await expect(page.getByText('U先/百补派样ROI').first()).toBeVisible()

    // 关键断言 3: 渠道对比卡片 (数据为空时接受)
    await expect(page.getByText('U先派样').first()).toBeVisible({ timeout: 30000 }).catch(() => {
      // CI 无 production DuckDB 时可能不渲染, 接受
    })
    await expect(page.getByText('百补').first()).toBeVisible().catch(() => {
      // CI 无 production DuckDB 时可能不渲染, 接受
    })

    // 关键断言 4: 品类明细表 (数据 fetch 后才渲染, 接受 EmptyState)
    await expect(page.getByText('品类明细').first()).toBeVisible({ timeout: 5000 }).catch(() => {
      // CI 无 production DuckDB 时可能显示 EmptyState, 接受
    })

    // 无 console error 与 API 5xx (a9b1d91 当时 Vite 编译错会污染 console)
    expect(consoleErrors).toHaveLength(0)

    // 截图保留 (供 Sprint 32.3 a9b1d91 教训回归 baseline)
    await page.screenshot({ path: 'e2e/screenshots/sampling-roi-sprint33.png', fullPage: true })
  })
})
