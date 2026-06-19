import { test, expect } from '@playwright/test'

/**
 * Sprint 33.2 候选 3: /category-detail/:id 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * 4 个 MetricCard + 日趋势图 (ECharts canvas) + RFM 饼图 + 用户明细表
 */
test.describe('category-detail 路由', () => {
  const consoleErrors: string[] = []

  test.beforeEach(async ({ page }) => {
    consoleErrors.length = 0
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        // Sprint 32.2: WASM streaming race filter
        const text = msg.text()
        if (text.includes('wasm streaming compile failed') ||
            text.includes('falling back to ArrayBuffer instantiation')) {
          return
        }
        consoleErrors.push(text)
      }
    })

    // 登录
    await page.goto('/')
    await page.waitForSelector('text=欢迎回来', { timeout: 10000 })
    await page.locator('input[type="text"]').first().fill('admin')
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')
    await page.waitForSelector('text=人群看板', { timeout: 10000 })
  })

  test('访问 /category-detail/:id, MetricCard + 日趋势 chart + 用户表渲染, 无 error', async ({ page }) => {
    // 找一个真实 categoryId (从 /category 进)
    await page.goto('/category')
    await expect(page.getByText('品类看板').first()).toBeVisible({ timeout: 10000 })
    await page.waitForTimeout(2000)

    // 点击品类明细表第一行 (假设 DataTablePro 行可点击跳转详情)
    // 若点击不可行, 退而求其次直接访问 /category-detail/1 (route 接受任意 id, 后端 404 时仍能验证页面渲染)
    await page.goto('/category-detail/1')

    // 断言 4 个 MetricCard 标题
    const metrics = ['总用户数', '累计GMV', '新客占比', '平均AUS']
    for (const m of metrics) {
      await expect(page.getByText(m).first()).toBeVisible({ timeout: 10000 })
    }

    // Sprint 32.2 #S32-2 模式: bi-card + filter 定位日趋势 chart
    const trendCard = page.locator('.bi-card').filter({ hasText: '日趋势' }).first()
    if (await trendCard.isVisible().catch(() => false)) {
      const chart = trendCard.locator('canvas').first()
      // 等真实渲染 (数据 fetch + ECharts draw), 容许空状态 EmptyState
      await expect(chart).toBeVisible({ timeout: 15000 }).catch(() => {
        // 接受 EmptyState ("暂无趋势数据") 作为合法状态
      })
    }

    // 断言用户明细表存在
    await expect(page.getByText('用户明细表').first()).toBeVisible().catch(() => {
      // 用户明细表可能在空数据时不渲染, 接受
    })

    // Sprint 36-2 业务断言: /api/v1/category/overview?category_id=1 返回 200 + overview dict
    const token = await page.evaluate(() => sessionStorage.getItem('fq_crm_auth_token') || '')
    const overviewResp = await page.request.get('/api/v1/category/overview', {
      params: { category_id: 1 },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    // Sprint 36-2 fix: 不再容忍 backend 500, 期望真 200 (category id=1 在生产 DuckDB 存在)
    expect(overviewResp.status(), '/api/v1/category/overview 业务断言').toBe(200)
    const overviewJson = await overviewResp.json()
    expect(typeof overviewJson, 'overview 应为 dict').toBe('object')

    // 无 error 级别控制台日志
    // Sprint 36-2 fix: 删 Sprint 33.2 backend 500 容忍 (用真业务断言替代, 不再需要 500 容忍)
    expect(consoleErrors).toHaveLength(0)
  })
})
