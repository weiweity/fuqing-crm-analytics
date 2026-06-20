import { test, expect } from './fixtures/auth.fixture'

test.describe('visitor 路由', () => {
  test('访问 /visitor，访客指标与导航正常渲染，无控制台 error', async ({
    authenticatedPage: page,
    consoleErrors,
  }) => {
    await page.goto('/visitor')

    await expect(page).toHaveURL(/\/visitor$/)
    await expect(page.getByRole('link', { name: '访客看板' })).toBeVisible()
    await expect(page.getByRole('link', { name: '访客看板' })).toHaveClass(/sidebar-nav-item--active/)
    await expect(page.getByText('访客数').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('会员入会率').first()).toBeVisible()
    await expect(page.getByText('入会趋势').first()).toBeVisible()
    expect(consoleErrors).toHaveLength(0)
  })
})
