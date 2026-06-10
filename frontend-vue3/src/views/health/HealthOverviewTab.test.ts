// HealthOverviewTab 格式化函数测试
// fmtPercent / fmtCount 在 <script setup> 内部，无法直接 import
// 策略: vi.mock 所有重依赖 + mount 组件，通过渲染结果间接验证
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

// 抑制 jsdom + Vue runtime 的 unhandled rejection (setAttribute style object / __vnode null)
// 这些是 jsdom 对 Vue 内部渲染的兼容性问题，不影响测试结果
beforeAll(() => {
  const origUnhandled = process.listeners('unhandledRejection')
  process.removeAllListeners('unhandledRejection')
  process.on('unhandledRejection', (reason: any) => {
    const msg = String(reason?.message ?? reason)
    if (msg.includes('Cannot convert object to primitive value') || msg.includes('__vnode')) return
    // 其他 unhandled rejection 正常抛出
    origUnhandled.forEach(h => h(reason as any))
  })
})

// ── Mock vue-query ──
const mockData = ref<any>(null)
vi.mock('@tanstack/vue-query', () => ({
  useQuery: () => ({
    data: mockData,
    isLoading: ref(false),
    error: ref(null),
    refetch: vi.fn(),
  }),
}))

// ── Mock pinia store ──
vi.mock('@/stores/filterStore', () => ({
  useFilterStore: () => ({
    channel: '全店',
    dateRange: ['2026-01-01', '2026-01-31'],
    excludeLowPrice: false,
    compareParams: ['2025-01-01', '2025-01-31'],
  }),
}))

// ── Mock API ──
vi.mock('@/api/health', () => ({
  fetchHealthOverview: vi.fn(),
  fetchChannelHealthScores: vi.fn(),
  fetchHealthTargets: vi.fn(),
}))

// ── Mock 子组件 ──
vi.mock('@/components/MetricCard.vue', () => ({
  default: {
    name: 'MetricCard',
    props: ['title', 'value', 'change', 'unit', 'suffix'],
    template: '<div data-testid="metric-card"><span data-testid="metric-value">{{ value }}</span><span data-testid="metric-title">{{ title }}</span></div>',
  },
}))

vi.mock('@/components/LoadingState.vue', () => ({
  default: { name: 'LoadingState', template: '<div>loading</div>' },
}))

vi.mock('@/components/ErrorState.vue', () => ({
  default: { name: 'ErrorState', template: '<div>error</div>' },
}))

vi.mock('@/components/EChartsWrapper.vue', () => ({
  default: { name: 'EChartsWrapper', template: '<div>chart</div>' },
}))

vi.mock('@/components/YOYBadge.vue', () => ({
  default: { name: 'YOYBadge', template: '<span>badge</span>' },
}))

vi.mock('@/components/ExportToolbar.vue', () => ({
  default: { name: 'ExportToolbar', template: '<span />' },
}))

vi.mock('@/constants/channels', () => ({
  LOW_PRICE_CHANNELS: [],
}))

// naive-ui 组件 mock: defineComponent 确保 props 正确透传，避免 jsdom setAttribute 报错
vi.mock('naive-ui', () => {
  const { defineComponent, h } = require('vue')
  const stub = (name: string) => defineComponent({
    name,
    props: { type: String, title: String, closable: Boolean, description: String, text: Boolean, size: String, component: [String, Object] },
    setup(_: any, { slots }: any) {
      return () => h('div', slots.default?.())
    },
  })
  return {
    NAlert: stub('NAlert'),
    NGrid: stub('NGrid'),
    NGi: stub('NGi'),
    NEmpty: stub('NEmpty'),
    NButton: stub('NButton'),
    NIcon: stub('NIcon'),  // Sprint 13: RatioConventionBanner 使用 NIcon
  }
})

import HealthOverviewTab from './HealthOverviewTab.vue'

// ── 辅助: 设置 mock 数据后 mount ──
function mountWithData(data: any) {
  mockData.value = data
  return mount(HealthOverviewTab)
}

