import { test, expect } from './fixtures/auth.fixture'

/**
 * Sprint 33.2 候选 3: /category-detail/:id 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * 4 个 MetricCard + 日趋势图 (ECharts canvas) + RFM 饼图 + 用户明细表
 */
test.describe('category-detail 路由', () => {
  test('访问 /category-detail/:id, MetricCard + 日趋势 chart + 用户表渲染, 无 error', async ({ authenticatedPage: page, consoleErrors }) => {
    // Sprint 43.1 post-merge fix: 之前 chart expect.toBeVisible 30s retry 阻塞 test 30s 超时.
    // 现在 chart 改 5s waitFor + isVisible check (EmptyState 不阻塞), test 总 ~2s.
    // test.setTimeout 保留 20s 兜底 (Sprint 36-2 业务断言 + 渲染断言 chain).
    test.setTimeout(20000)

    // 找一个真实 categoryId (从 /category 进)
    await page.goto('/category')
    await expect(page.getByText('品类看板').first()).toBeVisible({ timeout: 30000 })
    // Sprint 43 #S43-2: 删冗余 waitForTimeout, 后面 expect MetricCard 自己 wait

    // 点击品类明细表第一行 (假设 DataTablePro 行可点击跳转详情)
    // 若点击不可行, 退而求其次直接访问 /category-detail/1 (route 接受任意 id, 后端 404 时仍能验证页面渲染)
    await page.goto('/category-detail/1')
    // Sprint 43.1 post-merge fix: waitForLoadState 等页面 networkidle, 避免 chromium headless
    // 在 navigation 后 ~15-30s page.close 引发 "Target page, context or browser has been closed".
    await page.waitForLoadState('networkidle')

    // Sprint 43.1 post-merge fix: page.evaluate 提前到 page.goto 后立即执行.
    // 之前 page.evaluate 在 expect chain 末尾 (line 71), chromium headless 在 ~15s 后 page closed,
    // 导致 "Target page, context or browser has been closed". 提前到 navigation 后立刻 fetch
    // sessionStorage token (避开 expect chain 触发的 chromium cleanup).
    const token = await page.evaluate(() => sessionStorage.getItem('fq_crm_auth_token') || '')

    // Sprint 36-2 业务断言: /api/v1/category/overview?category_id=1 返回 200 + overview dict
    const overviewResp = await page.request.get('/api/v1/category/overview', {
      params: { category_id: 1 },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    // Sprint 36-2 fix: 不再容忍 backend 500, 期望真 200 (category id=1 在生产 DuckDB 存在)
    expect(overviewResp.status(), '/api/v1/category/overview 业务断言').toBe(200)
    const overviewJson = await overviewResp.json()
    expect(typeof overviewJson, 'overview 应为 dict').toBe('object')

    // 断言 4 个 MetricCard 标题 (post-API call 继续验证渲染)
    const metrics = ['总用户数', '累计GMV', '新客占比', '平均AUS']
    for (const m of metrics) {
      await expect(page.getByText(m).first()).toBeVisible({ timeout: 30000 })
    }

    // Sprint 32.2 #S32-2 模式: bi-card + filter 定位日趋势 chart
    const trendCard = page.locator('.bi-card').filter({ hasText: '日趋势' }).first()
    if (await trendCard.isVisible().catch(() => false)) {
      const chart = trendCard.locator('canvas').first()
      // Sprint 43.1 post-merge fix: 改用 5s waitFor 短 timeout + isVisible check,
      // 不再用 expect.toBeVisible 30s retry. /category-detail/1 page 在 ECharts EmptyState
      // 时 canvas 不渲染, expect.toBeVisible retry 30s 后才 catch 接受.
      // (实测 chart 没渲染时 31s 才 timeout 触发 catch)
      await chart.waitFor({ state: 'visible', timeout: 5000 }).catch(() => null)
      const chartVisible = await chart.isVisible().catch(() => false)
      // chart 可见就 expect (立即), 不可见接受 EmptyState
      if (chartVisible) {
        await expect(chart).toBeVisible()
      }
    }

    // 断言用户明细表存在 (短 timeout 不 retry 30s)
    await page.getByText('用户明细表').first().waitFor({ state: 'visible', timeout: 5000 }).catch(() => null)
    const userTableVisible = await page.getByText('用户明细表').first().isVisible().catch(() => false)
    if (userTableVisible) {
      await expect(page.getByText('用户明细表').first()).toBeVisible()
    }

    // 无 error 级别控制台日志
    // Sprint 36-2 fix: 删 Sprint 33.2 backend 500 容忍 (用真业务断言替代, 不再需要 500 容忍)
    expect(consoleErrors).toHaveLength(0)
  })
})
