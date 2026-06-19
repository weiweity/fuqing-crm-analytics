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
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // Sprint 32.1: defend against v1208-class chromium SSL bugs (current v1217 bypassed,
    // but defense-in-depth for future HTTPS migration or external HTTPS endpoints)
    ignoreHTTPSErrors: true,
    launchOptions: { args: ['--ignore-certificate-errors'] },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
