import { describe, expect, it } from 'vitest'
import {
  CATEGORY_NAME_PASSTHROUGH,
  categoryDisplayName,
  destColor,
  labeledCategoryOptions,
  maskCategoryName,
  selectableCategoryNames,
  uniqueDisplayNames,
} from './maskCategoryName'

describe('maskCategoryName', () => {
  it('maps the requested display names', () => {
    expect(maskCategoryName('凉茶次抛')).toBe('爆款次抛')
    expect(maskCategoryName('经典膜')).toBe('爆款面膜')
    expect(maskCategoryName('医用洁面')).toBe('爆款洁面')
  })

  it('leaves totals and empty labels unmasked', () => {
    expect(maskCategoryName('合计')).toBe('合计')
    expect(maskCategoryName('TTL')).toBe('TTL')
    expect(maskCategoryName('全部')).toBe('全部')
    expect(maskCategoryName('全店')).toBe('全店')
    expect(maskCategoryName('')).toBe('')
    expect(maskCategoryName(null)).toBe('')
    expect(CATEGORY_NAME_PASSTHROUGH.has('合计')).toBe(true)
  })

  it('keeps raw names distinct from display labels for filters', () => {
    const raw = '凉茶次抛'
    const option = { label: maskCategoryName(raw), value: raw }
    expect(option.label).toBe('爆款次抛')
    expect(option.value).toBe('凉茶次抛')
    expect(option.value).not.toBe(option.label)
  })

  it('masks by suffix, unknown fallback, already-masked, and whitespace', () => {
    expect(maskCategoryName('  凉茶次抛  ')).toBe('爆款次抛')
    expect(maskCategoryName('某护理液')).toBe('爆款护理液')
    expect(maskCategoryName('夜间凝胶')).toBe('爆款凝胶')
    expect(maskCategoryName('未知小品类')).toBe('爆款品类')
    expect(maskCategoryName('爆款护理贴')).toBe('爆款护理贴')
  })

  it('prefers API display_name then falls back to the local mask', () => {
    expect(categoryDisplayName({ name: '凉茶次抛', display_name: '爆款次抛' })).toBe('爆款次抛')
    expect(categoryDisplayName({ name: '凉茶次抛' })).toBe('爆款次抛')
    expect(categoryDisplayName({ name: '凉茶次抛', display_name: '' })).toBe('爆款次抛')
  })

  it('disambiguates colliding masks with A/B suffixes', () => {
    const map = uniqueDisplayNames(['经典膜', '水杨酸面膜', '凉茶次抛'])
    expect(map.get('凉茶次抛')).toBe('爆款次抛')
    expect(map.get('经典膜')).not.toBe(map.get('水杨酸面膜'))
    expect(map.get('经典膜')?.startsWith('爆款面膜')).toBe(true)
    expect(map.get('水杨酸面膜')?.startsWith('爆款面膜')).toBe(true)
  })

  it('drops totals and empty names from filter options', () => {
    expect(selectableCategoryNames(['凉茶次抛', '合计', 'TTL', '', '全部', '全店', null])).toEqual([
      '凉茶次抛',
    ])
    expect(selectableCategoryNames([])).toEqual([])
  })

  it('labeledCategoryOptions prefers catalog labels and drops totals', () => {
    expect(
      labeledCategoryOptions(['经典膜', '水杨酸面膜', '合计'], {
        经典膜: '爆款面膜A',
        水杨酸面膜: '爆款面膜B',
      }),
    ).toEqual([
      { label: '爆款面膜A', value: '经典膜' },
      { label: '爆款面膜B', value: '水杨酸面膜' },
    ])
  })

  it('destColor matches masked suffix names', () => {
    expect(destColor('爆款面膜A')).toBe('#533afd')
    expect(destColor('爆款凝胶')).toBe('#ea2261')
    expect(destColor('沉默流失')).toBe('#64748b')
    expect(destColor('无')).toBe('#64748b')
  })
})
