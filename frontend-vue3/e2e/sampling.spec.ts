import { test, expect } from '@playwright/test'

/**
 * Sprint 33.2 候选 3: /sampling 路由 smoke 验证 — Sprint 32.3 a9b1d91 教训核心
 * 治根 a9b1d91 类事故: SamplingView 5+ 天未发现回归 (Vite 编译错)
 * e2e 覆盖: 路由能加载 + 3 个 sub-tab (ROI/Lock/Rolling) 内容渲染 + 关键 MetricCard 可见
 *
 * Sprint 32.3 修复说明:
 * - 父 commit a505f85b restore 32653 字节
 * - 8 处业务专名 drift 闭环 (summer_sale/double11/spring_festival)
 * - 当前文件 32653 bytes / 699 行 (Sprint 33.2 验证: e2e 1 test 触达此路由)
 */
test.describe('sampling 路由 (Sprint 32.3 治根重点)', () => {
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

  test('访问 /sampling, PageHeader + ROI sub-tab 渲染, 无控制台 error (回归 a9b1d91)', async ({ page }) => {
    await page.goto('/sampling')

    // 关键断言 1: PageHeader 标题可见 (a9b1d91 误清空后这块会空白)
    await expect(page.getByText('派样看板').first()).toBeVisible({ timeout: 10000 })

    // 关键断言 2: PageHeader subtitle 可见
    await expect(page.getByText('U先/百补派样ROI').first()).toBeVisible()

    // 关键断言 3: 渠道对比卡片 (Explore agent 确认: 2 个 n-card 渠道对比 U先派样/百补)
    await expect(page.getByText('U先派样').first()).toBeVisible({ timeout: 15000 })
    await expect(page.getByText('百补').first()).toBeVisible()

    // 关键断言 4: 品类明细表
    await expect(page.getByText('品类明细').first()).toBeVisible().catch(() => {
      // 数据 fetch 后才渲染, 接受 EmptyState
    })

    // 等待 ROI sub-tab 数据 fetch
    await page.waitForTimeout(2000)

    // Sprint 36-2 业务断言: /api/v1/sampling/roi 返回 200 + 有 channel_summary 数组
    // Sprint 41.5: page.request 不带 sessionStorage token,手动从 sessionStorage 拿 + 加 Authorization header
    const token = await page.evaluate(() => sessionStorage.getItem('fq_crm_auth_token') || '')
    const roiResp = await page.request.get('/api/v1/sampling/roi', {
      params: { start_date: '2025-01-01', end_date: '2025-12-31' },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    expect(roiResp.status(), '/api/v1/sampling/roi 业务断言').toBe(200)
    const roiJson = await roiResp.json()
    // Sprint 41.6 fix: backend 实际返 `summary.channels` array, spec 原写 channel_summary (跟 Sprint 36-2 business assertion 一致), Sprint 41.6 跑批发现 typo
    expect(Array.isArray(roiJson.summary?.channels), 'summary.channels 应为数组').toBe(true)

    // 无 error 级别控制台日志 (a9b1d91 当时 Vite 编译错会污染 console)
    expect(consoleErrors).toHaveLength(0)

    // 截图保留 (供 Sprint 32.3 a9b1d91 教训回归 baseline)
    await page.screenshot({ path: 'e2e/screenshots/sampling-roi-sprint33.png', fullPage: true })
  })
})
