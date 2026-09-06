import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { parse } from 'postcss'
import { shineMageCssVariables, shineMageTheme } from './theme'

const protectedVisualSources = [
  './App.vue',
  './components/BrandMark.vue',
  './components/NavBar.vue',
  './views/LoginView.vue',
  './views/GrowthBoardView.vue',
  './features/mission/components/MissionHero.vue',
  './features/mission/components/ImpactForecast.vue',
  './features/mission/components/ChannelPortfolio.vue',
  './features/mission/components/BusinessQuery.vue',
  './features/mission/components/MissionActionRail.vue',
]

// Resolve from the test module rather than Vite's browser asset URL transform.
const sourceUrl = (relativePath: string) => new URL(relativePath, import.meta.url)

describe('Shine Mage visual token contract', () => {
  it('uses Outfit for English presentation labels and workflow numerals', () => {
    const typographySelectors: Record<string, string[]> = {
      './components/NavBar.vue': ['.request-modal > header span', '.notify-button > span'],
      './features/mission/components/ImpactForecast.vue': ['.panel-meta', '.experiment-line span:first-child'],
      './features/mission/components/MissionHero.vue': ['.panel-meta', '.decision-route b', '.ai-recommendation div > span'],
      './features/mission/components/ChannelPortfolio.vue': ['.section-heading div:first-child > span', '.channel-name i'],
      './features/mission/components/BusinessQuery.vue': ['.section-heading div > span', '.guardrail'],
      './features/mission/components/MissionActionRail.vue': ['.state-step i', '.state-step small', '.action-copy > span', '.approve-button small'],
      './views/GrowthBoardView.vue': ['.board-title span', '.badge', '.evidence-ribbon > span'],
      './views/LoginView.vue': ['.illustration-copy li > i', '.illustration-copy li small'],
    }
    for (const [file, selectors] of Object.entries(typographySelectors)) {
      const source = readFileSync(sourceUrl(file), 'utf8')
      const sheet = parse(source.match(/<style[^>]*>([\s\S]*?)<\/style>/)![1]!)
      for (const selector of selectors) {
        let font = ''
        sheet.walkRules(selector, rule => {
          rule.walkDecls('font', declaration => { font = declaration.value })
        })
        expect(font, `${file}: ${selector}`).toContain('var(--sm-font-display)')
      }
    }
  })

  it('keeps navigation popovers outside clipping containers and wraps narrow navigation', () => {
    const source = readFileSync(sourceUrl('./components/NavBar.vue'), 'utf8')
    const sheet = parse(source.match(/<style[^>]*>([\s\S]*?)<\/style>/)![1]!)
    const styles: Record<string, Record<string, string>> = {}
    sheet.walkRules(rule => {
      const scope = rule.parent?.type === 'atrule' ? 'mobile ' : ''
      rule.walkDecls(declaration => {
        const key = scope + rule.selector
        ;(styles[key] ??= {})[declaration.prop] = declaration.value
      })
    })
    expect(styles['.navbar-main']?.overflow).toBe('visible')
    expect(styles['mobile .navbar-main']).toMatchObject({ position: 'relative', 'flex-basis': '100%' })
    expect(styles['mobile .navbar-tabs']).toMatchObject({ 'min-width': '0', 'flex-wrap': 'wrap' })
    expect(styles['mobile .navbar-item']?.position).toBe('static')
    expect(styles['mobile .navbar-popover']).toMatchObject({ right: '0', 'min-width': '0' })
  })

  it('allows responsive grid tracks to shrink below the channel table intrinsic width', () => {
    const source = readFileSync(sourceUrl('./views/GrowthBoardView.vue'), 'utf8')
    const sheet = parse(source.match(/<style[^>]*>([\s\S]*?)<\/style>/)![1]!)
    let responsiveTrack = ''
    sheet.walkAtRules('media', media => {
      if (media.params === `(max-width: ${shineMageTheme.breakpoint.board}px)`) {
        media.walkRules('.hero-grid, .intelligence-grid', rule => {
          rule.walkDecls('grid-template-columns', declaration => { responsiveTrack = declaration.value })
        })
      }
    })
    expect(responsiveTrack).toBe('minmax(0, 1fr)')
  })

  it('keeps query focus breathing token-driven with a static reduced-motion fallback', () => {
    const source = readFileSync(sourceUrl('./features/mission/components/BusinessQuery.vue'), 'utf8')
    const css = source.match(/<style[^>]*>([\s\S]*?)<\/style>/)![1]!
    const sheet = parse(css)
    const frames: Record<string, string> = {}
    let reducedMotion = false
    let focusAnimation = ''
    sheet.walkRules('.ask-form:focus-within', rule => {
      rule.walkDecls('animation', declaration => {
        if (rule.parent?.type === 'root') focusAnimation = declaration.value
      })
    })
    sheet.walkAtRules('keyframes', rule => {
      if (rule.params === 'query-focus-breath') {
        rule.walkRules(frame => {
          frame.walkDecls('box-shadow', declaration => { frames[frame.selector] = declaration.value })
        })
      }
    })
    sheet.walkAtRules('media', rule => {
      if (rule.params === '(prefers-reduced-motion: reduce)') {
        rule.walkRules('.ask-form:focus-within', focus => {
          focus.walkDecls('animation', declaration => { reducedMotion = declaration.value === 'none' })
        })
      }
    })
    expect(focusAnimation).toBe('query-focus-breath var(--sm-motion-focus-breath) infinite')
    expect(frames).toEqual({ '0%, 100%': 'var(--sm-shadow-focus-rest)', '50%': 'var(--sm-shadow-focus)' })
    expect(reducedMotion).toBe(true)
    expect(shineMageCssVariables['--sm-motion-focus-breath']).toBe(shineMageTheme.motion.focusBreath)
    expect(shineMageCssVariables['--sm-shadow-focus-rest']).toBe(shineMageTheme.shadow.focusRest)
  })

  it('the shared glass panel consumes the theme for every material property', () => {
    const css = readFileSync(sourceUrl('./styles/globals.css'), 'utf8')
    const declarations: Record<string, string> = {}
    parse(css).walkRules('.glass-panel', rule => {
      rule.walkDecls(declaration => { declarations[declaration.prop] = declaration.value })
    })
    expect(declarations).toMatchObject({
      border: 'var(--sm-dimension-px-1) solid var(--sm-line)',
      'border-radius': 'var(--sm-radius-panel)',
      background: 'var(--sm-glass)',
      'box-shadow': 'var(--sm-shadow-panel)',
      'backdrop-filter': 'var(--sm-blur-panel)',
      '-webkit-backdrop-filter': 'var(--sm-blur-panel)',
    })
  })

  it('registers and ships the real Outfit variable font with its license', () => {
    const css = readFileSync(sourceUrl('./styles/fonts.css'), 'utf8')
    const entry = readFileSync(sourceUrl('./main.ts'), 'utf8')
    const font = readFileSync(sourceUrl('./assets/fonts/Outfit-Variable.ttf'))
    const license = readFileSync(sourceUrl('../public/licenses/Outfit-OFL.txt'), 'utf8')
    expect(entry).toContain("import './styles/fonts.css'")
    expect(css).toContain("font-family: 'Outfit'")
    expect(css).toContain("url('../assets/fonts/Outfit-Variable.ttf')")
    expect(css).toContain('font-weight: 100 900')
    expect(css).toContain('font-display: swap')
    expect(font.readUInt32BE(0)).toBe(0x00010000)
    expect(font.length).toBe(110884)
    expect(createHash('sha256').update(font).digest('hex')).toBe(
      'fc7287273e66929776e2ba54f144fe699080bec29f61bf649d70d871468aeade',
    )
    expect(license).toContain('SIL OPEN FONT LICENSE Version 1.1')
    expect(shineMageTheme.font.display).toBe("'Outfit', var(--sm-font-body)")
  })

  it.each(protectedVisualSources)('%s does not duplicate brand or glass color literals', (sourcePath) => {
    const source = readFileSync(new URL(sourcePath, import.meta.url), 'utf8')

    expect(source).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(/i)
  })

  it.each(protectedVisualSources)('%s uses defined dimension tokens and approved breakpoints', (sourcePath) => {
    const source = readFileSync(new URL(sourcePath, import.meta.url), 'utf8')
    const blocks = [...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)]
    expect(blocks.length).toBeGreaterThan(0)

    for (const [, css] of blocks) {
      const sheet = parse(css!)
      sheet.walkDecls((declaration) => {
        expect(declaration.value, `${sourcePath}: ${declaration.prop}`).not.toMatch(
          /(?<![\w-])-?(?:\d*\.)?\d+(?:px|rem|em|vw|vh|dvh|vmin|ch)\b/,
        )
        for (const [name] of declaration.value.matchAll(/--sm-dimension-[\w-]+/g)) {
          expect(Object.hasOwn(shineMageCssVariables, name), `Undefined token ${name}`).toBe(true)
        }
      })
      // Custom properties are not supported in media query conditions.
      // These source-level constants must still match the theme's breakpoint contract.
      sheet.walkAtRules('media', (rule) => {
        for (const [, pixels] of rule.params.matchAll(/(?:max|min)-width:\s*(\d+)px/g)) {
          expect(Object.values(shineMageTheme.breakpoint)).toContain(Number(pixels))
        }
      })
    }
  })
})
