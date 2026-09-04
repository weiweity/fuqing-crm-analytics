import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getTodayMission: vi.fn(),
  diagnoseMission: vi.fn(),
  approveMission: vi.fn(),
  createDraftExport: vi.fn(),
  downloadDraftExport: vi.fn(),
  resetMission: vi.fn(),
}))

vi.mock('@/features/mission/api', () => api)

import GrowthBoardView from './GrowthBoardView.vue'
import { useAuthStore } from '@/stores/auth'

const baseMission = {
  mission_id: 'mission-20260831-aa9316f2',
  status: 'AWAITING_APPROVAL' as const,
  version: 1,
  title: '把直播大盘变成可复购资产',
  executive_summary: '直播带来最多首付费客户，但货架二单率更高。',
  recommendation: '对直播待补货人群发起 90/10 对照实验。',
  decision: {
    decision_type: 'SECOND_PURCHASE_ACTIVATION',
    volume_leader: '直播',
    quality_leader: '货架',
    guardrail: '未经审批不产生名单',
    next_action: 'APPROVE_DRAFT_EXPORT',
  },
  channel_metrics: [
    { channel: '直播', first_paid_customers: 3511, mature_30d_customers: 3385, second_paid_rate_30d: 0.2798, median_days_to_second_paid: 37, cross_channel_rate: 0.6502, avg_net_value_180d: 441.53 },
    { channel: '货架', first_paid_customers: 2730, mature_30d_customers: 2630, second_paid_rate_30d: 0.3449, median_days_to_second_paid: 35, cross_channel_rate: 0.6568, avg_net_value_180d: 618.28 },
    { channel: '淘客', first_paid_customers: 1759, mature_30d_customers: 1694, second_paid_rate_30d: 0.2633, median_days_to_second_paid: 37, cross_channel_rate: 0.6094, avg_net_value_180d: 272.83 },
  ],
  target_audience: {
    segment_key: '直播:REPLENISHMENT_DUE',
    segment_name: '直播首购·待补货人群',
    channel: '直播',
    lifecycle_stage: 'REPLENISHMENT_DUE',
    eligible_customers: 132,
    activation_product: { product_code: 'SYN-P-003', product_name: '修护精华', list_price: 169, synthetic_unit_cost: 46, replenishment_cycle_days: 35 },
  },
  economics: { experiment_share: 0.9, holdout_share: 0.1, assumed_conversion_uplift: 0.0326, expected_incremental_customers: 3.9, expected_incremental_margin: 479.7, currency: 'CNY_SYNTHETIC', assumption_note: '合成假设' },
  evidence: [
    { metric: 'first_paid_customers', finding: '直播首付费客户 3511 人，规模第一', metric_version: 'customer-origin-v1' },
  ],
  state_timeline: [
    { state: 'DISCOVERED', reached: true },
    { state: 'EVIDENCE_READY', reached: true },
    { state: 'AWAITING_APPROVAL', reached: true },
    { state: 'APPROVED', reached: false },
    { state: 'WAITING_MEASUREMENT', reached: false },
  ],
  approval: null,
  latest_export: null,
  demo_controls: { reset_enabled: false },
  data_provenance: {
    data_profile: 'synthetic' as const,
    contains_real_data: false as const,
    dataset_version: 'syn-commerce-1.0.0',
    dataset_content_sha256: 'sha256:aa9316f2072f545fadbedf9e88e04f873ef6117121c85ed69388c631ee7456b9',
    analysis_as_of_date: '2026-08-31',
    metric_versions: ['customer-origin-v1'],
  },
}

