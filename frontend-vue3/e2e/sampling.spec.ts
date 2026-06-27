import { test, expect } from './fixtures/auth.fixture'

/**
 * Sprint 33.2 候选 3: /sampling 路由 smoke 验证 — Sprint 32.3 a9b1d91 教训核心
 * Sprint 60.3 C+: 降级为纯 UI smoke。CI runner 无 production DuckDB，
 * 去掉 /api/v1/sampling/roi 业务断言，只验证路由/关键文案/无报错。
 */
test.describe('sampling 路由 (Sprint 32.3 治根重点)', () => {
  test.setTimeout(30000)

  test('访问 /sampling, PageHeader + ROI 文案渲染, 无控制台/API error (回归 a9b1d91)', async ({ authenticatedPage: page, consoleErrors }) => {
    // Sprint 60.3+ C+: CI 用 schema-only DB，sampling API 在空数据下会超时/500；mock 成合法空响应
    await page.route('/api/v1/sampling/**', async (route) => {
      const url = route.request().url()
      let body = '{}'
      if (url.includes('/roi')) {
        body = JSON.stringify({
          summary: {
            channels: [
              {
                channel: 'U先派样',
                sample_users: 1000,
                repurchase_users_7d: 120,
                repurchase_users_30d: 300,
                repurchase_users_60d: 360,
                repurchase_rate_7d: 0.12,
                repurchase_rate_30d: 0.3,
                repurchase_rate_60d: 0.36,
                repurchase_gsv_7d: 26000,
                repurchase_gsv_30d: 80000,
                repurchase_gsv_60d: 98000,
                repurchase_aus_7d: 216,
                repurchase_aus_30d: 267,
                repurchase_aus_60d: 272,
                full_repurchase_users_30d: 120,
                full_repurchase_gsv_30d: 50000,
                full_repurchase_aus_30d: 416,
                full_repurchase_rate_30d: 0.12,
                full_repurchase_users_60d: 160,
                full_repurchase_gsv_60d: 68000,
                full_repurchase_aus_60d: 425,
                nonfull_repurchase_users_30d: 180,
                nonfull_repurchase_gsv_30d: 30000,
                nonfull_repurchase_aus_30d: 166,
              },
            ],
          },
          category_breakdown: [
            {
              channel: 'U先派样',
              category: '次抛精华',
              sample_users: 500,
              repurchase_users: 100,
              repurchase_rate: 0.2,
              repurchase_gsv: 42000,
              repurchase_aus: 420,
              same_category_repurchase: 60,
              same_category_rate: 0.12,
              full_repurchase_users: 40,
              full_repurchase_rate: 0.08,
              full_repurchase_gsv: 20000,
              full_repurchase_aus: 500,
              nonfull_repurchase_users: 60,
              nonfull_repurchase_gsv: 22000,
              nonfull_repurchase_aus: 367,
            },
          ],
          time_range: { start: '2026-05-01', end: '2026-05-31', window_days: 30 },
          period_distribution: {
            bucket_1_3d: 30,
            bucket_4_7d: 60,
            bucket_8_30d: 150,
            bucket_31_60d: 60,
            full_bucket_1_3d: 10,
            full_bucket_4_7d: 20,
            full_bucket_8_30d: 60,
            full_bucket_31_60d: 30,
          },
          quality_flags: [],
        })
      } else if (url.includes('/lock-analysis')) {
        body = JSON.stringify({
          campaign_info: { year: 2026, campaign_name: '' },
          current_year: { total_uv: 0, locked_users: 0, lock_rate: 0, converted_users: 0, conversion_rate: 0, lock_gsv: 0, lock_aus: 0, new_locked_users: 0, new_locked_ratio: 0, new_converted_users: 0, new_conversion_rate: 0, new_lock_gsv: 0, new_lock_aus: 0 },
          last_year: { total_uv: 0, locked_users: 0, lock_rate: 0, converted_users: 0, conversion_rate: 0, lock_gsv: 0, lock_aus: 0, new_locked_users: 0, new_locked_ratio: 0, new_converted_users: 0, new_conversion_rate: 0, new_lock_gsv: 0, new_lock_aus: 0 },
          yoy: {},
        })
      } else if (url.includes('/rolling-comparison')) {
        body = JSON.stringify({
          year_a: { phase: '', total_uv: 0, locked_users: 0, lock_rate: 0, new_locked_users: 0, new_locked_ratio: 0, old_locked_users: 0, old_locked_ratio: 0, converted_users: 0, conversion_rate: 0, conv_gsv: 0, conv_aus: 0, new_converted_users: 0, new_conversion_rate: 0, new_conv_gsv: 0, new_conv_aus: 0, old_converted_users: 0, old_conversion_rate: 0 },
          year_b: { phase: '', total_uv: 0, locked_users: 0, lock_rate: 0, new_locked_users: 0, new_locked_ratio: 0, old_locked_users: 0, old_locked_ratio: 0, converted_users: 0, conversion_rate: 0, conv_gsv: 0, conv_aus: 0, new_converted_users: 0, new_conversion_rate: 0, new_conv_gsv: 0, new_conv_aus: 0, old_converted_users: 0, old_conversion_rate: 0 },
          yoy: {},
          timeline: { year_a_sample_start: '', year_a_sample_end: '', year_a_conv_start: '', year_b_sample_start: '', year_b_sample_end: '', year_b_conv_start: '', rolling_end: '', year_b_equiv_end: '', T: 0, T_sample_a: 0, T_sample_b: 0, T_conv: 0 },
        })
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body })
    })

    await page.goto('/sampling')

    // 关键断言 1: PageHeader 标题可见 (a9b1d91 误清空后这块会空白)
    await expect(page.getByText('派样看板').first()).toBeVisible({ timeout: 30000 })

    // 关键断言 2: PageHeader subtitle 可见
    await expect(page.getByText('U先/百补派样ROI').first()).toBeVisible()

    // Sprint 139: 4 KPI 卡 + 正装拆分真值断言
    await expect(page.getByText('派样人数').first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('任意回购人数').first()).toBeVisible()
    await expect(page.getByText('正装回购人数').first()).toBeVisible()
    await expect(page.getByText('正装转化率').first()).toBeVisible()

    // 关键断言 3: 渠道对比卡片 + 正装/非正装 split
    await expect(page.getByText('U先派样').first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText(/正装回购 \(spu_type='正装'\)/).first()).toBeVisible()
    await expect(page.getByText('非正装回购').first()).toBeVisible()

    // 关键断言 4: 品类明细表新增正装列
    await expect(page.getByText('品类回购明细').first()).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('正装回购率').first()).toBeVisible()

    // 关键断言 5: 周期分布图
    await expect(page.getByText('回购周期分布').first()).toBeVisible({ timeout: 5000 })

    // 无 console error 与 API 5xx (a9b1d91 当时 Vite 编译错会污染 console)
    expect(consoleErrors).toHaveLength(0)

    // 截图保留 (供 Sprint 32.3 a9b1d91 教训回归 baseline)
    await page.screenshot({ path: 'e2e/screenshots/sampling-roi-sprint33.png', fullPage: true })
  })
})
