import { test, expect } from '@playwright/test'

/**
 * Sprint 33.2 候选 3: /market-focus 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * MarketFocusView 是容器, 0 API call, 4 sub-tab lazy load
 */
test.describe('market-focus 路由', () => {
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
    await page.waitForSelector('text=欢迎回来', { timeout: 30000 })
    await page.locator('input[type="text"]').first().fill('admin')
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')
    await page.waitForSelector('text=人群看板', { timeout: 30000 })
  })

  test('访问 /market-focus, 4 个 sub-tab 渲染, 无控制台 error', async ({ page }) => {
    await page.goto('/market-focus')

    // 断言 PageHeader 标题
    await expect(page.getByText('市场对焦').first()).toBeVisible({ timeout: 30000 })

    // 断言 4 个 sub-tab names (Explore agent 提取)
    const tabNames = ['核心单品新老客', '全店资产', '单品资产', '单品资产-其他']
    for (const name of tabNames) {
      await expect(page.getByText(name).first()).toBeVisible()
    }

    // 等待 sub-tab 默认加载
    await page.waitForTimeout(2000)

    // 无 error 级别控制台日志
    expect(consoleErrors).toHaveLength(0)
  })
})
