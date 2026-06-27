import { test, expect } from './fixtures/auth.fixture'

test.describe('customer-health 路由', () => {
  test('导航到 customer-health，6个Tab正常渲染，无控制台 error', async ({ authenticatedPage: page, consoleErrors }) => {
    await page.goto('/customer-health')

    // 断言6个Tab存在（naive-ui NTabs 渲染）
    const tabNames = ['现状概览', 'RFM分析', 'R区间分析', 'F区间分析', 'M区间分析', '复购周期']
    for (const name of tabNames) {
      await expect(page.getByText(name).first()).toBeVisible()
    }

    // 等待数据加载（现状概览默认激活） (Sprint 43 #S43-2: 删冗余 waitForTimeout, expect tab 已 wait)

    // 断言无 error 级别日志
    expect(consoleErrors).toHaveLength(0)
  })

  test('切换 RFM分析 Tab，图表和表格正常渲染', async ({ authenticatedPage: page, consoleErrors }) => {
    await page.goto('/customer-health')

    // 点击 RFM分析 tab
    await page.getByText('RFM分析').first().click()
    // Sprint 43 #S43-2: 删冗余 waitForTimeout, 下面 expect .rfm-analysis-tab 自己 wait

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
