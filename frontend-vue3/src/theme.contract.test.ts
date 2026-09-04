import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

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

describe('Shine Mage visual token contract', () => {
  it.each(protectedVisualSources)('%s does not duplicate brand or glass color literals', (sourcePath) => {
    const source = readFileSync(new URL(sourcePath, import.meta.url), 'utf8')

    expect(source).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(/i)
  })
})
