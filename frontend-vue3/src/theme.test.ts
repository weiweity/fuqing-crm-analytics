import { describe, expect, it } from 'vitest'
import { applyShineMageTheme, shineMageCssVariables, shineMageTheme } from './theme'

describe('Shine Mage theme SSOT', () => {
  it('keeps the approved VI colors in one token source', () => {
    expect(shineMageTheme.color.brandPrimary).toBe('#805D9D')
    expect(shineMageTheme.color.brandSecondary).toBe('#D3C3E8')
    expect(shineMageTheme.color.brandAccent).toBe('#F2FFDC')
    expect(shineMageCssVariables['--sm-gradient-primary']).toContain('#674482')
  })

  it('applies the design tokens to the document root', () => {
    applyShineMageTheme(document.documentElement)

    expect(document.documentElement.style.getPropertyValue('--sm-purple')).toBe('#805D9D')
    expect(document.documentElement.style.getPropertyValue('--sm-blur-panel')).toContain('blur(26px)')
    expect(document.documentElement.style.getPropertyValue('--sm-radius-pill')).toBe('999px')
  })
})
