// Sprint 11 S11-4: vitest 单元测试样板 (立框架)
// EmptyState.vue 是最简单的纯展示组件, 适合第一个 vitest 测试
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmptyState from './EmptyState.vue'

describe('EmptyState', () => {
  it('renders default description when no prop', () => {
    const wrapper = mount(EmptyState)
    expect(wrapper.text()).toContain('暂无数据')
  })

  it('renders custom description when prop provided', () => {
    const wrapper = mount(EmptyState, {
      props: { description: '没有匹配订单' },
    })
    expect(wrapper.text()).toContain('没有匹配订单')
    expect(wrapper.text()).not.toContain('暂无数据')
  })

  it('renders emoji', () => {
    const wrapper = mount(EmptyState)
    expect(wrapper.text()).toContain('📭')
  })

  it('has correct DOM structure', () => {
    const wrapper = mount(EmptyState)
    expect(wrapper.find('div').exists()).toBe(true)
    expect(wrapper.find('p').exists()).toBe(true)
  })
})