describe('GrowthBoardView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    setActivePinia(createPinia())
    useAuthStore().setSession('test-token', 'JUDGE_DEMO', true)
    api.getTodayMission.mockResolvedValue(structuredClone(baseMission))
    api.diagnoseMission.mockResolvedValue({
      question: '哪个渠道粘性最强？',
      intent: 'CHANNEL_QUALITY',
      answer_mode: 'DETERMINISTIC_TOOL',
      answer: '直播是规模入口，但货架是质量标杆。',
      evidence: [],
      limitations: ['仅支持受控问数'],
      data_provenance: baseMission.data_provenance,
    })
    api.approveMission.mockResolvedValue({
      ...structuredClone(baseMission),
      status: 'APPROVED',
      version: 2,
      approval: { approved_by: 'JUDGE_DEMO', approved_at: '2026-09-04T10:00:00Z' },
    })
    api.createDraftExport.mockResolvedValue({
      mission_id: baseMission.mission_id,
      mission_status: 'WAITING_MEASUREMENT',
      mission_version: 3,
      export_id: 'draft-aa9316f2-2',
      export_status: 'DRAFT_EXPORT_READY',
      row_count: 132,
      experiment_count: 119,
      holdout_count: 13,
      sha256: 'sha256:export',
      download_url: '/api/v1/missions/x/download',
      expires_at: null,
      data_provenance: baseMission.data_provenance,
    })
    api.resetMission.mockResolvedValue({
      ...structuredClone(baseMission),
      version: 4,
      demo_controls: { reset_enabled: true },
    })
  })

  it('展示 CEO 决策冲突和 synthetic 边界', async () => {
    const wrapper = mount(GrowthBoardView)
    await flushPromises()

    expect(wrapper.text()).toContain('CEO GROWTH BOARD')
    expect(wrapper.text()).toContain('客户运营全局营销')
    expect(wrapper.text()).toContain('把直播大盘变成可复购资产')
    expect(wrapper.text()).toContain('SYNTHETIC DATA')
    expect(wrapper.text()).toContain('规模入口')
    expect(wrapper.text()).toContain('质量标杆')
    expect(wrapper.text()).toContain('EXPECTED IMPACT')
    expect(wrapper.text()).toContain('可激活人群')
    expect(wrapper.text()).toContain('假设提升')
    expect(wrapper.get('.channel-row--leader').text()).toContain('货架')
    expect(wrapper.get('.channel-row--leader').text()).toContain('粘性第一')
    expect(wrapper.get('.approve-button').text()).toContain('(90% EXPERIMENT · 10% HOLDOUT)')
  })

  it('自由问数使用受控诊断接口', async () => {
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    const chip = wrapper.findAll('.prompt-chips button')[0]
    await chip.trigger('click')
    await flushPromises()

    expect(api.diagnoseMission).toHaveBeenCalledWith('哪个渠道粘性最强？')
    expect(wrapper.text()).toContain('直播是规模入口，但货架是质量标杆。')
  })

  it('新问题失败时清除上一条答案，避免把旧结论当新结论', async () => {
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    await wrapper.findAll('.prompt-chips button')[0].trigger('click')
    await flushPromises()
    api.diagnoseMission.mockRejectedValueOnce(new Error('诊断暂不可用'))

    await wrapper.findAll('.prompt-chips button')[1].trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('直播是规模入口，但货架是质量标杆。')
    expect(wrapper.text()).toContain('诊断暂不可用')
  })

  it('审批后串行生成 DRAFT_EXPORT', async () => {
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    await wrapper.get('.approve-button').trigger('click')
    await flushPromises()

    expect(api.approveMission).toHaveBeenCalledWith(
      baseMission.mission_id,
      1,
      expect.stringContaining('approve-'),
    )
    expect(api.createDraftExport).toHaveBeenCalledWith(
      baseMission.mission_id,
      2,
      expect.stringContaining('export-'),
    )
    expect(wrapper.text()).toContain('132 条合成人群')
    expect(wrapper.text()).toContain('下载合成人群草稿')
  })

  it('刷新后从 Mission 恢复最近的 DRAFT_EXPORT 下载入口', async () => {
    const latestExport = {
      mission_id: baseMission.mission_id,
      mission_status: 'WAITING_MEASUREMENT' as const,
      mission_version: 3,
      export_id: 'draft-aa9316f2-2',
      export_status: 'DRAFT_EXPORT_READY' as const,
      row_count: 132,
      experiment_count: 119,
      holdout_count: 13,
      sha256: 'sha256:export',
      download_url: '/api/v1/missions/x/download',
      expires_at: null,
      data_provenance: baseMission.data_provenance,
    }
    api.getTodayMission.mockResolvedValue({
      ...structuredClone(baseMission),
      status: 'WAITING_MEASUREMENT',
      version: 3,
      latest_export: latestExport,
    })
    const wrapper = mount(GrowthBoardView)
    await flushPromises()

    expect(wrapper.text()).toContain('下载合成人群草稿')
    await wrapper.get('.approve-button.export-ready').trigger('click')
    await flushPromises()
    expect(api.downloadDraftExport).toHaveBeenCalledWith(latestExport)
  })

  it('导出失败重试时复用同一个幂等键且不会重复审批', async () => {
    api.createDraftExport
      .mockRejectedValueOnce(new Error('网络中断'))
      .mockResolvedValueOnce({
        mission_id: baseMission.mission_id,
        mission_status: 'WAITING_MEASUREMENT',
        mission_version: 3,
        export_id: 'draft-aa9316f2-2',
        export_status: 'DRAFT_EXPORT_READY',
        row_count: 132,
        experiment_count: 119,
        holdout_count: 13,
        sha256: 'sha256:export',
        download_url: '/api/v1/missions/x/download',
        expires_at: null,
        data_provenance: baseMission.data_provenance,
      })
    const wrapper = mount(GrowthBoardView)
    await flushPromises()

    await wrapper.get('.approve-button').trigger('click')
    await flushPromises()
    await wrapper.get('.approve-button').trigger('click')
    await flushPromises()

    expect(api.approveMission).toHaveBeenCalledTimes(1)
    expect(api.createDraftExport).toHaveBeenCalledTimes(2)
    expect(api.createDraftExport.mock.calls[0]?.[2]).toBe(
      api.createDraftExport.mock.calls[1]?.[2],
    )
  })

  it('演示重置按钮受服务端开关和管理员身份双重控制', async () => {
    api.getTodayMission.mockResolvedValue({
      ...structuredClone(baseMission),
      demo_controls: { reset_enabled: true },
    })
    useAuthStore().setIdentity('viewer', false)
    const wrapper = mount(GrowthBoardView)
    await flushPromises()

    expect(wrapper.find('.reset-demo-button').exists()).toBe(false)
  })

  it('管理员可把演示恢复到审批前并清空页面临时结果', async () => {
    const latestExport = {
      mission_id: baseMission.mission_id,
      mission_status: 'WAITING_MEASUREMENT' as const,
      mission_version: 3,
      export_id: 'draft-aa9316f2-2',
      export_status: 'DRAFT_EXPORT_READY' as const,
      row_count: 132,
      experiment_count: 119,
      holdout_count: 13,
      sha256: 'sha256:export',
      download_url: '/api/v1/missions/x/download',
      expires_at: null,
      data_provenance: baseMission.data_provenance,
    }
    api.getTodayMission.mockResolvedValue({
      ...structuredClone(baseMission),
      status: 'WAITING_MEASUREMENT',
      version: 3,
      latest_export: latestExport,
      demo_controls: { reset_enabled: true },
    })
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    await wrapper.findAll('.prompt-chips button')[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('直播是规模入口，但货架是质量标杆。')
    await wrapper.get('.reset-demo-button').trigger('click')
    await flushPromises()

    expect(api.resetMission).toHaveBeenCalledWith(
      baseMission.mission_id,
      3,
      expect.stringContaining('reset-'),
    )
    expect(wrapper.text()).not.toContain('直播是规模入口，但货架是质量标杆。')
    expect(wrapper.text()).not.toContain('下载合成人群草稿')
    expect(wrapper.text()).toContain('审批并生成 DRAFT_EXPORT')
    expect(wrapper.get('input[aria-label="自由问数问题"]').element).toHaveProperty('value', '')
  })
})
