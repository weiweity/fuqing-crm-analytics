import { test, expect, type Page } from '@playwright/test'

const ADMIN_TOKEN = 'mock-token-admin', ADMIN_USER = 'admin', MOCK_UPLOAD_ID = 'mock-upload-12345'
const ADMIN_UPLOAD_CONFIG = { sources: [{ business_type: 'taoke', display_name: '淘客订单', allowed_extensions: ['.csv'], mode: 'append', max_size_bytes: 100*1024*1024, future_post_actions: ['refresh-taoke-cache'], replacement_warning: null }, { business_type: 'shop', display_name: '门店资料', allowed_extensions: ['.xlsx'], mode: 'single', max_size_bytes: 10*1024*1024, future_post_actions: ['rescan-spu'], replacement_warning: '此操作将替换门店资料当前生效版本' }], max_upload_bytes: 100*1024*1024 }
const MOCK_UPLOAD_RESPONSE = { upload: { upload_id: MOCK_UPLOAD_ID, business_type: 'taoke', original_filename: 'taoke-sample.csv', extension: '.csv', size_bytes: 1024, sha256: 'a'.repeat(64), uploaded_by: ADMIN_USER, uploaded_at: '2026-07-16T00:00:00Z', status: 'staged', validation: { validator: 'csv-utf8', valid: true, detected_format: 'utf-8', row_sample_count: 5, warnings: [] }, future_post_actions: ['refresh-taoke-cache'] }, duplicate: false }

async function setupApiMockGuard(page: Page) {
  const unexpectedApiCalls: string[] = []
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    unexpectedApiCalls.push(`${request.method()} ${request.url()}`)
    await route.abort()
  })
  return unexpectedApiCalls
}
async function readStoredIdentity(page: Page) { return page.evaluate(() => ({ token: sessionStorage.getItem('fq_crm_auth_token'), user: sessionStorage.getItem('fq_crm_auth_user'), isAdmin: sessionStorage.getItem('fq_crm_is_admin') })) }
async function mockAudienceApis(page: Page) {
  // glob 不匹配 query string, 用函数 predicate 匹配路径 (per Playwright 文档)
  await page.route((url: URL) => {
    const p = url.pathname
    return p.endsWith('/metrics/overview') || p.endsWith('/metrics/trend') || p.endsWith('/audience/summary') || p.endsWith('/visitor/summary') || p.endsWith('/visitor/daily-trend')
  }, (route: any) => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }))
}
async function mockCommonApis(page: Page) {
  await page.route('**/api/v1/auth/login-requests/pending', (route: any) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ pending: [] }) }))
  await page.route('**/api/v1/auth/refresh', (route: any) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) }))
}

test.describe('AdminUploadView e2e (admin happy path)', () => {
  let adminApiCalls: { url: string; method: string; body?: any }[] = []; let unexpectedApiCalls: string[] = []
  test.beforeEach(async ({ context }) => { adminApiCalls = []; await context.addInitScript(({ token, user, isAdmin }: { token: string; user: string; isAdmin: boolean }) => { sessionStorage.setItem('fq_crm_auth_token', token); sessionStorage.setItem('fq_crm_auth_user', user); sessionStorage.setItem('fq_crm_is_admin', isAdmin ? 'true' : 'false') }, { token: ADMIN_TOKEN, user: ADMIN_USER, isAdmin: true }) })
  test('admin uploads taoke, sees mock upload_id, history row appears, no real backend leak', async ({ page }) => {
    unexpectedApiCalls = await setupApiMockGuard(page)  // 低优先 fallback
    await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ username: ADMIN_USER, is_admin: true }) }))
    await page.route('**/api/v1/admin/upload-config', (route) => { adminApiCalls.push({ url: route.request().url(), method: 'GET' }); route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ADMIN_UPLOAD_CONFIG) }) })
    await page.route('**/api/v1/admin/uploads**', (route) => { adminApiCalls.push({ url: route.request().url(), method: 'GET' }); const offset = parseInt(new URL(route.request().url()).searchParams.get('offset')||'0',10); const count = adminApiCalls.filter(c=>c.url.includes('/admin/uploads')).length; return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(offset===0&&count>1? { items: [MOCK_UPLOAD_RESPONSE.upload], total: 1, limit: 20, offset: 0 } : { items:[], total:0, limit:20, offset:0 }) }) })
    await page.route('**/api/v1/admin/upload', (route) => { adminApiCalls.push({ url: route.request().url(), method: 'POST' }); route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(MOCK_UPLOAD_RESPONSE) }) })
    await mockCommonApis(page)  // 高优先覆盖 fallback
    await mockAudienceApis(page)
    await page.goto('/admin/upload'); await expect(page.getByTestId('admin-upload-view')).toBeVisible({ timeout: 10000 }); await expect(page.getByText(/当前版本只负责文件上传和暂存/)).toBeVisible()
    await page.getByTestId('business-type-select').click(); await page.getByText(/淘客订单/).click()
    await page.setInputFiles('[data-testid="file-input"] input[type="file"]', { name: 'taoke-sample.csv', mimeType: 'text/csv', buffer: Buffer.from('订单号,金额\n1,100\n2,200\n3,300\n', 'utf-8') })
    await page.getByTestId('upload-button').click(); await expect(page.getByTestId('upload-success')).toBeVisible({ timeout: 10000 }); await expect(page.getByTestId('upload-success')).toContainText(MOCK_UPLOAD_ID)
    await expect(page.getByText(/尚未在 Sprint 3A 执行/)).toBeVisible(); await expect(page.locator(`.upload-row-${MOCK_UPLOAD_ID}`)).toBeVisible({ timeout: 10000 })
    await page.waitForLoadState('networkidle')
    expect(unexpectedApiCalls).toEqual([])
  })
})

