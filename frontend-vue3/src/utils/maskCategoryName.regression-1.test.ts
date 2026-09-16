import { describe, expect, it } from 'vitest'
import { destDisplayName, maskDestsInText } from './maskCategoryName'

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
})
