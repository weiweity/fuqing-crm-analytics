import { test, expect } from '@playwright/test'

/**
 * Sprint 27 治根 e2e 验证: 人群看板 → 日趋势 → "全店GSV与会员占比" 折线图 tooltip
 *
 * Bug: 治根前 tooltip 显示 5346.0% (×100×100 双 Bug), 期望 53.46% (0.5346 × 100)
 * 治根后:
 *   - service: overview.py:453,461 返 0-1 decimal (不再 ×100)
 *   - contract: TrendData.member_ratios 改 RatioField 0-1
 *   - frontend: tooltip formatter (val * 100).toFixed(1) 保持, val 现在是 0-1
 *   - frontend: Y 轴 max 100 → 1, formatter 加 ×100
 *
 * E2E 断言:
 *   - hover tooltip 后, "会员GSV占比" 行数值在 [0, 100] 区间 (X.X% 格式, 不超过 100)
 *   - 不应出现 "5346" / "4460" / 4位数百分比 (治根前 bug)
 *   - Y 轴右侧标签含 "%" 但不应有 "3500" / "5346" 异常值
 */
test.describe('audience 日趋势会员占比 tooltip', () => {
  const consoleErrors: string[] = []

  test.beforeEach(async ({ page }) => {
    consoleErrors.length = 0
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        // Sprint 32.2: 过滤 WASM streaming race 网络瞬态 (跟 customer-health 同根因)
        // "wasm streaming compile failed" / "falling back to ArrayBuffer instantiation"
        // 是 dev server 启动首次加载 DuckDB-WASM 时的 race, e2e 跨页面状态泄漏到 console,
        // 不影响业务逻辑, 但污染 consoleErrors 断言. 真 e2e 业务错误仍会被捕获.
        const text = msg.text()
        if (text.includes('wasm streaming compile failed') ||
            text.includes('falling back to ArrayBuffer instantiation')) {
          return
        }
        consoleErrors.push(text)
      }
    })

    // 登录 (复用 customer-health.spec.ts 模式)
    await page.goto('/')
    await page.waitForSelector('text=欢迎回来', { timeout: 10000 })
    await page.locator('input[type="text"]').first().fill('admin')
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')
    await page.waitForSelector('text=人群看板', { timeout: 10000 })
  })

  test('日趋势 全店GSV与会员占比 chart tooltip 显示 53.X% (非 5346%)', async ({ page }) => {
    await page.goto('/audience')

    // 等待 "全店GSV" 标题 (图表卡片标题)
    await expect(page.getByText('全店GSV').first()).toBeVisible({ timeout: 10000 })

    // 等待 ECharts canvas 渲染
    await page.waitForTimeout(2000)

    // Sprint 32.2 治根 (债 #S32-2): 用 bi-card + filter 模式定位日趋势 chart container,
    // 避免 page.locator('canvas').first() 选错其它 canvas (e.g. 顶部 stat card sparkline)
    const trendCard = page.locator('.bi-card').filter({ hasText: '日趋势' }).first()
    await expect(trendCard).toBeVisible({ timeout: 10000 })

    // Sprint 32.2: wait for ECharts canvas 真正渲染 (数据 fetch 完 + ECharts 画完).
    // 之前用 waitForTimeout(2000) 太短, data 还没加载完 chart 不存在
    const chart = trendCard.locator('canvas').first()
    await expect(chart).toBeVisible({ timeout: 15000 })

    // Sprint 32.2: 滚动 trend card 到视口中心, 避免 chart 在视口外 hover 不响应
    // ECharts tooltip 默认 append 到 body, 视口外坐标可能不触发 hover
    await trendCard.scrollIntoViewIfNeeded()
    await page.waitForTimeout(500)

    const box = await chart.boundingBox()
    if (!box) throw new Error('日趋势 chart canvas 未找到')

    // hover canvas 中点偏右 (X 轴日期中段, 必有数据)
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5)
    await page.waitForTimeout(500)

    // ECharts tooltip 默认 append 到 body, class 默认包含 'tooltip'
    const tooltip = page.locator('div[style*="position: absolute"]').filter({ hasText: '占比' }).first()
    await expect(tooltip).toBeVisible({ timeout: 5000 })

    const tooltipText = (await tooltip.textContent()) || ''

    // 治根后断言: tooltip 文本不应出现 4 位数百分比 (治根前 bug: 5346.0% 等)
    expect(tooltipText).not.toMatch(/\d{4,}\.\d+%/)  // 5346.0%, 4460.0%, etc.
    expect(tooltipText).not.toContain('5346')
    expect(tooltipText).not.toContain('4460')

    // 治根后断言: "会员GSV占比" 行数值应是 2 位以内百分比 (e.g. 53.5%, 60.0%)
    // 会员占比通常在 30-70% 区间, toFixed(1) 输出形如 "53.5%"
    const ratioMatch = tooltipText.match(/会员GSV占比[\s\S]*?(\d{1,2}(?:\.\d)?)%/)
    expect(ratioMatch).not.toBeNull()
    if (ratioMatch) {
      const pct = parseFloat(ratioMatch[1])
      expect(pct).toBeGreaterThanOrEqual(0)
      expect(pct).toBeLessThanOrEqual(100)
    }

    // 无 error 级别控制台日志
    expect(consoleErrors).toHaveLength(0)

    // 截图保留 (供 Sprint 27 收口佐证)
    await page.screenshot({ path: 'e2e/screenshots/audience-daily-trend-tooltip-sprint27.png', fullPage: true })
  })
})
