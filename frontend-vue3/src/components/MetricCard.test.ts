// Sprint 11 修: humanizeChange 按 unit 区分, 统一 0.00 形式
// 设计 (跟 AudienceView caller 配套):
//   - unit='%': caller (kpiChangePct) 已 *100, 传 percentage 值 (e.g. 14 for 14%)
//   - unit='pp': caller (kpiChange) 传 0-1 ratio (e.g. 0.10 for 10pp), humanizeChange 内部 *100
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCard from './MetricCard.vue'

// 抽出组件的 humanizeChange 函数逻辑 (script setup 不能直接 export, 通过 mount + 验证渲染)
function getChangeText(wrapper: ReturnType<typeof mount>): string {
  // MetricCard 渲染 change 文本在第一个 span 内
  const span = wrapper.find('span')
  return span.text().trim()
}

describe('MetricCard YOY/pp display (Sprint 11 修, 0.00 形式)', () => {
  it('integer percentage 14 (% unit) 显示 "↑14.00%" (不 trim 整数)', () => {
    // caller 模式: kpiChangePct 返 14 (已 *100)
    const wrapper = mount(MetricCard, {
      props: { title: '全店GSV', value: '¥559.2万', change: 14, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑14.00%')
  })

  it('integer pp ratio 0.10 (pp unit) 显示 "↑10.00pp" (*100 后 0.00 形式)', () => {
    // caller 模式: kpiChange 返 0.10 (0-1 ratio, 未 *100)
    const wrapper = mount(MetricCard, {
      props: { title: '老客占比', value: '53.4%', change: 0.10, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↑10.00pp')
  })

  it('non-integer percentage 80.61 显示 "↑80.61%" (保留 2 位小数)', () => {
    // caller 模式: kpiChangePct 返 80.61
    const wrapper = mount(MetricCard, {
      props: { title: '新增会员数', value: '8,745', change: 80.61, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑80.61%')
  })

  it('non-integer pp ratio 0.0358 显示 "↓3.58pp" (*100 + 2 位)', () => {
    // caller 模式: kpiChange 返 -0.0358
    const wrapper = mount(MetricCard, {
      props: { title: '去年同期入会率', value: '4.81%', change: -0.0358, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓3.58pp')
  })

  it('half-up 14.5 percentage 治 toFixed bug (e.g. 14.5 → "14.50")', () => {
    // Math.round(14.5 * 100) / 100 = 14.5, toFixed(2) = "14.50"
    // 跟直接 toFixed(14.5) = "14.5" 对比, 现在用 round 确保无 banker's rounding
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 14.5, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑14.50%')
  })

  it('0 percentage 显示 "0.00%" (不显示 "0%")', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 0, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('0.00%')
  })

  it('0 pp ratio 显示 "0.00pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 0, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('0.00pp')
  })

  it('negative percentage -7 显示 "↓7.00%"', () => {
    // caller 模式: kpiChangePct 返 -7
    const wrapper = mount(MetricCard, {
      props: { title: '新客GSV', value: '¥260.5万', change: -7, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↓7.00%')
  })

  it('negative pp ratio -0.5381 显示 "↓53.81pp" (会员入会率 1.23% vs 4.81% 差)', () => {
    // caller 模式: visitorChange 返 -0.5381
    const wrapper = mount(MetricCard, {
      props: { title: '会员入会率', value: '1.23%', change: -0.5381, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓53.81pp')
  })

  it('NaN/Infinity 显示 "0.00%" (fallback)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: NaN, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('0.00%')
  })
})
