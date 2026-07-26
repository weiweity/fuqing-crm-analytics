import { readFileSync, statSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(__dirname, '..')

describe('frontend security hosting', () => {
  it.each(['rive.wasm', 'rive_fallback.wasm'])(
    'self-hosts the package-matched Rive runtime: %s',
    (fileName) => {
      const hostedPath = resolve(frontendRoot, 'public', 'riv', fileName)
      const packagePath = resolve(
        frontendRoot,
        'node_modules',
        '@rive-app',
        'canvas',
        fileName,
      )

      expect(statSync(hostedPath).size).toBeGreaterThan(1_000_000)
      expect(readFileSync(hostedPath).equals(readFileSync(packagePath))).toBe(true)
    },
  )

  it('enforces a same-origin preview CSP that permits only WASM compilation', () => {
    const viteConfig = readFileSync(resolve(frontendRoot, 'vite.config.ts'), 'utf8')

    expect(viteConfig).toContain('"script-src \'self\' \'wasm-unsafe-eval\'"')
    expect(viteConfig).toContain(
      'PREVIEW_CONTENT_SECURITY_POLICY = buildContentSecurityPolicy("\'self\'")',
    )
    expect(viteConfig).toContain(
      'headers: securityHeaders(PREVIEW_CONTENT_SECURITY_POLICY)',
    )
    expect(viteConfig).not.toMatch(
      /PREVIEW_CONTENT_SECURITY_POLICY\s*=.*https?:/i,
    )
  })
})
