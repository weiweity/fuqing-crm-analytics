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
  fetchCategoryChurn: vi.fn(),
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
    template: '<div data-testid="churn-table" />',
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
    template: '<div data-testid="churn-export" />',
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
}))

import ChurnWarningTab from './ChurnWarningTab.vue'

const row = {
  category_name: '白膜',
  display_name: '爆款品类BB',
  current_users: 1200,
  previous_users: 1500,
  mean_hazard: 0.62,
  high_risk_users: 80,
  inter_churn: 40,
  silent_churn: 20,
  top_churn_dest1: '凉茶次抛',
  top_churn_dest1_ratio: 0.4,
  top_churn_dest2: '医用洁面',
  挽回建议: '用凉茶次抛承接 医用洁面 流失',
}

describe('ChurnWarningTab #165 wiring', () => {
  beforeEach(() => {
    mockData.value = {
      table: [row],
      scatter_data: [{ ...row, category_name: '白膜' }],
      operation_suggestions: ['紧急:医用凝胶 流失加速'],
    }
    tableCapture.columns = []
    tableCapture.data = []
    exportCapture.columns = []
    exportCapture.data = []
  })

  it('masks dest columns and suggestion text, keeps mean_hazard', () => {
    const wrapper = mount(ChurnWarningTab)
    const dest1 = tableCapture.columns.find((c) => c.key === 'top_churn_dest1')
    const dest2 = tableCapture.columns.find((c) => c.key === 'top_churn_dest2')
    const advice = tableCapture.columns.find((c) => c.key === '挽回建议')
    expect(dest1.render(row).children).toBe('爆款次抛')
    expect(dest2.render(row).children).toBe('爆款洁面')
    expect(advice.render(row)).toBe('用爆款次抛承接 爆款洁面 流失')
    expect(wrapper.text()).toContain('爆款凝胶')
    expect(exportCapture.columns.map((c) => c.key)).toContain('mean_hazard')
    expect(exportCapture.columns.map((c) => c.key)).toContain('high_risk_users')
    wrapper.unmount()
  })
})
