import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // Sprint 41.7 fix: 本地 + CI 都用 1 worker (serial mode).
  // 之前 fullyParallel=true 在 GH Actions runner 14GB disk 上 3 worker 抢资源,
  // customer-health RFM Tab 渲染偶发 fail (其他 spec 不抢资源时 single run PASS).
  // CI runner 资源有限, serial mode 反而稳定 (53.9s 跑完 11 spec).
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  // Sprint 41.10 fix: CI runner headless Linux 渲染慢 + 没 DuckDB fetch 慢, 默认 10s/30s timeout 不够 (Sprint 41.7/41.8/41.9 CI 11/11 spec TimeoutError).
  // Sprint 41.10: CI 改 60s (beforeEach login + test body 总和 30-50s), 本地保留 10s (Chrome 真实渲染快).
  // Sprint 41.9 spec hardcode timeout 改 30000 (Sprint 41.8 config 不覆盖 spec hardcode).
  timeout: process.env.CI ? 60000 : 10000,
  expect: { timeout: process.env.CI ? 30000 : 5000 },
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // Sprint 32.1: defend against v1208-class chromium SSL bugs (current v1217 bypassed,
    // but defense-in-depth for future HTTPS migration or external HTTPS endpoints)
    ignoreHTTPSErrors: true,
    launchOptions: { args: ['--ignore-certificate-errors'] },
    // Sprint 41.8: CI navigation timeout 30s (跟全局 timeout 一致)
    navigationTimeout: process.env.CI ? 30000 : 15000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
