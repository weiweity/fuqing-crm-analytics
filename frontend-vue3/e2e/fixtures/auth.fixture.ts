import { test as base, expect, Page } from '@playwright/test'

/**
 * Sprint 51: 共享登录 fixture — 消除 9 个 spec 文件的登录 boilerplate 重复
 *
 * 提供:
 *   authenticatedPage — 已登录的 page (含 WASM console error 过滤)
 *   consoleErrors — 收集的 console error 数组 (可在 test body 中断言)
 *
 * 用法:
 *   import { test, expect } from './fixtures/auth.fixture'
 *   test('my test', async ({ authenticatedPage, consoleErrors }) => {
 *     await authenticatedPage.goto('/some-route')
 *     expect(consoleErrors).toHaveLength(0)
 *   })
 */
export const test = base.extend<{ authenticatedPage: Page; consoleErrors: string[] }>({
  consoleErrors: async ({}, use) => {
    await use([])
  },

  authenticatedPage: async ({ page, consoleErrors }, use) => {
    // WASM filter — 必须在 goto 之前注册 (Sprint 32.2)
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text()
        if (
          text.includes('wasm streaming compile failed') ||
          text.includes('falling back to ArrayBuffer instantiation')
        ) {
          return
        }
        consoleErrors.push(text)
      }
    })

    // Sprint 60.3 C+: 拦截 API 5xx，让 smoke e2e 仍保留后端健康检查能力
    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) {
        consoleErrors.push(`API ${response.status()}: ${response.url()}`)
      }
    })

    // 登录
    await page.goto('/')
    await page.waitForSelector('text=欢迎回来', { timeout: 30000 })
    await page.locator('input[type="text"]').first().fill('admin')
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')
    await page.waitForSelector('text=人群看板', { timeout: 30000 })

    await use(page)
  },
})

export { expect }
