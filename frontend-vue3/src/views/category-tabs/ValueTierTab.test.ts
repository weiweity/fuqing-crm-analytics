import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const mockData = ref<any>(null)
const tableCapture = { columns: [] as any[], data: [] as any[] }
const exportCapture = { columns: [] as any[], data: [] as any[] }

vi.mock('@tanstack/vue-query', () => ({
  useQuery: () => ({
    data: mockData,
    isLoading: ref(false),
    error: ref(null),
    refetch: vi.fn(),
  }),
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
  fetchCategoryValueTier: vi.fn(),
}))

vi.mock('@/components/EChartsWrapper.vue', () => ({
  default: { name: 'EChartsWrapper', template: '<div data-testid="chart" />' },
}))
vi.mock('@/components/LoadingState.vue', () => ({
  default: { name: 'LoadingState', template: '<div>loading</div>' },
}))
vi.mock('@/components/ErrorState.vue', () => ({
  default: { name: 'ErrorState', template: '<div>error</div>' },
}))
vi.mock('@/components/EmptyState.vue', () => ({
  default: { name: 'EmptyState', template: '<div>empty</div>' },
}))
vi.mock('@/components/DataTablePro.vue', () => ({
  default: {
    name: 'DataTablePro',
    props: ['columns', 'data'],
    template: '<div data-testid="value-table" />',
    created(this: { columns: unknown; data: unknown }) {
      tableCapture.columns = this.columns as typeof tableCapture.columns
      tableCapture.data = this.data as typeof tableCapture.data
    },
  },
}))
vi.mock('@/components/ExportToolbar.vue', () => ({
  default: {
    name: 'ExportToolbar',
    props: ['columns', 'data'],
    template: '<div data-testid="value-export" />',
    created(this: { columns: unknown; data: unknown }) {
      exportCapture.columns = this.columns as typeof exportCapture.columns
      exportCapture.data = this.data as typeof exportCapture.data
    },
  },
}))
vi.mock('naive-ui', () => ({
  NTooltip: {
    name: 'NTooltip',
    template: '<div><slot name="trigger" /><slot /></div>',
  },
  NTabs: {
    name: 'NTabs',
    template: '<div><slot /></div>',
  },
}))

import ValueTierTab from './ValueTierTab.vue'

const row = {
  category_name: '凉茶次抛',
  display_name: '爆款次抛',
  total_users: 100,
  high_value_users: 10,
  high_value_ratio: 0.1,
  member_ratio: 0.2,
  avg_aus: 80,
  value_score: 1.2,
  value_grade: 'A',
  wool_party: {
    high_risk_count: 7,
    high_risk_ratio: 0.07,
    mean_score: 0.42,
    never_converted_count: 3,
    converted_then_sample_count: 2,
    sample_only_window_count: 4,
    scored_users: 90,
  },
}

describe('ValueTierTab #165 wool fields', () => {
  beforeEach(() => {
    mockData.value = {
      table: [row],
      dual_axis_line: {
        categories: ['凉茶次抛'],
        wool_party_ratios: [0.07],
        high_value_ratios: [0.1],
      },
    }
    tableCapture.columns = []
    tableCapture.data = []
    exportCapture.columns = []
    exportCapture.data = []
  })

  it('renders user-level wool scores and does not read type1_count', () => {
    const wrapper = mount(ValueTierTab)
    const riskCol = tableCapture.columns.find((c) => c.key === 'wool_high_risk')
    const scoreCol = tableCapture.columns.find((c) => c.key === 'wool_mean_score')
    expect(riskCol.render(row)).toBe('7 (7.0%)')
    expect(scoreCol.render(row)).toBe('42')
    const keys = exportCapture.columns.map((c) => c.key)
    expect(keys).toEqual(expect.arrayContaining([
      'wool_high_risk_count',
      'wool_mean_score',
      'wool_never_converted',
    ]))
    expect(keys.join(',')).not.toMatch(/type1_count|type2_count|total_count/)
    expect(exportCapture.data[0].category_name).toBe('爆款次抛')
    expect(exportCapture.data[0].wool_high_risk_count).toBe(7)
    wrapper.unmount()
  })
})
