import { test as base, expect, Page } from '@playwright/test'

/**
 * Sprint 51: 共享登录 fixture
 * 2026-07-19 tech-debt: 登录默认跳 /audience（LoginView），勿死等「品类看板」正文。
 * 成功条件 = 离开 /login + 侧栏/壳层出现任一业务菜单文案。
 */
export const test = base.extend<{ authenticatedPage: Page; consoleErrors: string[] }>({
  consoleErrors: async ({}, use) => {
    await use([])
  },

  authenticatedPage: async ({ page, consoleErrors }, use) => {
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

    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) {
        consoleErrors.push(`API ${response.status()}: ${response.url()}`)
      }
    })

    await page.goto('/')
    await page.waitForSelector('text=欢迎回来', { timeout: 30000 })
    await page.locator('input[type="text"]').first().fill('admin')
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')

    // 登录成功：离开 login（默认 redirect /audience）
    await page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 30000,
    })

    // 壳层菜单（NavBar）至少有一个业务入口
    await expect(
      page.getByText(/人群看板|品类看板|老客分析|访客看板/).first(),
    ).toBeVisible({ timeout: 30000 })

    await use(page)
  },
})

export { expect }
