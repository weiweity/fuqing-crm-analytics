import { describe, expect, it } from 'vitest'
import {
  destDisplayName,
  maskCategoryTokensInText,
  maskDestsInText,
  uniqueDisplayNames,
} from './maskCategoryName'

// Regression: ISSUE-002 — 流失 TOP 去向把原名画在表格上
// Found by /qa on 2026-09-16
// Report: .gstack/qa-reports/qa-report-127-0-0-1-15173-2026-09-16.md

describe('destDisplayName', () => {
  it('masks raw dest names and keeps passthrough tokens', () => {
    expect(destDisplayName('医用洁面')).toBe('爆款洁面')
    expect(destDisplayName('经典膜')).toBe('爆款面膜')
    expect(destDisplayName('无')).toBe('无')
    expect(destDisplayName('沉默流失')).toBe('沉默流失')
    expect(destDisplayName('')).toBe('—')
    expect(destDisplayName(null)).toBe('—')
  })

  it('replaces raw dests inside suggestion copy', () => {
    expect(maskDestsInText('触达推送 医用洁面', ['医用洁面', '白膜'])).toBe('触达推送 爆款洁面')
    expect(maskDestsInText('', ['医用洁面'])).toBe('—')
  })

  it('masks raw category tokens in ops suggestion copy', () => {
    expect(maskCategoryTokensInText('紧急:医用凝胶 流失加速')).toBe('紧急:爆款凝胶 流失加速')
    expect(maskCategoryTokensInText('触达推送 医用洁面')).toBe('触达推送 爆款洁面')
  })

  it('masks suffix-only dests and leaves already-masked dests', () => {
    expect(destDisplayName('夜间凝胶')).toBe('爆款凝胶')
    expect(maskDestsInText('触达推送 爆款洁面', ['爆款洁面'])).toBe('触达推送 爆款洁面')
    expect(maskDestsInText('触达推送 爆款洁面', [null, ''])).toBe('触达推送 爆款洁面')
    expect(maskCategoryTokensInText('')).toBe('')
    expect(maskCategoryTokensInText('  ')).toBe('')
  })

  it('replaces longer dests before shorter overlapping dests', () => {
    expect(
      maskDestsInText('触达推送 黑膜+白膜', ['白膜', '黑膜+白膜']),
    ).toBe('触达推送 爆款品类')
  })

  it('uniqueDisplayNames uses AA after Z for 27 collisions', () => {
    const names = Array.from({ length: 27 }, (_, i) => `未知小品类-${String(i).padStart(2, '0')}`)
    const map = uniqueDisplayNames(names)
    expect(map.get('未知小品类-00')).toBe('爆款品类A')
    expect(map.get('未知小品类-25')).toBe('爆款品类Z')
    expect(map.get('未知小品类-26')).toBe('爆款品类AA')
  })
})
