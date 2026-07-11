import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ManualQueryButton from './ManualQueryButton.vue'

describe('ManualQueryButton', () => {
  it('blocks clicks and exposes busy state while loading', async () => {
    const wrapper = mount(ManualQueryButton, {
      props: { loading: true },
      slots: { default: '查询数据' },
    })

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('aria-busy')).toBe('true')
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
    expect(wrapper.text()).toContain('查询中')
  })

  it('emits one click when idle', async () => {
    const wrapper = mount(ManualQueryButton)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