test.describe('AdminUploadView e2e (non-admin denial)', () => {
  test.beforeEach(async ({ context }) => { await context.addInitScript(({ token, user, isAdmin }: { token: string; user: string; isAdmin: boolean }) => { sessionStorage.setItem('fq_crm_auth_token', token); sessionStorage.setItem('fq_crm_auth_user', user); sessionStorage.setItem('fq_crm_is_admin', isAdmin ? 'true' : 'false') }, { token: 'token-user', user: 'fqsw', isAdmin: true }) })
  test('stale admin + /me false → /audience, no leak', async ({ page }) => {
    const unexpectedApiCalls = await setupApiMockGuard(page)
    await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ username: 'fqsw', is_admin: false }) }))
    await mockCommonApis(page)
    await mockAudienceApis(page)
    await page.goto('/admin/upload'); await page.waitForURL(/\/audience/, { timeout: 10000 }); await expect(page).toHaveURL(/\/audience/)
    await page.waitForLoadState('networkidle'); await expect(page).toHaveURL(/\/audience$/); await expect(page.getByTestId('admin-upload-view')).not.toBeVisible()
    expect(unexpectedApiCalls).toEqual([])
  })
})

test.describe('AdminUploadView e2e (/auth/me 身份收敛 per [P2-2])', () => {
  test('stale false + /me true → admin 通过', async ({ page, context }) => {
    await context.addInitScript(() => { sessionStorage.setItem('fq_crm_auth_token', 't-admin'); sessionStorage.setItem('fq_crm_auth_user', 'admin'); sessionStorage.setItem('fq_crm_is_admin', 'false') })
    const unexpectedApiCalls = await setupApiMockGuard(page)
    await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ username: 'admin', is_admin: true }) }))
    await page.route('**/api/v1/admin/upload-config', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ADMIN_UPLOAD_CONFIG) }))
    await page.route('**/api/v1/admin/uploads**', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items:[], total:0, limit:20, offset:0 }) }))
    await mockCommonApis(page)
    await page.goto('/admin/upload'); await expect(page.getByTestId('admin-upload-view')).toBeVisible({ timeout: 10000 })
    expect(await readStoredIdentity(page)).toEqual({ token: 't-admin', user: 'admin', isAdmin: 'true' })
    await page.waitForLoadState('networkidle'); expect(unexpectedApiCalls).toEqual([])
  })
  test('stale true + /me false → 降权到 /audience', async ({ page, context }) => {
    await context.addInitScript(() => { sessionStorage.setItem('fq_crm_auth_token', 't-fqsw'); sessionStorage.setItem('fq_crm_auth_user', 'fqsw'); sessionStorage.setItem('fq_crm_is_admin', 'true') })
    const unexpectedApiCalls = await setupApiMockGuard(page)
    await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ username: 'fqsw', is_admin: false }) }))
    await mockCommonApis(page)
    await mockAudienceApis(page)
    await page.goto('/admin/upload'); await page.waitForURL(/\/audience$/, { timeout: 10000 }); await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/audience$/); await expect(page.getByTestId('admin-upload-view')).not.toBeVisible()
    expect(await readStoredIdentity(page)).toEqual({ token: 't-fqsw', user: 'fqsw', isAdmin: 'false' })
    expect(page.url()).not.toContain('/login'); expect(unexpectedApiCalls).toEqual([])
  })
  test('/me 401 → 清三件套 + /login', async ({ page, context }) => {
    await context.addInitScript(() => { sessionStorage.setItem('fq_crm_auth_token', 't-stale'); sessionStorage.setItem('fq_crm_auth_user', 'admin'); sessionStorage.setItem('fq_crm_is_admin', 'true') })
    const unexpectedApiCalls = await setupApiMockGuard(page)
    await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'UNAUTHENTICATED', message: 'token expired' } }) }))
    await page.route('**/api/v1/auth/refresh', (route) => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'expired' }) }))
    await page.goto('/admin/upload'); await page.waitForURL(/\/login/, { timeout: 10000 }); await expect(page).toHaveURL(/\/login/)
    expect(await readStoredIdentity(page)).toEqual({ token: null, user: null, isAdmin: null })
    await page.waitForLoadState('networkidle'); expect(unexpectedApiCalls).toEqual([])
  })
})