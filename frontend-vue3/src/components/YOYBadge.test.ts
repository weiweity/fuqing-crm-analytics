// YOYBadge 组件测试
// 验证 humanizeChange 逻辑: unit='%' 直接显示, unit='pp' 内部 *100
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import YOYBadge from './YOYBadge.vue'

function getText(wrapper: ReturnType<typeof mount>): string {
  return wrapper.text().trim()
}

describe('YOYBadge display', () => {
  it('value=14 unit=% → "+14.00% ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 14, unit: '%' } })
    expect(getText(wrapper)).toBe('+14.00% ↑')
  })

  it('value=-7 unit=% → "7.00% ↓"', () => {
    const wrapper = mount(YOYBadge, { props: { value: -7, unit: '%' } })
    expect(getText(wrapper)).toBe('7.00% ↓')
  })

  it('value=10 unit=pp → "+10.00pp ↑" (caller 已 *100)', () => {
    // Sprint 13 改: caller 传已 *100 数值, humanizeChange 不再 *100
    const wrapper = mount(YOYBadge, { props: { value: 10, unit: 'pp' } })
    expect(getText(wrapper)).toBe('+10.00pp ↑')
  })

  it('value=-53.81 unit=pp → "53.81pp ↓" (caller 已 *100)', () => {
    const wrapper = mount(YOYBadge, { props: { value: -53.81, unit: 'pp' } })
    expect(getText(wrapper)).toBe('53.81pp ↓')
  })

  it('value=null → "—"', () => {
    const wrapper = mount(YOYBadge, { props: { value: null } })
    expect(getText(wrapper)).toBe('—')
  })

  it('value=0 → "+0.00% ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0 } })
    expect(getText(wrapper)).toBe('+0.00% ↑')
  })
})

// Sprint 13 收口: humanizeChange pass-through 契约单测 (跟 MetricCard 同步)
// 工单 W14: 验证 caller 已 *100 传 pp/percentage 数值, humanizeChange 不再 *100
describe('YOYBadge pass-through 契约 (Sprint 13 修)', () => {
  it('pp 5.0 (caller 已 *100) → "+5.00pp ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 5.0, unit: 'pp' } })
    expect(getText(wrapper)).toBe('+5.00pp ↑')
  })

  it('pp -3.5 (caller 已 *100) → "3.50pp ↓" (abs)', () => {
    const wrapper = mount(YOYBadge, { props: { value: -3.5, unit: 'pp' } })
    expect(getText(wrapper)).toBe('3.50pp ↓')
  })

  it('pp 0 (caller 已 *100) → "+0.00pp ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0, unit: 'pp' } })
    expect(getText(wrapper)).toBe('+0.00pp ↑')
  })

  it('% 25 (caller 已 *100) → "+25.00% ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 25, unit: '%' } })
    expect(getText(wrapper)).toBe('+25.00% ↑')
  })

  it('pp NaN → "+0.00pp ↑" (fallback, value=NaN → 走 humanizeChange 防护)', () => {
    // YOYBadge 模板 v-else-if="value >= 0", NaN 走 else 分支, 显示 0.00pp ↓
    const wrapper = mount(YOYBadge, { props: { value: NaN, unit: 'pp' } })
    expect(getText(wrapper)).toBe('0.00pp ↓')
  })

  it('% Infinity → "+0.00% ↑" (fallback, Infinity>=0 走 if 分支)', () => {
    const wrapper = mount(YOYBadge, { props: { value: Infinity, unit: '%' } })
    expect(getText(wrapper)).toBe('+0.00% ↑')
  })
})
