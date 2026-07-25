// MetricCard YOY/pp display (L4.81 契约更新)
// L4.81 SSOT: backend 返回 raw ratio (0-1), YOYGuard 集中 *100 显示
// MetricCard 只包箭头 + 颜色, 数值格式化下沉到 YOYGuard
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCard from './MetricCard.vue'

// 抽出组件的 change 文本 (script setup 不能直接 export, 通过 mount + 验证渲染)
function getChangeText(wrapper: ReturnType<typeof mount>): string {
  // MetricCard 渲染 change 文本在第一个 span 内
  const span = wrapper.find('span')
  return span.text().trim()
}

describe('MetricCard YOY/pp display (L4.81 raw ratio → *100)', () => {
  it('integer percentage raw 0.14 (% unit) 显示 "↑14.00%"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '全店GSV', value: '¥559.2万', change: 0.14, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑14.00%')
  })

  it('integer pp raw 0.10 (pp unit) 显示 "↑10.00pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '老客占比', value: '53.4%', change: 0.10, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↑10.00pp')
  })

  it('non-integer percentage raw 0.8061 显示 "↑80.61%"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '新增会员数', value: '8,745', change: 0.8061, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑80.61%')
  })

  it('non-integer pp raw -0.0358 显示 "↓3.58pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '去年同期入会率', value: '4.81%', change: -0.0358, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓3.58pp')
  })

  it('half-up raw 0.145 percentage → "↑14.50%"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 0.145, unit: '%' },
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

  it('negative percentage raw -0.07 显示 "↓7.00%"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '新客GSV', value: '¥260.5万', change: -0.07, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↓7.00%')
  })

  it('negative pp raw -0.5381 显示 "↓53.81pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '会员入会率', value: '1.23%', change: -0.5381, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓53.81pp')
  })

  it('NaN/Infinity 显示 "0.00%" (fallback) / "↑数据异常"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: NaN, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('0.00%')
  })
})

// L4.81: raw ratio 传入, 组件 *100
describe('MetricCard L4.81 raw-ratio 契约', () => {
  it('pp 0.05 (raw) → "↑5.00pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '老客占比', value: '53.4%', change: 0.05, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↑5.00pp')
  })

  it('pp -0.035 (raw) → "↓3.50pp" (abs)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '入会率', value: '4.81%', change: -0.035, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('↓3.50pp')
  })

  it('pp 0 (raw) → "0.00pp"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 0, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('0.00pp')
  })

  it('% 0.25 (raw) → "↑25.00%"', () => {
    const wrapper = mount(MetricCard, {
      props: { title: '新客GSV', value: '¥260.5万', change: 0.25, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑25.00%')
  })

  it('pp NaN → "0.00pp" (fallback)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: NaN, unit: 'pp' },
    })
    expect(getChangeText(wrapper)).toBe('0.00pp')
  })

  it('% Infinity → "↑数据异常" (|Infinity|>1e6 守卫生效)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: Infinity, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑数据异常')
  })
})

// YOYGuard 守卫扩展: threshold 在 raw ratio 上
describe('MetricCard YOYGuard 集成 (L4.81)', () => {
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

  it('change=1.0 unit=% → "↑100.00%" (raw 1.0 = 100%, 边界内正常值)', () => {
    const wrapper = mount(MetricCard, {
      props: { title: 'test', value: '0', change: 1.0, unit: '%' },
    })
    expect(getChangeText(wrapper)).toBe('↑100.00%')
  })
})
