import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import BrandMark from './BrandMark.vue'
import { shineMageTheme } from '../theme'

// Keep filesystem checks out of Vite's static browser-asset URL transform.
const sourceUrl = (path: string) => new URL(path, import.meta.url)

describe('approved Shine Mage source logo', () => {
  it('favicon clips only the original hat, with no wordmark or redrawing', () => {
    const svg = readFileSync(sourceUrl('../../public/shine-mage-mark.svg'), 'utf8')
    const png = readFileSync(sourceUrl('../assets/brand/shine-mage.png'))
    expect(svg).toContain('viewBox="-4 -4 54 54"')
    expect(svg).toContain('overflow="hidden"')
    expect(svg).toContain(png.toString('base64'))
    const html = readFileSync(sourceUrl('../../index.html'), 'utf8')
    expect(html).toContain('href="/shine-mage-mark.svg"')
    expect(html).not.toContain('data:image/png;base64')
  })
  it('uses the original combined logo instead of a redrawn symbol', () => {
    const wrapper = mount(BrandMark)
    const logo = wrapper.get('img')
    expect(logo.attributes('alt')).toBe('SHINE MAGE')
    expect(logo.attributes('width')).toBe('249')
    expect(logo.attributes('height')).toBe('45')
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.text()).toContain('伸美集团 · CRM 增长分析平台')
    expect(wrapper.classes()).toContain('inverse')
  })

  it('preserves compact and original-color variants', () => {
    const wrapper = mount(BrandMark, { props: { compact: true, inverse: false } })
    expect(wrapper.classes()).toContain('compact')
    expect(wrapper.classes()).not.toContain('inverse')
    expect(wrapper.find('small').exists()).toBe(false)
    expect(wrapper.get('img').attributes('alt')).toBe('SHINE MAGE')
  })

  it('ships the exact user-authorized Figma PNG', () => {
    const logo = readFileSync(sourceUrl('../assets/brand/shine-mage.png'))
    expect(logo.length).toBe(3662)
    expect(logo.readUInt32BE(16)).toBe(249)
    expect(logo.readUInt32BE(20)).toBe(45)
    expect(createHash('sha256').update(logo).digest('hex')).toBe('21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000')
  })

  it('preserves aspect ratio and applies inverse through the theme', () => {
    const source = readFileSync(sourceUrl('./BrandMark.vue'), 'utf8')
    expect(source).toContain('height: auto')
    expect(source).toContain('object-fit: contain')
    expect(source).toContain('flex-direction: row')
    expect(source).toContain('gap: var(--sm-dimension-px-12)')
    expect(source).toContain('filter: var(--sm-filter-brand-inverse)')
    expect(shineMageTheme.filter.brandInverse).toBe('brightness(0) invert(1)')
  })
})
