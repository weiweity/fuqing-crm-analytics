// Sprint 11 修: humanizeChange 单测样板
// 覆盖整数 (14.00 → 14) / 一位小数 (14.5 → 14.5) / 两位小数 (14.55 → 14.55) / 零 (0 → 0%) / pp 单元
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCard from './MetricCard.vue'

// 抽出组件的 humanizeChange 函数逻辑 (script setup 不能直接 export, 通过 mount + 验证渲染)
function getChangeText(wrapper: ReturnType<typeof mount>): string {
  // MetricCard 渲染 change 文本在第一个 span 内
  const span = wrapper.find('span')
  return span.text().trim()
}

describe('MetricCard YOY/pp display (Sprint 11 修)', () => {
  it('integer ratio 0.14 (% unit) 显示 "14%" (trim trailing .00)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '全店GSV', value: '¥559.2万', change: 0.14, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑14%')
  })

  it('integer pp 0.10 (pp unit) 显示 "10pp" (trim trailing .00)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '老客占比', value: '53.4%', change: 0.10, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↑10pp')
  })

  it('non-integer ratio 0.8061 显示 "80.61%" (保留 2 位小数)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '新增会员数', value: '8,745', change: 0.8061, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑80.61%')
  })

  it('non-integer pp 0.0358 显示 "3.58pp" (保留 2 位小数)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '去年同期入会率', value: '4.81%', change: -0.0358, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓3.58pp')
  })

  it('half-up 0.145 rounds to "14.5%" (不是 "14.49%" toFixed bug)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 0.145, unit: '%' },
    })
    // Math.round(0.145 * 100 * 100) / 100 = 14.5
    expect(getChangeText(wrapper)).toBe('↑14.5%')
  })

  it('0 显示 "0%" (不显示 "0.00%")', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 0, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('0%')
  })

  it('negative change 显示 ↓ 箭头', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '新客GSV', value: '¥260.5万', change: -0.07, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↓7%')
  })
})
