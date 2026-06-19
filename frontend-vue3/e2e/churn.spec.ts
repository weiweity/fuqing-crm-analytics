import { test, expect } from '@playwright/test'

/**
 * Sprint 33.2 候选 3: /churn 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * 注意: ChurnView 顶部有 "待优化更新" 重构遮罩 (Sprint 当前未启用功能),
 *       e2e 断言 PageHeader + 遮罩文字存在 (重构中状态), 跳过 chart 渲染断言
 */
test.describe('churn 路由', () => {
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

  test('访问 /churn, PageHeader + 重构遮罩存在, 无控制台 error', async ({ page }) => {
    await page.goto('/churn')

    // 断言 PageHeader 标题
    await expect(page.getByText('流失分析').first()).toBeVisible({ timeout: 30000 })

    // 断言重构遮罩 (Explore agent 确认: 全屏覆盖, 含"待优化更新")
    await expect(page.getByText('待优化更新').first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('该模块正在重构中').first()).toBeVisible()

    // 无 error 级别控制台日志 (遮罩不应该报错)
    expect(consoleErrors).toHaveLength(0)
  })
})
