import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const overviewData = ref<any>(null)
const distributionData = ref<any>(null)
const repurchaseProps = { categoryOptions: [] as string[], categoryLabels: {} as Record<string, string> }
const flowProps = { categoryOptions: [] as string[], categoryLabels: {} as Record<string, string> }

vi.mock('@tanstack/vue-query', () => ({
  useQuery: ({ queryKey }: { queryKey: { value: unknown[] } }) => {
    const key = Array.isArray(queryKey?.value) ? queryKey.value[0] : queryKey
    if (key === 'category-overview') {
      return { data: overviewData, isLoading: ref(false), error: ref(null), refetch: vi.fn() }
    }
    return { data: distributionData, isLoading: ref(false), error: ref(null), refetch: vi.fn() }
  },
}))

vi.mock('@/stores/filterStore', () => ({
  useFilterStore: () => ({
    channel: '全店',
    dateRange: ['2026-07-06', '2026-09-15'],
    excludeLowPrice: false,
    compareParams: null,
  }),
}))

vi.mock('@/api/category', () => ({
  fetchCategoryOverview: vi.fn(),
  fetchCategoryDistribution: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/category', query: {}, hash: '#risk' }),
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock('naive-ui', () => ({
  NGrid: { name: 'NGrid', template: '<div><slot /></div>' },
  NGi: { name: 'NGi', template: '<div><slot /></div>' },
  NTabs: { name: 'NTabs', template: '<div data-testid="category-tabs"><slot /></div>' },
  NTabPane: { name: 'NTabPane', props: ['name', 'tab'], template: '<div :data-tab="name"><slot /></div>' },
}))

vi.mock('@/components/BaseStyleButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/MetricCard.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/PageHeader.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/EChartsWrapper.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/LoadingState.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/ErrorState.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/EmptyState.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/YOYGuard.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/RatioConventionBanner.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/DataTablePro.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/ExportToolbar.vue', () => ({ default: { template: '<div />' } }))

vi.mock('./category-tabs/ValueTierTab.vue', () => ({
  default: { name: 'ValueTierTab', template: '<div data-testid="wool-tab" />' },
}))
vi.mock('./category-tabs/ChurnWarningTab.vue', () => ({
  default: { name: 'ChurnWarningTab', template: '<div data-testid="risk-tab" />' },
}))
vi.mock('./category-tabs/CategoryFlowTab.vue', () => ({
  default: {
    name: 'CategoryFlowTab',
    props: ['categoryOptions', 'categoryLabels'],
    template: '<div data-testid="flow-tab" />',
    created(this: { categoryOptions: string[]; categoryLabels: Record<string, string> }) {
      flowProps.categoryOptions = this.categoryOptions
      flowProps.categoryLabels = this.categoryLabels
    },
  },
}))
vi.mock('./category-tabs/CategoryRepurchaseTab.vue', () => ({
  default: {
    name: 'CategoryRepurchaseTab',
    props: ['categoryOptions', 'categoryLabels'],
    template: '<div data-testid="repurchase-tab" />',
    created(this: { categoryOptions: string[]; categoryLabels: Record<string, string> }) {
      repurchaseProps.categoryOptions = this.categoryOptions
      repurchaseProps.categoryLabels = this.categoryLabels
    },
  },
}))
vi.mock('./category-tabs/MarketBasketTab.vue', () => ({
  default: { name: 'MarketBasketTab', template: '<div data-testid="basket-tab" />' },
}))
vi.mock('./category-tabs/ProductClassRepurchaseTab.vue', () => ({
  default: { name: 'ProductClassRepurchaseTab', template: '<div data-testid="product-repurchase-tab" />' },
}))

import CategoryView from './CategoryView.vue'

describe('CategoryView tab wiring', () => {
  beforeEach(() => {
    overviewData.value = {
      all_rows: [{ name: '白膜', display_name: '爆款品类BB', gsv: 1 }],
      member_rows: [],
    }
    distributionData.value = {
      distribution: [
        { name: '凉茶次抛', display_name: '爆款次抛', gmv: 10 },
        { name: '合计', display_name: '合计', gmv: 10 },
      ],
    }
    repurchaseProps.categoryOptions = []
    repurchaseProps.categoryLabels = {}
    flowProps.categoryOptions = []
    flowProps.categoryLabels = {}
  })

  it('mounts wool/risk tabs and keeps filter values as raw names', () => {
    const wrapper = mount(CategoryView)
    expect(wrapper.find('[data-testid="wool-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="risk-tab"]').exists()).toBe(true)
    expect(repurchaseProps.categoryOptions).toEqual(['凉茶次抛'])
    expect(repurchaseProps.categoryOptions).not.toContain('合计')
    expect(repurchaseProps.categoryLabels['凉茶次抛']).toBe('爆款次抛')
    expect(flowProps.categoryOptions).toEqual(['凉茶次抛'])
    wrapper.unmount()
  })
})
