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
    for (const [key, value] of Object.entries(shineMageTheme.dimension)) {
      expect(document.documentElement.style.getPropertyValue(`--sm-dimension-${key}`)).toBe(value)
    }
  })

  it('uses the requested translucent glass and lilac-white metric treatment', () => {
    expect(shineMageTheme.material.glass).toBe('rgba(255, 255, 255, 0.03)')
    expect(shineMageTheme.material.line).toBe('rgba(211, 195, 232, 0.12)')
    expect(shineMageTheme.gradient.metric).toBe('linear-gradient(96deg, #FEFCFF 0%, #D3C3E8 100%)')
    expect(shineMageCssVariables['--sm-shadow-metric']).toBe(shineMageTheme.shadow.metric)
    expect(shineMageTheme.shadow.panel).toContain('inset 0 1px 0 rgba(211, 195, 232, 0.18)')
  })
})
