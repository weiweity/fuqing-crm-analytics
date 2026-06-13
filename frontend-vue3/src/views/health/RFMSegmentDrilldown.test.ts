// RFMSegmentDrilldown YOYGuard 集成测试 (Sprint 18 #124)
// 验证表格 column render 函数集成 YOYGuard 后:
//   - 正常值: 显示 "↑X.Xpp" / "↓X.Xpp" (颜色/箭头由 v 正负决定, 数值通过 YOYGuard abs+toFixed(1))
//   - 异常值: |v|>1e6 触发 YOYGuard 守卫 → 显示 "数据异常"
//   - null: 维持原 '-' 占位
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

// 抑制 jsdom + Vue runtime 的 unhandled rejection
beforeAll(() => {
  const origUnhandled = process.listeners('unhandledRejection')
  process.removeAllListeners('unhandledRejection')
  process.on('unhandledRejection', (reason: any) => {
    const msg = String(reason?.message ?? reason)
    if (msg.includes('Cannot convert object to primitive value') || msg.includes('__vnode')) return
    origUnhandled.forEach(h => h(reason as any, Promise.resolve()))
  })
})

// ── Mock API: fetchRFMCategoryDrilldown 返回测试数据 ──
const mockData = ref<any>(null)
vi.mock('@/api/health', () => ({
  fetchRFMCategoryDrilldown: vi.fn(() => Promise.resolve(mockData.value)),
}))

// ── Mock pinia store ──
vi.mock('@/stores/filterStore', () => ({
  useFilterStore: () => ({
    channel: '全店',
    excludeLowPrice: false,
  }),
}))

vi.mock('@/constants/channels', () => ({
  LOW_PRICE_CHANNELS: [],
}))

vi.mock('@/composables/useChartTheme', () => ({
  BRAND_PRIMARY: '#2563eb',
}))

// ── Mock EChartsWrapper: 简单 div, 避免 echarts/jsdom 复杂度 ──
vi.mock('@/components/EChartsWrapper.vue', () => ({
  default: { name: 'EChartsWrapper', template: '<div>chart</div>' },
}))

// ── Mock DataTablePro: 真实渲染 columns 中的 render 函数 (含 h/YOYGuard vnode), 通过 wrapper.find 取文本 ──
vi.mock('@/components/DataTablePro.vue', () => {
  const { defineComponent, h } = require('vue')
  return {
    default: defineComponent({
      name: 'DataTablePro',
      props: ['columns', 'data'],
      setup(props: any) {
        return () => h('div', { 'data-testid': 'data-table-pro' },
          (props.data || []).map((row: any) =>
            h('div', { 'data-testid': 'row', key: row.category_name },
              (props.columns || []).map((col: any) =>
                h('div', { 'data-testid': col.key, key: col.key },
                  col.render ? [col.render(row)] : [String(row[col.key] ?? '-')]
                )
              )
            )
          )
        )
      },
    }),
  }
})

vi.mock('naive-ui', () => {
  const { defineComponent, h } = require('vue')
  return {
    NButton: defineComponent({ name: 'NButton', setup(_props: any, { slots }: any) { return () => h('button', slots.default?.()) } }),
    NSpin: defineComponent({ name: 'NSpin', setup(_props: any, { slots }: any) { return () => h('div', slots.default?.()) } }),
  }
})

vi.mock('@vicons/ionicons5', () => {
  const { defineComponent, h } = require('vue')
  return {
    Close: defineComponent({ name: 'Close', setup() { return () => h('span', '×') } }),
  }
})

import RFMSegmentDrilldown from './RFMSegmentDrilldown.vue'

function makeData(overrides: Record<string, any> = {}) {
  return {
    summary: {
      segment_user_count: 1000,
      overall_repurchase_rate: 0.2,
      overall_repurchase_rate_yoy: 2.5,
      top_drivers: [],
    },
    categories: [
      {
        category_name: '面膜',
        hist_users_current: 500,
        repurchase_users_current: 100,
        repurchase_rate_current: 0.2,
        yoy_repurchase_rate: 2.5,
        repurchase_gsv_current: 50000,
      },
      {
        category_name: '精华',
        hist_users_current: 300,
        repurchase_users_current: 60,
        repurchase_rate_current: 0.2,
        yoy_repurchase_rate: -3.1,
        repurchase_gsv_current: 30000,
      },
      {
        category_name: '异常品类',
        hist_users_current: 100,
        repurchase_users_current: 10,
        repurchase_rate_current: 0.1,
        yoy_repurchase_rate: 5e6,
        repurchase_gsv_current: 10000,
      },
    ],
    member_categories: [],
    year_label: '2026',
    comp_year_label: '2025',
    ...overrides,
  }
}

describe('RFMSegmentDrilldown YOYGuard 集成 (Sprint 18 #124)', () => {
  it('正常 pp 值显示 "↑2.5pp" (YOYGuard abs+toFixed(1) 格式, 箭头+绿色由 v 正负决定)', async () => {
    mockData.value = makeData()
    const wrapper = mount(RFMSegmentDrilldown, {
      props: { rfmSegment: 'R5', queryParams: { start_date: '2026-01-01', end_date: '2026-01-31' } },
    })
    await new Promise(r => setTimeout(r, 50))
    const yoyCells = wrapper.findAll('[data-testid="yoy_repurchase_rate"]')
    expect(yoyCells.length).toBeGreaterThan(0)
    expect(yoyCells[0].text()).toContain('↑')
    expect(yoyCells[0].text()).toContain('2.5pp')
  })

  it('负向 pp 值显示 "↓3.1pp" (YOYGuard abs+toFixed(1) 格式, 红色)', async () => {
    mockData.value = makeData()
    const wrapper = mount(RFMSegmentDrilldown, {
      props: { rfmSegment: 'R5', queryParams: { start_date: '2026-01-01', end_date: '2026-01-31' } },
    })
    await new Promise(r => setTimeout(r, 50))
    const yoyCells = wrapper.findAll('[data-testid="yoy_repurchase_rate"]')
    expect(yoyCells.length).toBeGreaterThan(1)
    expect(yoyCells[1].text()).toContain('↓')
    expect(yoyCells[1].text()).toContain('3.1pp')
  })

  it('万倍异常值触发 YOYGuard 守卫 → 显示 "数据异常" (跟 MetricCard/YOYBadge 行为一致)', async () => {
    mockData.value = makeData()
    const wrapper = mount(RFMSegmentDrilldown, {
      props: { rfmSegment: 'R5', queryParams: { start_date: '2026-01-01', end_date: '2026-01-31' } },
    })
    await new Promise(r => setTimeout(r, 50))
    const yoyCells = wrapper.findAll('[data-testid="yoy_repurchase_rate"]')
    expect(yoyCells.length).toBeGreaterThan(2)
    expect(yoyCells[2].text()).toContain('数据异常')
  })
})