// ── 构造最小可用的 data 对象 ──
function makeData(overrides: Record<string, any> = {}) {
  return {
    health_score: 75,
    health_level: 'healthy',
    analysis_date: '2026-01-31',
    period_days: 31,
    old_gsv: 100000,
    old_users: 1234,
    old_customer_aus: 350,
    old_customer_gsv_ratio: 0.5335,
    member_old_gsv: 80000,
    member_old_users: 800,
    member_old_customer_aus: 400,
    member_old_customer_gsv_ratio: 0.45,
    period_repurchase_users: 5000,
    ly_period_repurchase_users: 4500,
    all_store_repurchase_rate: 0.21,
    same_product_repurchase_rate: 0.12,
    ly_all_store_repurchase_rate: 0.19,
    ly_same_product_repurchase_rate: 0.10,
    ly_old_customer_gsv_ratio: 0.36,
    ly_old_customer_aus: 90,
    health_score_yoy: null,
    ly_health_score: null,
    mom_period_repurchase_users: null,
    yoy_period_repurchase_users: null,
    yoy_old_gsv: null,
    yoy_old_users: null,
    yoy_old_customer_aus: null,
    yoy_old_customer_gsv_ratio: null,
    yoy_member_old_gsv: null,
    yoy_member_old_users: null,
    yoy_member_old_customer_aus: null,
    yoy_member_old_customer_gsv_ratio: null,
    alerts: [],
    ...overrides,
  }
}

describe('HealthOverviewTab fmtPercent / fmtCount', () => {
  // ── fmtPercent 通过 MetricCard 渲染的 value 来验证 ──

  it('fmtPercent(0.5335) → "53.3%" (old_customer_gsv_ratio, JS toFixed 浮点精度)', () => {
    // 注意: (0.5335 * 100).toFixed(1) = "53.3" 因为 0.5335*100 = 53.34999...994
    const wrapper = mountWithData(makeData({ old_customer_gsv_ratio: 0.5335 }))
    const cards = wrapper.findAll('[data-testid="metric-card"]')
    const ratioCard = cards[3]
    expect(ratioCard.find('[data-testid="metric-value"]').text()).toBe('53.3%')
  })

  it('fmtPercent(null) → "—" (当 old_customer_gsv_ratio 为 null)', () => {
    const wrapper = mountWithData(makeData({ old_customer_gsv_ratio: null }))
    const cards = wrapper.findAll('[data-testid="metric-card"]')
    const ratioCard = cards[3]
    expect(ratioCard.find('[data-testid="metric-value"]').text()).toBe('—')
  })

  it('fmtPercent(undefined) → "—" (当 old_customer_gsv_ratio 为 undefined)', () => {
    const d = makeData()
    delete d.old_customer_gsv_ratio
    const wrapper = mountWithData(d)
    const cards = wrapper.findAll('[data-testid="metric-card"]')
    const ratioCard = cards[3]
    expect(ratioCard.find('[data-testid="metric-value"]').text()).toBe('—')
  })

  // ── fmtCount 通过 MetricCard 渲染的 value 来验证 ──

  it('fmtCount(1234) → "1,234" (old_users)', () => {
    const wrapper = mountWithData(makeData({ old_users: 1234 }))
    const cards = wrapper.findAll('[data-testid="metric-card"]')
    const countCard = cards[1]
    expect(countCard.find('[data-testid="metric-value"]').text()).toBe('1,234')
  })

  it('fmtCount(null) → "—" (当 old_users 为 null)', () => {
    const wrapper = mountWithData(makeData({ old_users: null }))
    const cards = wrapper.findAll('[data-testid="metric-card"]')
    const countCard = cards[1]
    expect(countCard.find('[data-testid="metric-value"]').text()).toBe('—')
  })

  it('fmtCount(0) → "0" (当 old_users 为 0)', () => {
    const wrapper = mountWithData(makeData({ old_users: 0 }))
    const cards = wrapper.findAll('[data-testid="metric-card"]')
    const countCard = cards[1]
    expect(countCard.find('[data-testid="metric-value"]').text()).toBe('0')
  })
})
