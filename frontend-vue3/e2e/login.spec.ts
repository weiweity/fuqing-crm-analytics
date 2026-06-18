import { test, expect } from '@playwright/test'

/**
 * Sprint 33.2 候选 3: /login 路由 smoke 验证
 * 治根 a9b1d91 类事故: e2e 覆盖 11/11 view routes
 * /login 关键: form 可见 + 提交跳转
 */
test.describe('login 路由', () => {
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
  })

  test('访问 / 显示登录表单，提交后跳转到 /audience', async ({ page }) => {
    await page.goto('/login')

    // 断言 form 元素可见 (Sprint 33.2 fix: getByText strict mode 加 .first(), 跟其他 spec 一致)
    await expect(page.getByText('欢迎回来').first()).toBeVisible({ timeout: 10000 })
    await expect(page.locator('input[type="text"]').first()).toBeVisible()
    await expect(page.locator('input').nth(1)).toBeVisible()
    await expect(page.locator('button:has-text("登 录")')).toBeVisible()

    // 提交登录
    await page.locator('input[type="text"]').first().fill('admin')
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')

    // 断言跳转后导航栏出现 (登录成功标志)
    await page.waitForSelector('text=人群看板', { timeout: 10000 })
    await expect(page).toHaveURL(/\/audience/)

    // 无 error 级别控制台日志
    expect(consoleErrors).toHaveLength(0)
  })
})
