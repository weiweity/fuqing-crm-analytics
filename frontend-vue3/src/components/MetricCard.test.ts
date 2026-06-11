// Sprint 13 修: humanizeChange pass-through 契约
// 设计 (跟 caller 配套, 跟 YOYBadge 同步):
//   - unit='%': caller 已 *100, 传 percentage 值 (e.g. 25 for 25%)
//   - unit='pp': caller 已 *100, 传 pp 数值 (e.g. 5 for 5pp)
//   - humanizeChange 只做 abs + toFixed(2), 不再内部 *100
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

  it('integer pp ratio 10 (pp unit) 显示 "↑10.00pp" (caller 已 *100, 0.00 形式)', () => {
    // Sprint 13 改: caller 模式: kpiChange 返 10 (已 *100), humanizeChange 不再 *100
    const wrapper = mount(MetricCard, {
      props: { title: '老客占比', value: '53.4%', change: 10, unit: 'pp' },
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

  it('non-integer pp ratio -3.58 显示 "↓3.58pp" (caller 已 *100, 2 位)', () => {
    // Sprint 13 改: caller 模式: kpiChange 返 -3.58 (已 *100), humanizeChange 不再 *100
    const wrapper = mount(MetricCard, {
      props: { title: '去年同期入会率', value: '4.81%', change: -3.58, unit: 'pp' },
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

  it('negative pp ratio -53.81 显示 "↓53.81pp" (会员入会率 1.23% vs 4.81% 差, caller 已 *100)', () => {
    // Sprint 13 改: caller 模式: visitorChange 返 -53.81 (已 *100)
    const wrapper = mount(MetricCard, {
      props: { title: '会员入会率', value: '1.23%', change: -53.81, unit: 'pp' },
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

// Sprint 13 收口: humanizeChange pass-through 契约单测 (跟 YOYBadge 同步)
// 工单 W14: 验证 caller 已 *100 传 pp/percentage 数值, humanizeChange 不再 *100
describe('MetricCard pass-through 契约 (Sprint 13 修)', () => {
  it('pp 5.0 (caller 已 *100) → "↑5.00pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '老客占比', value: '53.4%', change: 5.0, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↑5.00pp')
  })

  it('pp -3.5 (caller 已 *100) → "↓3.50pp" (abs)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '入会率', value: '4.81%', change: -3.5, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓3.50pp')
  })

  it('pp 0 (caller 已 *100) → "0.00pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 0, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('0.00pp')
  })

  it('% 25 (caller 已 *100) → "↑25.00%"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '新客GSV', value: '¥260.5万', change: 25, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑25.00%')
  })

  it('pp NaN → "0.00pp" (fallback)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: NaN, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('0.00pp')
  })

  it('% Infinity → "↑数据异常" (Sprint 18 #124: |Infinity|>1e6 守卫生效, 跟 YOYBadge 同步)', () => {
    // Sprint 18 #124 扩守卫到 MetricCard, 跟 YOYBadge 行为一致
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: Infinity, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑数据异常')
  })
})

// Sprint 18 #124: MetricCard 集成 YOYGuard 守卫扩展测试
// 跟 YOYBadge 一致: |v|>1e6 触发守卫, NaN/Infinity 也走守卫
describe('MetricCard YOYGuard 集成 (Sprint 18 #124)', () => {
  it('change=1e7 unit=% → "↑数据异常" (万倍异常值守卫生效)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '全店GSV', value: '¥559.2万', change: 1e7, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑数据异常')
  })

  it('change=-1e7 unit=pp → "↓数据异常" (负向万倍异常值守卫)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '老客占比', value: '53.4%', change: -1e7, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓数据异常')
  })

  it('change=100 unit=% → "↑100.00%" (边界内正常值, 不触发守卫, 跟 YOYBadge 同款)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 100, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑100.00%')
  })
})
