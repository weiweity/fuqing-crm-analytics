import { test, expect } from '@playwright/test'

test.describe('customer-health 路由', () => {
  const consoleErrors: string[] = []

  test.beforeEach(async ({ page }) => {
    consoleErrors.length = 0
    page.on('console', (msg) => {
      // 过滤 ECharts cosmetic warn，只收集 error
      if (msg.type() === 'error') {
        // Sprint 32.2: 过滤 WASM streaming race 网络瞬态 (跟 audience-daily-trend 同根因)
        // "wasm streaming compile failed" / "falling back to ArrayBuffer instantiation"
        // 是 dev server 启动首次加载 DuckDB-WASM 时的 race, e2e 跨页面状态泄漏到 console,
        // 不影响业务逻辑, 但污染 consoleErrors 断言.
        const text = msg.text()
        if (text.includes('wasm streaming compile failed') ||
            text.includes('falling back to ArrayBuffer instantiation')) {
          return
        }
        consoleErrors.push(text)
      }
    })

    // 登录：访问登录页面，输入账号密码
    await page.goto('/')
    await page.waitForSelector('text=欢迎回来', { timeout: 30000 })
    // 账号输入框（第一个 input）
    await page.locator('input[type="text"]').first().fill('admin')
    // 密码输入框（第二个 input）
    await page.locator('input').nth(1).fill('123456')
    await page.click('button:has-text("登 录")')
    // 等待登录成功（跳转到 /audience 或出现导航菜单）
    await page.waitForSelector('text=人群看板', { timeout: 30000 })
  })

  test('导航到 customer-health，6个Tab正常渲染，无控制台 error', async ({ page }) => {
    await page.goto('/customer-health')

    // 断言6个Tab存在（naive-ui NTabs 渲染）
    const tabNames = ['现状概览', 'RFM分析', 'R区间分析', 'F区间分析', 'M区间分析', '复购周期']
    for (const name of tabNames) {
      await expect(page.getByText(name).first()).toBeVisible()
    }

    // 等待数据加载（现状概览默认激活）
    await page.waitForTimeout(3000)

    // 断言无 error 级别日志
    expect(consoleErrors).toHaveLength(0)
  })

  test('切换 RFM分析 Tab，图表和表格正常渲染', async ({ page }) => {
    await page.goto('/customer-health')

    // 点击 RFM分析 tab
    await page.getByText('RFM分析').first().click()
    await page.waitForTimeout(3000)

    // 断言图表容器存在
    await expect(page.locator('.rfm-analysis-tab')).toBeVisible()

    // 断言表格存在（至少一个 DataTablePro）
    await expect(page.locator('.bi-card').filter({ hasText: 'RFM 人群流转详情' }).first()).toBeVisible()

    // 断言无 error 级别日志
    expect(consoleErrors).toHaveLength(0)

    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/rfm-analysis-tab.png', fullPage: true })
  })
})
