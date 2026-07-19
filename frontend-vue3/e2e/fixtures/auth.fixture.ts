import { test as base, expect, Page } from '@playwright/test'

/**
 * Sprint 51: 共享登录 fixture
 * 2026-07-19 e2e 根治:
 * - 登录默认跳 /audience（LoginView），勿死等「品类看板」正文。
 * - 成功条件 = 离开 /login + 侧栏/壳层出现任一业务菜单文案。
 * - 每个 case 前 POST /api/v1/_test/reset（需后端 FQ_CRM_TEST_MODE=1），
 *   清 L4.85 ACTIVE_TOKENS，避免同账号二次 login 409「申请登录」卡死。
 */
export const test = base.extend<{ authenticatedPage: Page; consoleErrors: string[] }>({
  consoleErrors: async ({}, use) => {
    await use([])
  },

  authenticatedPage: async ({ page, consoleErrors, request }, use) => {
    // 必须在任何导航前注入：page.goto 触发 beforeunload 时跳过 sendBeacon logout
    await page.addInitScript(() => {
      sessionStorage.setItem('fq_crm_e2e', '1')
    })

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

    // e2e 根治: 清后端会话（失败不抛 — 非 TEST_MODE 本地可走 TEST_MODE login kick）
    await request.post('/api/v1/_test/reset').catch(() => null)

    await page.goto('/')
    await page.waitForSelector('text=欢迎回来', { timeout: 30000 })
    await page.locator('input[type="text"]').first().fill('admin')
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')

    // 登录成功：离开 login（默认 redirect /audience）
    // 若仍停在 login 且出现「申请登录」，说明 reset/TEST_MODE 未生效
    await page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 30000,
    })

    // 壳层菜单（NavBar）至少有一个业务入口
    await expect(
      page.getByText(/人群看板|品类看板|老客分析|派样看板|市场对焦/).first(),
    ).toBeVisible({ timeout: 30000 })

    await use(page)
  },
})

export { expect }
