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
    vi.resetAllMocks()
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

  it('完整保留设计稿的经营数字、五列渠道证据和五阶段状态', async () => {
    const designMission = structuredClone(baseMission)
    designMission.target_audience.eligible_customers = 196
    designMission.economics.expected_incremental_customers = 5.7
    designMission.economics.expected_incremental_margin = 701
    api.getTodayMission.mockResolvedValue(designMission)
    const wrapper = mount(GrowthBoardView)
    await flushPromises()

    expect(wrapper.get('.mission-hero').text()).toContain('MISSION / AA9316F2')
    expect(wrapper.get('.mission-status').text()).toBe('等待 CEO 审批')
    expect(wrapper.get('.section-kicker').text()).toBe('今日唯一经营命题')
    expect(wrapper.get('h1').text()).toBe(designMission.title)
    expect(wrapper.get('.executive-summary').text()).toBe(designMission.executive_summary)
    expect(wrapper.get('.ai-recommendation p').text()).toBe(designMission.recommendation)
    expect(wrapper.findAll('.decision-route strong').map(node => node.text())).toEqual(['直播', '货架', '修护精华'])
    expect(wrapper.get('.impact-hero strong').text().replace('￥', '¥')).toBe('¥701')
    expect(wrapper.findAll('.impact-grid dd').map(node => node.text())).toEqual(['196', '+5.7', '+3.3%'])
    expect(wrapper.get('.impact-panel .panel-meta').text()).toContain('90 / 10 TEST')
    expect(wrapper.get('.impact-hero small').text()).toBe('合成测算，不代表已实现收益')
    expect(wrapper.get('.experiment-line span:first-child').attributes('style')).toContain('width: 90%')
    expect(wrapper.get('.experiment-line [aria-label="对照组"]').attributes('style')).toContain('width: 10%')

    expect(wrapper.findAll('[role="columnheader"]').map(node => node.text())).toEqual([
      '首付费渠道', '获客规模', '30 天二单率', '跨渠道率', '180 天净价值',
    ])
    const rows = wrapper.findAll('.channel-row:not(.channel-head)')
    expect(rows).toHaveLength(3)
    const expectedRows = [
      ['直播', '3,511', '28.0%', '65.0%', '¥442'],
      ['货架', '2,730', '34.5%', '65.7%', '¥618'],
      ['淘客', '1,759', '26.3%', '60.9%', '¥273'],
    ]
    rows.forEach((row, index) => {
      const cells = row.findAll('[role="cell"]').map(node => node.text().replace('￥', '¥'))
      expectedRows[index]!.forEach((expected, cell) => expect(cells[cell]).toContain(expected))
    })
    expect(wrapper.findAll('.state-step i').map(node => node.text())).toEqual(['01', '02', '03', '04', '05'])
    expect(wrapper.findAll('.state-step small').map(node => node.text())).toEqual([
      'DISCOVERED', 'EVIDENCE_READY', 'AWAITING_APPROVAL', 'APPROVED', 'WAITING_MEASUREMENT',
    ])
    expect(wrapper.findAll('.state-step.reached')).toHaveLength(3)
    expect(wrapper.get('.action-copy').text()).toContain('批准后仅生成合成人群草稿，不会自动触达用户。')
    expect(wrapper.get('.action-copy').text()).toContain(designMission.decision.guardrail)
    expect(wrapper.get('.approve-button').text()).toContain('审批并生成 DRAFT_EXPORT')
    expect(wrapper.get('.approve-button').text()).toContain('(90% EXPERIMENT · 10% HOLDOUT)')
    expect(api.approveMission).not.toHaveBeenCalled()
    expect(api.createDraftExport).not.toHaveBeenCalled()
  })

  it('经营指标继续来自接口，不把设计示例数字硬编码进页面', async () => {
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    expect(wrapper.get('.impact-hero strong').text().replace('￥', '¥')).toBe('¥480')
    expect(wrapper.findAll('.impact-grid dd').map(node => node.text())).toEqual(['132', '+3.9', '+3.3%'])
    expect(wrapper.get('.impact-grid').text()).not.toContain('196')
  })

  it.each([
    '哪个渠道粘性最强？',
    '有多少客户到了补货窗口？',
    '哪个产品更适合做老客？',
  ])('保留建议问题及其调用：%s', async (question) => {
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    const chip = wrapper.findAll('.prompt-chips button').find(node => node.text() === question)
    expect(chip).toBeDefined()
    await chip!.trigger('click')
    await flushPromises()
    expect(api.diagnoseMission).toHaveBeenCalledExactlyOnceWith(question)
  })

  it('自由输入保留空值防护，并提交用户输入的问题', async () => {
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    const input = wrapper.get('input[aria-label="自由问数问题"]')
    expect(input.attributes('maxlength')).toBe('300')
    expect(wrapper.get('.ask-form button').attributes('disabled')).toBeDefined()
    await input.setValue('  哪个产品更适合做新客？  ')
    expect(wrapper.get('.ask-form button').attributes('disabled')).toBeUndefined()
    await wrapper.get('.ask-form').trigger('submit')
    await flushPromises()
    expect(api.diagnoseMission).toHaveBeenCalledExactlyOnceWith('哪个产品更适合做新客？')
  })

  it('审批失败不进入草稿导出，错误可见且保留重试入口', async () => {
    api.approveMission.mockRejectedValueOnce(new Error('审批版本冲突'))
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    await wrapper.get('.approve-button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('审批版本冲突')
    expect(api.createDraftExport).not.toHaveBeenCalled()
    expect(wrapper.get('.approve-button').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).not.toContain('下载合成人群草稿')
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

  it.each(['success', 'failure'])('重置后忽略旧问数的延迟 %s，且不结束新请求', async (outcome) => {
    api.getTodayMission.mockResolvedValue({ ...structuredClone(baseMission), demo_controls: { reset_enabled: true } })
    const oldRequest = Promise.withResolvers<any>()
    const newRequest = Promise.withResolvers<any>()
    api.diagnoseMission.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    await wrapper.findAll('.prompt-chips button')[0].trigger('click')
    await wrapper.get('.reset-demo-button').trigger('click')
    await flushPromises()
    await wrapper.findAll('.prompt-chips button')[1].trigger('click')
    expect(api.diagnoseMission).toHaveBeenCalledTimes(2)

    if (outcome === 'success') oldRequest.resolve({ answer: '重置前旧答案', limitations: [] })
    else oldRequest.reject(new Error('重置前旧错误'))
    await flushPromises()
    expect(wrapper.text()).not.toContain('重置前旧')
    expect(wrapper.get('.ask-form button').text()).toContain('正在诊断')

    newRequest.resolve({ answer: '重置后新答案', limitations: [] })
    await flushPromises()
    expect(wrapper.text()).toContain('重置后新答案')
    expect(wrapper.get('.ask-form button').text()).toContain('生成诊断')
    wrapper.unmount()
  })

  it.each(['success', 'failure'])('重置等待期间隔离旧问数的 %s，拒绝插入新问数', async (outcome) => {
    api.getTodayMission.mockResolvedValue({ ...structuredClone(baseMission), demo_controls: { reset_enabled: true } })
    const oldRequest = Promise.withResolvers<any>()
    const resetRequest = Promise.withResolvers<any>()
    api.diagnoseMission.mockReturnValueOnce(oldRequest.promise)
    api.resetMission.mockReturnValueOnce(resetRequest.promise)
    const wrapper = mount(GrowthBoardView)
    await flushPromises()
    await wrapper.findAll('.prompt-chips button')[0].trigger('click')
    await wrapper.get('.reset-demo-button').trigger('click')
    if (outcome === 'success') oldRequest.resolve({ answer: '重置前旧答案', limitations: [] })
    else oldRequest.reject(new Error('重置前旧错误'))
    await flushPromises()
    await wrapper.findAll('.prompt-chips button')[1].trigger('click')
    expect(api.diagnoseMission).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('重置前旧')
    resetRequest.reject(new Error('重置失败可重试'))
    await flushPromises()
    expect(wrapper.text()).toContain('重置失败可重试')
    await wrapper.findAll('.prompt-chips button')[1].trigger('click')
    await flushPromises()
    expect(api.diagnoseMission).toHaveBeenCalledTimes(2)
    wrapper.unmount()
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
