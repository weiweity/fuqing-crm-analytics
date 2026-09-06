import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { describe, expect, it } from 'vitest'

describe('Tailwind launch-directory contract', () => {
  it('generates identical shell utilities from the repository and frontend directories', () => {
    const ui = resolve(dirname(fileURLToPath(import.meta.url)), '..')
    // Exercise the real PostCSS configuration, not a CLI --config override
    // that would hide Tailwind's process.cwd()-dependent config discovery.
    const args = ['--input-type=module', '-e', `
      import { createRequire } from 'node:module';
      import { readFileSync } from 'node:fs';
      const require = createRequire(${JSON.stringify(resolve(ui, 'package.json'))});
      const { default: config } = await import(${JSON.stringify(pathToFileURL(resolve(ui, 'postcss.config.js')).href)});
      const from = ${JSON.stringify(resolve(ui, 'src/styles/tailwind.css'))};
      const plugins = Object.entries(config.plugins).map(([name, options]) => require(name)(options));
      const result = await require('postcss')(plugins).process(readFileSync(from, 'utf8'), { from });
      process.stdout.write(result.css);
    `]
    const outputs = [resolve(ui, '..'), ui].map(cwd => execFileSync(process.execPath, args, {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 15000,
    }))
    for (const css of outputs) {
      for (const selector of ['.flex {', '.h-screen {', '.p-5 {', '.overflow-y-auto {']) {
        expect(css).toContain(selector)
      }
    }
    expect(outputs[0]).toBe(outputs[1])
  }, 30000)
})
