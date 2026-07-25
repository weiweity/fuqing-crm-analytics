// YOYBadge 组件测试 (L4.81 契约更新)
// L4.81 SSOT: backend 返回 raw ratio (0-1), YOYGuard 集中 *100 显示; YOYBadge 只负责箭头+颜色
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import YOYBadge from './YOYBadge.vue'

function getText(wrapper: ReturnType<typeof mount>): string {
  return wrapper.text().trim()
}

describe('YOYBadge display (L4.81 raw ratio)', () => {
  it('value=0.14 unit=% → "+14.00% ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0.14, unit: '%' } })
    expect(getText(wrapper)).toBe('+14.00% ↑')
  })

  it('value=-0.07 unit=% → "7.00% ↓"', () => {
    const wrapper = mount(YOYBadge, { props: { value: -0.07, unit: '%' } })
    expect(getText(wrapper)).toBe('7.00% ↓')
  })

  it('value=0.10 unit=pp → "+10.00pp ↑" (raw ratio, 组件 *100)', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0.10, unit: 'pp' } })
    expect(getText(wrapper)).toBe('+10.00pp ↑')
  })

  it('value=-0.5381 unit=pp → "53.81pp ↓" (raw ratio, 组件 *100)', () => {
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

// L4.81: raw ratio 传入, YOYGuard *100; 不再是 Sprint 13 "caller 已 *100"
describe('YOYBadge L4.81 raw-ratio 契约', () => {
  it('pp 0.05 (raw) → "+5.00pp ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0.05, unit: 'pp' } })
    expect(getText(wrapper)).toBe('+5.00pp ↑')
  })

  it('pp -0.035 (raw) → "3.50pp ↓" (abs)', () => {
    const wrapper = mount(YOYBadge, { props: { value: -0.035, unit: 'pp' } })
    expect(getText(wrapper)).toBe('3.50pp ↓')
  })

  it('pp 0 (raw) → "+0.00pp ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0, unit: 'pp' } })
    expect(getText(wrapper)).toBe('+0.00pp ↑')
  })

  it('% 0.25 (raw) → "+25.00% ↑"', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0.25, unit: '%' } })
    expect(getText(wrapper)).toBe('+25.00% ↑')
  })

  it('pp NaN → "0.00pp ↓" (fallback, value=NaN → 走 else 分支)', () => {
    // YOYBadge 模板 v-else-if="value >= 0", NaN 走 else 分支
    const wrapper = mount(YOYBadge, { props: { value: NaN, unit: 'pp' } })
    expect(getText(wrapper)).toBe('0.00pp ↓')
  })

  it('% Infinity → "数据异常" (|v|>1e6 守卫优先于显示)', () => {
    const wrapper = mount(YOYBadge, { props: { value: Infinity, unit: '%' } })
    expect(getText(wrapper)).toBe('数据异常')
  })
})

// 异常值守卫: threshold 在 raw ratio 上 (|v|>1e6)
describe('YOYBadge 异常值守卫 (L4.81 raw ratio threshold)', () => {
  it('value=1.0 unit=% → "+100.00% ↑" (raw 1.0 = 100%, 边界内正常值)', () => {
    const wrapper = mount(YOYBadge, { props: { value: 1.0, unit: '%' } })
    expect(getText(wrapper)).toBe('+100.00% ↑')
  })

  it('value=-1.0 unit=% → "100.00% ↓" (边界内负值, abs 后显示)', () => {
    const wrapper = mount(YOYBadge, { props: { value: -1.0, unit: '%' } })
    expect(getText(wrapper)).toBe('100.00% ↓')
  })

  it('value=1e7 unit=% → "数据异常" (|v|>1e6 触发守卫, 不显示炸弹)', () => {
    const wrapper = mount(YOYBadge, { props: { value: 1e7, unit: '%' } })
    expect(getText(wrapper)).toBe('数据异常')
  })

  it('value=0 unit=% → "+0.00% ↑" (零值边界, 不触发守卫)', () => {
    const wrapper = mount(YOYBadge, { props: { value: 0, unit: '%' } })
    expect(getText(wrapper)).toBe('+0.00% ↑')
  })
})
