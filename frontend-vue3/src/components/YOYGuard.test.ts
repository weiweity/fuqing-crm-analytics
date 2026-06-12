// YOYGuard 通用组件测试 (Sprint 18 #124)
// 验证: 守卫 (|v|>1e6 → "数据异常") + 格式化 (4 unit 类型) + null/NaN/Infinity fallback
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import YOYGuard from './YOYGuard.vue'

function getText(wrapper: ReturnType<typeof mount>): string {
  return wrapper.text().trim()
}

function getHtml(wrapper: ReturnType<typeof mount>): string {
  return wrapper.html()
}

describe('YOYGuard display', () => {
  it('value=14 unit=% → "14.00%" (默认 precision 2, caller 已 *100)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 14 } })
    expect(getText(wrapper)).toBe('14.00%')
  })

  it('value=5.5 unit=pp → "5.50pp"', () => {
    const wrapper = mount(YOYGuard, { props: { value: 5.5, unit: 'pp' } })
    expect(getText(wrapper)).toBe('5.50pp')
  })

  it('value=2.5 unit=pp precision=1 → "2.5pp" (precision prop 控制小数位)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 2.5, unit: 'pp', precision: 1 } })
    expect(getText(wrapper)).toBe('2.5pp')
  })

  it('value=-7.5 unit=% → "7.50%" (abs 后显示, 符号交给 caller)', () => {
    const wrapper = mount(YOYGuard, { props: { value: -7.5, unit: '%' } })
    expect(getText(wrapper)).toBe('7.50%')
  })

  it('value=null → "—" (默认 empty)', () => {
    const wrapper = mount(YOYGuard, { props: { value: null } })
    expect(getText(wrapper)).toBe('—')
  })

  it('value=undefined → "—" (默认 empty)', () => {
    const wrapper = mount(YOYGuard, { props: { value: undefined } })
    expect(getText(wrapper)).toBe('—')
  })

  it('value=null empty="-" → "-" (custom empty, RFMSegmentDrilldown 用法)', () => {
    const wrapper = mount(YOYGuard, { props: { value: null, empty: '-' } })
    expect(getText(wrapper)).toBe('-')
  })

  it('value=NaN → "0.00%" (NaN fallback, 跟原 humanizeChange 契约一致)', () => {
    const wrapper = mount(YOYGuard, { props: { value: NaN } })
    expect(getText(wrapper)).toBe('0.00%')
  })

  it('value=Infinity → "数据异常" (|Infinity|>1e6 守卫优先于 fallback)', () => {
    // 跟 backend/contracts/types.py PercentageField "真实值 > 1e6 建议前端 YOYBadge 守卫" 一致
    const wrapper = mount(YOYGuard, { props: { value: Infinity } })
    expect(getText(wrapper)).toBe('数据异常')
  })

  it('value=1e7 → "数据异常" (|v|>1e6 触发守卫, 不显示炸弹)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 1e7, unit: '%' } })
    expect(getText(wrapper)).toBe('数据异常')
  })

  it('value=-1e6-1 → "数据异常" (负值超过 -1e6)', () => {
    const wrapper = mount(YOYGuard, { props: { value: -1e6 - 1, unit: 'pp' } })
    expect(getText(wrapper)).toBe('数据异常')
  })

  it('value=1e6 → "1000000.00%" (边界值, |v|==1e6 不触发守卫)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 1e6, unit: '%' } })
    expect(getText(wrapper)).toBe('1000000.00%')
  })

  it('value=100 unit=raw → "100.00" (raw unit 不加后缀)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 100, unit: 'raw' } })
    expect(getText(wrapper)).toBe('100.00')
  })

  it('value=0 unit=% → "0.00%" (零值边界, abs 后显示)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 0, unit: '%' } })
    expect(getText(wrapper)).toBe('0.00%')
  })

  it('value=53.81 unit=pp precision=2 → "53.81pp" (Sprint 13 契约 caller 已 *100)', () => {
    // 模拟 backend yoy_ratio() 返 0.5381 → caller *100 → 53.81
    const wrapper = mount(YOYGuard, { props: { value: 53.81, unit: 'pp' } })
    expect(getText(wrapper)).toBe('53.81pp')
  })
})


// ============================================================
// Sprint 20 P1-2: styled 模式 (替代 YOYBadge, 9 组件迁移)
// ============================================================

describe('YOYGuard styled mode (替代 YOYBadge)', () => {
  it('value=null styled=true → "—" (YOYBadge 同款 null 守卫)', () => {
    const wrapper = mount(YOYGuard, { props: { value: null, styled: true } })
    expect(getText(wrapper)).toBe('—')
  })

  it('value=14 unit=% styled=true → "+14.00% ↑" (绿色, YOYBadge 同款)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 14, unit: '%', styled: true } })
    expect(getText(wrapper)).toBe('+14.00% ↑')
    // 颜色: 绿 #108c3d
    expect(getHtml(wrapper)).toContain('rgb(16, 140, 61)')  // #108c3d 绿色, jsdom 渲染成 rgb 形式
  })

  it('value=-7.5 unit=pp styled=true → "7.50pp ↓" (红色, abs 符号由 YOYGuard 处理)', () => {
    const wrapper = mount(YOYGuard, { props: { value: -7.5, unit: 'pp', styled: true } })
    expect(getText(wrapper)).toBe('7.50pp ↓')
    // 颜色: 红 #c41d4e
    expect(getHtml(wrapper)).toContain('rgb(196, 29, 78)')  // #c41d4e 红色, jsdom 渲染成 rgb 形式
  })

  it('value=5.5 unit=pp precision=1 styled=true → "+5.5pp ↑" (precision 1 位小数)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 5.5, unit: 'pp', precision: 1, styled: true } })
    expect(getText(wrapper)).toBe('+5.5pp ↑')
  })

  it('value=0 unit=% styled=true → "+0.00% ↑" (零值走正数分支 v>=0)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 0, unit: '%', styled: true } })
    expect(getText(wrapper)).toBe('+0.00% ↑')
  })

  it('value=1e7 unit=% styled=true → "数据异常" (YOYBadge 同款 |v|>1e6 守卫, 灰色)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 1e7, unit: '%', styled: true } })
    expect(getText(wrapper)).toBe('数据异常')
    expect(getHtml(wrapper)).toContain('text-slate-400')
    expect(getHtml(wrapper)).toContain('title="数据异常')
  })

  it('value=-1e6-1 unit=pp styled=true → "数据异常" (负值超过 -1e6 守卫)', () => {
    const wrapper = mount(YOYGuard, { props: { value: -1e6 - 1, unit: 'pp', styled: true } })
    expect(getText(wrapper)).toBe('数据异常')
  })

  it('value=1e6 unit=% styled=true → "+1000000.00% ↑" (边界值 |v|==1e6 不触发守卫)', () => {
    const wrapper = mount(YOYGuard, { props: { value: 1e6, unit: '%', styled: true } })
    expect(getText(wrapper)).toBe('+1000000.00% ↑')
  })
})
