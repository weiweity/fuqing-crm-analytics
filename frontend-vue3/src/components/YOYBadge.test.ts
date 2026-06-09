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

  it('value=0.10 unit=pp → "+10.00pp ↑" (pp 内部 *100)', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0.10, unit: 'pp' } })
    expect(getText(wrapper)).toBe('+10.00pp ↑')
  })

  it('value=-0.5381 unit=pp → "53.81pp ↓" (pp 内部 *100)', () => {
    const wrapper = mount(YOYBadge, { props: { value: -0.5381, unit: 'pp' } })
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
