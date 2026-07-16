/**
 * Sprint 3A Phase D: AdminUploadView tests.
 *
 * 覆盖 (per prompt §十八 case 11-14):
 * - case 11: config 加载后渲染 sources 选项 + accept 属性
 * - case 12: single source 使用服务端 replacement_warning; 取消不 POST, 确认才 POST
 * - case 13: 上传中禁用重复提交; 失败重试复用同一 Idempotency-Key
 * - case 14: 成功/duplicate/validation/future_post_actions 正确显示 + 刷新历史;
 *            empty / filter / pagination
 *
 * 测试策略:
 * - 不用 NConfigProvider wrapper (避免 wrapper.vm 是 provider 的 vm)
 * - naive-ui vi.mock importActual 透传 (AdminUploadView 不再 use useMessage, per Codex Stage 3 review [清理])
 * - script setup state 通过 defineExpose 暴露, 用 findComponent(vm) 访问
 * - naive-ui NModal/NAlert 用 teleport → 用 state-based 断言代替 DOM
 */
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// === admin API mock ===
const apiMocks = vi.hoisted(() => ({
  getUploadConfig: vi.fn(),
  uploadAdminFile: vi.fn(),
  getUploads: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getUploadConfig: apiMocks.getUploadConfig,
  uploadAdminFile: apiMocks.uploadAdminFile,
  getUploads: apiMocks.getUploads,
  getAdminErrorMessage: (err: any, fallback = '请求失败') => {
    const d = err?.data?.detail
    if (d && typeof d === 'object') {
      const m = d.message
      if (typeof m === 'string' && m.length > 0) return m
    }
    if (typeof d === 'string' && d.length > 0) return d
    const msg = err?.message
    if (typeof msg === 'string' && msg && msg !== '[object Object]') return msg
    return fallback
  },
  getAdminErrorCode: (err: any) => err?.data?.detail?.code,
  ADMIN_UPLOAD_TIMEOUT_MS: 5 * 60_000,
}))

vi.mock('naive-ui', async () => {
  // AdminUploadView 改后不再 import/use useMessage (per Codex Stage 3 review [清理])
  // 直接 importActual 即可, 不需要 useMessage mock
  return await vi.importActual<typeof import('naive-ui')>('naive-ui')
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/admin/upload', query: {}, hash: '' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

import AdminUploadView from './AdminUploadView.vue'
import type { UploadRecordOut } from '@/api/admin'

// === 完整 fixture factory (per Codex Stage 3 review [P1-1] 修假绿):
// 返回完全符合后端 contract 的 UploadRecordOut, 不含 as any.
// AdminUploadView.vue 表格执行 row.validation.valid, 必填字段缺失会报 TypeError.
function makeUploadRecord(
  uploadId: string,
  overrides: Partial<UploadRecordOut> = {},
): UploadRecordOut {
  return {
    upload_id: uploadId,
    business_type: 'taoke',
    original_filename: `${uploadId}.csv`,
    extension: '.csv',
    size_bytes: 100,
    sha256: 'a'.repeat(64),
    uploaded_by: 'admin',
    uploaded_at: '2026-07-16T00:00:00Z',
    status: 'staged',
    validation: {
      validator: 'csv-utf8',
      valid: true,
      detected_format: 'utf-8',
      row_sample_count: 1,
      warnings: [],
    },
    future_post_actions: [],
    ...overrides,
  }
}

const baseConfig = {
  sources: [
    {
      business_type: 'taoke',
      display_name: '淘客订单',
      allowed_extensions: ['.csv'],
      mode: 'append' as const,
      max_size_bytes: 100 * 1024 * 1024,
      future_post_actions: ['refresh-taoke-cache'],
      replacement_warning: null,
    },
    {
      business_type: 'shop',
      display_name: '门店资料',
      allowed_extensions: ['.xlsx'],
      mode: 'single' as const,
      max_size_bytes: 10 * 1024 * 1024,
      future_post_actions: ['rescan-spu'],
      replacement_warning: '此操作将替换门店资料当前生效版本',
    },
  ] as any,
  max_upload_bytes: 100 * 1024 * 1024,
}

const baseHistoryEmpty = { items: [], total: 0, limit: 20, offset: 0 }

function makeFile(name: string, size: number, type = 'text/csv'): File {
  return new File([new Uint8Array(size)], name, { type })
}

// === Helper: 拿到 AdminUploadView 真实 vm (脚本 setup state 通过 defineExpose 暴露) ===
function getVM(wrapper: any): any {
  return wrapper.findComponent(AdminUploadView).vm as any
}

function mountView() {
  return mount(AdminUploadView)
}

// === 测试套件 ===
describe('AdminUploadView config-driven rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getUploadConfig.mockResolvedValue(baseConfig)
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)
  })

  it('config-driven NUpload accept attribute after config loads', async () => {
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'taoke'
    await flushPromises()

    const fileInput = wrapper.find('input[type="file"]')
    expect(fileInput.exists()).toBe(true)
    expect(fileInput.attributes('accept')).toContain('.csv')
  })

  it('config renders 10 sources (via SSOT, not hardcoded)', async () => {
    const cfg = {
      sources: Array.from({ length: 10 }, (_, i) => ({
        business_type: `type-${i}`,
        display_name: `类型 ${i}`,
        allowed_extensions: ['.csv'],
        mode: 'append' as const,
        max_size_bytes: 100 * 1024 * 1024,
        future_post_actions: [],
        replacement_warning: null,
      })),
      max_upload_bytes: 100 * 1024 * 1024,
    }
    apiMocks.getUploadConfig.mockResolvedValueOnce(cfg)
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    expect(vm.sources.length).toBe(10)
  })
})

describe('AdminUploadView single source confirm flow (state-based)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getUploadConfig.mockResolvedValue(baseConfig)
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)
  })

  it('single source uses server replacement_warning, sets confirmModalVisible=true', async () => {
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'shop'
    await flushPromises()

    const file = makeFile('shop.xlsx', 1024, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    vm.fileList = [{ id: 'x', name: 'shop.xlsx', status: 'pending', file }]
    await flushPromises()

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()

    expect(vm.confirmModalVisible).toBe(true)
    expect(vm.confirmSource).not.toBeNull()
    expect(vm.confirmSource.business_type).toBe('shop')
    expect(vm.confirmSource.replacement_warning).toBe('此操作将替换门店资料当前生效版本')
    expect(apiMocks.uploadAdminFile).not.toHaveBeenCalled()
    expect(vm.status).toBe('confirming')
  })

  it('cancel confirm does NOT POST, preserves file + key', async () => {
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'shop'
    await flushPromises()

    const file = makeFile('shop.xlsx', 1024)
    vm.fileList = [{ id: 'x', name: 'shop.xlsx', status: 'pending', file }]
    await flushPromises()

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()
    expect(vm.confirmModalVisible).toBe(true)
    const keyBeforeCancel = vm.idempotencyKey

    vm.cancelConfirm()
    await flushPromises()

    expect(vm.confirmModalVisible).toBe(false)
    expect(apiMocks.uploadAdminFile).not.toHaveBeenCalled()
    expect(vm.fileList.length).toBe(1)
    expect(vm.idempotencyKey).toBe(keyBeforeCancel)
    expect(vm.status).toBe('idle')
  })

  it('confirm POSTs upload', async () => {
    apiMocks.uploadAdminFile.mockResolvedValueOnce({
      upload: {
        upload_id: 'u-shop-1',
        business_type: 'shop',
        original_filename: 'shop.xlsx',
        extension: '.xlsx',
        size_bytes: 1024,
        sha256: 'a'.repeat(64),
        uploaded_by: 'admin',
        uploaded_at: '2026-07-16T00:00:00Z',
        status: 'staged',
        validation: { validator: 'xlsx-pandas', valid: true, detected_format: 'xlsx', row_sample_count: 100, warnings: [] },
        future_post_actions: ['rescan-spu'],
      },
      duplicate: false,
    })

    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'shop'
    await flushPromises()

    const file = makeFile('shop.xlsx', 1024)
    vm.fileList = [{ id: 'x', name: 'shop.xlsx', status: 'pending', file }]
    await flushPromises()

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()
    expect(vm.confirmModalVisible).toBe(true)

    vm.confirmSingleUpload()
    await flushPromises()

    expect(apiMocks.uploadAdminFile).toHaveBeenCalledTimes(1)
    expect(apiMocks.uploadAdminFile.mock.calls[0][0].businessType).toBe('shop')
    expect(vm.status).toBe('success')
    expect(vm.successRecord.upload_id).toBe('u-shop-1')
  })
})

describe('AdminUploadView idempotency-key retry preserves same key on failure', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getUploadConfig.mockResolvedValue(baseConfig)
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)
  })

  it('failed upload keeps file + idempotencyKey, retry reuses same key', async () => {
    apiMocks.uploadAdminFile.mockRejectedValueOnce({
      status: 500,
      data: { detail: { code: 'INTERNAL', message: 'registry write failed' } },
      message: 'Request failed',
    })
    apiMocks.uploadAdminFile.mockResolvedValueOnce({
      upload: {
        upload_id: 'u-taoke-1',
        business_type: 'taoke',
        original_filename: 'taoke.csv',
        extension: '.csv',
        size_bytes: 100,
        sha256: 'b'.repeat(64),
        uploaded_by: 'admin',
        uploaded_at: '2026-07-16T00:00:00Z',
        status: 'staged',
        validation: { validator: 'csv-utf8', valid: true, detected_format: 'utf-8', row_sample_count: 5, warnings: [] },
        future_post_actions: [],
      },
      duplicate: false,
    })

    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'taoke'
    await flushPromises()

    const file = makeFile('taoke.csv', 100)
    vm.fileList = [{ id: 'x', name: 'taoke.csv', status: 'pending', file }]
    await flushPromises()
    const firstKey = vm.idempotencyKey
    expect(firstKey).not.toBe('')

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()

    expect(apiMocks.uploadAdminFile).toHaveBeenCalledTimes(1)
    expect(apiMocks.uploadAdminFile.mock.calls[0][0].idempotencyKey).toBe(firstKey)

    expect(vm.status).toBe('error')
    expect(vm.errorCode).toBe('INTERNAL')
    expect(vm.errorMessage).toBe('registry write failed')
    expect(vm.fileList.length).toBe(1)
    expect(vm.idempotencyKey).toBe(firstKey)

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()

    expect(apiMocks.uploadAdminFile).toHaveBeenCalledTimes(2)
    expect(apiMocks.uploadAdminFile.mock.calls[1][0].idempotencyKey).toBe(firstKey)
    expect(vm.status).toBe('success')
  })

  it('successful upload clears file + key + sets successRecord + future_post_actions', async () => {
    apiMocks.uploadAdminFile.mockResolvedValueOnce({
      upload: {
        upload_id: 'u-taoke-2',
        business_type: 'taoke',
        original_filename: 'taoke.csv',
        extension: '.csv',
        size_bytes: 100,
        sha256: 'c'.repeat(64),
        uploaded_by: 'admin',
        uploaded_at: '2026-07-16T00:00:00Z',
        status: 'staged',
        validation: { validator: 'csv-utf8', valid: true, detected_format: 'utf-8', row_sample_count: 5, warnings: ['row 3 空'] },
        future_post_actions: ['refresh-taoke-cache'],
      },
      duplicate: false,
    })
    apiMocks.getUploads.mockResolvedValueOnce({
      items: [{
        upload_id: 'u-taoke-2',
        business_type: 'taoke',
        original_filename: 'taoke.csv',
        extension: '.csv',
        size_bytes: 100,
        sha256: 'c'.repeat(64),
        uploaded_by: 'admin',
        uploaded_at: '2026-07-16T00:00:00Z',
        status: 'staged',
        validation: { validator: 'csv-utf8', valid: true, detected_format: 'utf-8', row_sample_count: 5, warnings: [] },
        future_post_actions: [],
      }],
      total: 1,
      limit: 20,
      offset: 0,
    })

    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'taoke'
    await flushPromises()

    const file = makeFile('taoke.csv', 100)
    vm.fileList = [{ id: 'x', name: 'taoke.csv', status: 'pending', file }]
    await flushPromises()

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()

    expect(vm.status).toBe('success')
    expect(vm.successRecord.upload_id).toBe('u-taoke-2')
    expect(vm.successRecord.future_post_actions).toContain('refresh-taoke-cache')
    expect(vm.successDuplicate).toBe(false)

    expect(vm.fileList.length).toBe(0)
    expect(vm.idempotencyKey).toBe('')

    expect(apiMocks.getUploads.mock.calls.length).toBeGreaterThan(1)
  })

  it('duplicate=true is success (not error) with explicit notice', async () => {
    apiMocks.uploadAdminFile.mockResolvedValueOnce({
      upload: {
        upload_id: 'u-dup',
        business_type: 'taoke',
        original_filename: 'taoke.csv',
        extension: '.csv',
        size_bytes: 100,
        sha256: 'd'.repeat(64),
        uploaded_by: 'admin',
        uploaded_at: '2026-07-16T00:00:00Z',
        status: 'staged',
        validation: { validator: 'csv-utf8', valid: true, detected_format: 'utf-8', row_sample_count: 5, warnings: [] },
        future_post_actions: [],
      },
      duplicate: true,
    })

    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'taoke'
    await flushPromises()

    vm.fileList = [{ id: 'x', name: 'taoke.csv', status: 'pending', file: makeFile('taoke.csv', 100) }]
    await flushPromises()

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()

    expect(vm.status).toBe('success')
    expect(vm.successDuplicate).toBe(true)
  })

  it('upload button disabled while status=uploading (per §17.7)', async () => {
    apiMocks.uploadAdminFile.mockImplementationOnce(() => new Promise(() => {}))
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'taoke'
    await flushPromises()

    vm.fileList = [{ id: 'x', name: 'taoke.csv', status: 'pending', file: makeFile('taoke.csv', 100) }]
    await flushPromises()

    const btn = wrapper.find('[data-testid="upload-button"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)

    await btn.trigger('click')
    await flushPromises()

    expect(vm.status).toBe('uploading')
    // 上传中 button disabled
    const btnAfter = wrapper.find('[data-testid="upload-button"]')
    expect((btnAfter.element as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('AdminUploadView history (empty/filter/pagination)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getUploadConfig.mockResolvedValue(baseConfig)
  })

  it('shows empty state when total=0', async () => {
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.html()).toContain('暂无上传记录')
  })

  it('renders history rows with row-class upload-row-{upload_id}', async () => {
    apiMocks.getUploads.mockResolvedValue({
      items: [
        {
          upload_id: 'abc-123',
          business_type: 'taoke',
          original_filename: 'taoke.csv',
          extension: '.csv',
          size_bytes: 100,
          sha256: 'e'.repeat(64),
          uploaded_by: 'admin',
          uploaded_at: '2026-07-16T00:00:00Z',
          status: 'staged',
          validation: { validator: 'csv-utf8', valid: true, detected_format: 'utf-8', row_sample_count: 5, warnings: [] },
          future_post_actions: [],
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.upload-row-abc-123').exists()).toBe(true)
  })

  it('passes business_type filter as query param', async () => {
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)
    const wrapper = mountView()
    await flushPromises()
    expect(apiMocks.getUploads.mock.calls[0][0].business_type).toBeUndefined()

    const vm = getVM(wrapper)
    vm.filterBusinessType = 'taoke'
    await flushPromises()
    const lastCall = apiMocks.getUploads.mock.calls[apiMocks.getUploads.mock.calls.length - 1]
    expect(lastCall[0].business_type).toBe('taoke')
  })

  it('pagination resets to page 1 when filter changes', async () => {
    apiMocks.getUploads.mockResolvedValue({
      items: [],
      total: 100,
      limit: 20,
      offset: 0,
    })
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.page = 3
    await flushPromises()

    vm.filterStatus = 'staged'
    await flushPromises()

    expect(vm.page).toBe(1)
  })
})

// === Codex Stage 3 review [P1-1]: loadHistory 异步竞态保护 ===
describe('AdminUploadView loadHistory race protection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getUploadConfig.mockResolvedValue(baseConfig)
  })

  it('stale request resolved later does NOT overwrite newer filter results', async () => {
    const responseA = {
      items: [makeUploadRecord('old-A')],
      total: 1,
      limit: 20,
      offset: 0,
    }
    const responseB = {
      items: [makeUploadRecord('new-B')],
      total: 1,
      limit: 20,
      offset: 0,
    }
    let resolveA!: (v: any) => void
    let resolveB!: (v: any) => void
    apiMocks.getUploads
      .mockImplementationOnce(() => new Promise((r) => { resolveA = r }))
      .mockImplementationOnce(() => new Promise((r) => { resolveB = r }))

    const wrapper = mountView()
    await flushPromises() // 第一次 mount loadHistory → 走 request A (未 resolve)

    // 触发 filter 变化 → 第二次 loadHistory → request B
    const vm = getVM(wrapper)
    vm.filterBusinessType = 'taoke'
    await flushPromises()

    // B 先 resolve
    resolveB(responseB)
    await flushPromises()
    expect(vm.historyItems[0].upload_id).toBe('new-B')

    // A 后 resolve (stale) — 必须被忽略
    resolveA(responseA)
    await flushPromises()
    expect(vm.historyItems[0].upload_id).toBe('new-B') // 仍是 B 的结果
  })

  it('filter change when page != 1 triggers only ONE new request via page watcher', async () => {
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)

    // 先翻到 page 3
    vm.page = 3
    await flushPromises()
    const callsBeforeFilter = apiMocks.getUploads.mock.calls.length

    // 改 filter
    vm.filterBusinessType = 'taoke'
    await flushPromises()
    const callsAfterFilter = apiMocks.getUploads.mock.calls.length

    // 期望: 只 +1 (page watcher 接手), 不是 +2
    expect(callsAfterFilter - callsBeforeFilter).toBe(1)
  })

  it('new history request aborts previous in-flight signal', async () => {
    let firstSignal: AbortSignal | undefined
    let secondSignal: AbortSignal | undefined
    apiMocks.getUploads
      .mockImplementationOnce((params: any) => {
        firstSignal = params.signal
        return new Promise(() => {}) // never resolves
      })
      .mockImplementationOnce((params: any) => {
        secondSignal = params.signal
        return Promise.resolve({ items: [], total: 0, limit: 20, offset: 0 })
      })

    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.filterBusinessType = 'taoke'
    await flushPromises()

    expect(firstSignal?.aborted).toBe(true)
    expect(secondSignal?.aborted).toBe(false)
  })

  it('history error preserves last successful historyItems (stale-tolerant)', async () => {
    const successResp = {
      items: [makeUploadRecord('keep-me')],
      total: 1,
      limit: 20,
      offset: 0,
    }
    // mount 一次成功
    apiMocks.getUploads.mockResolvedValueOnce(successResp)
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    expect(vm.historyItems[0].upload_id).toBe('keep-me')

    // DOM: .upload-row-keep-me 可见
    expect(wrapper.find('.upload-row-keep-me').exists()).toBe(true)

    // 触发 refresh 失败 (同 query, 直接调 loadHistory 保持 query key)
    apiMocks.getUploads.mockRejectedValueOnce({
      status: 500,
      data: { detail: { code: 'INTERNAL', message: 'network blip' } },
      message: 'Request failed',
    })
    await vm.loadHistory()
    await flushPromises()

    // 失败时 historyItems 保留
    expect(vm.historyItems[0].upload_id).toBe('keep-me')
    expect(vm.historyError).toBe('network blip')

    // 错误提示 DOM 可见
    expect(wrapper.text()).toContain('network blip')
    // 旧行仍然可见 (table 与 error 不互斥 per 二审 Comment 3)
    expect(wrapper.find('.upload-row-keep-me').exists()).toBe(true)
  })

  it('filter change failure clears historyItems (query key changed, per 三审 [P2])', async () => {
    const successResp = {
      items: [makeUploadRecord('type-shop')],
      total: 1,
      limit: 20,
      offset: 0,
    }
    apiMocks.getUploads.mockResolvedValueOnce(successResp)
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    expect(vm.historyItems[0].upload_id).toBe('type-shop')

    // 切 filter 后请求失败
    apiMocks.getUploads.mockRejectedValueOnce({
      status: 500,
      data: { detail: { message: 'filter switch failed' } },
      message: 'Request failed',
    })
    vm.filterBusinessType = 'shop'
    await flushPromises()

    // 旧数据清空 (shop 类型的数据不等于之前 type-shop 的数据)
    expect(vm.historyItems.length).toBe(0)
    expect(vm.historyTotal).toBe(0)
    expect(vm.historyError).toBe('filter switch failed')
  })

  it('page change failure also clears historyItems (query key changed)', async () => {
    const successResp = {
      items: [makeUploadRecord('page1')],
      total: 100,
      limit: 20,
      offset: 0,
    }
    apiMocks.getUploads.mockResolvedValueOnce(successResp)
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)

    // 翻到第 3 页失败
    apiMocks.getUploads.mockRejectedValueOnce({
      status: 500,
      data: { detail: { message: 'page switch failed' } },
      message: 'Request failed',
    })
    vm.page = 3
    await flushPromises()

    // 第 1 页数据清空 (不是第 3 页数据)
    expect(vm.historyItems.length).toBe(0)
    expect(vm.page).toBe(3)
    expect(vm.historyError).toBe('page switch failed')
  })

  it('different query clears old rows immediately while the new request is pending', async () => {
    const firstResponse = {
      items: [makeUploadRecord('old-page-row')],
      total: 1, limit: 20, offset: 0,
    }
    apiMocks.getUploads.mockResolvedValueOnce(firstResponse)
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    expect(vm.historyItems[0].upload_id).toBe('old-page-row')
    expect(wrapper.find('.upload-row-old-page-row').exists()).toBe(true)

    let rejectPending!: (reason?: unknown) => void
    apiMocks.getUploads.mockImplementationOnce(
      () => new Promise((_resolve, reject) => { rejectPending = reject }),
    )
    vm.filterBusinessType = 'shop'
    await flushPromises()

    expect(vm.historyLoading).toBe(true)
    expect(vm.historyItems).toEqual([])
    expect(vm.historyTotal).toBe(0)
    expect(wrapper.find('.upload-row-old-page-row').exists()).toBe(false)

    rejectPending({ status: 500, data: { detail: { message: 'pending query failed' } }, message: 'Request failed' })
    await flushPromises()

    expect(vm.historyLoading).toBe(false)
    expect(vm.historyItems).toEqual([])
    expect(vm.historyTotal).toBe(0)
    expect(vm.historyError).toBe('pending query failed')
    expect(wrapper.find('.upload-row-old-page-row').exists()).toBe(false)
  })

  it('null and all normalize to the same history query', async () => {
    const firstResponse = {
      items: [makeUploadRecord('all-query-row')],
      total: 1, limit: 20, offset: 0,
    }
    apiMocks.getUploads.mockResolvedValueOnce(firstResponse)
    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)

    expect(vm.filterBusinessType).toBeNull()
    expect(vm.historyItems[0].upload_id).toBe('all-query-row')

    apiMocks.getUploads.mockRejectedValueOnce({
      status: 500, data: { detail: { message: 'equivalent query refresh failed' } }, message: 'Request failed',
    })

    vm.filterBusinessType = 'all'
    await flushPromises()

    const lastCall = apiMocks.getUploads.mock.calls[apiMocks.getUploads.mock.calls.length - 1][0]
    expect(lastCall.business_type).toBeUndefined()

    expect(vm.historyItems[0].upload_id).toBe('all-query-row')
    expect(vm.historyTotal).toBe(1)
    expect(vm.historyError).toBe('equivalent query refresh failed')
    expect(wrapper.find('.upload-row-all-query-row').exists()).toBe(true)
  })
})

describe('AdminUploadView lifecycle: AbortController cleanup on unmount', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getUploadConfig.mockResolvedValue(baseConfig)
  })

  it('aborts in-flight config request when unmounted', async () => {
    let abortSignal: AbortSignal | undefined
    apiMocks.getUploadConfig.mockImplementationOnce((signal: AbortSignal) => {
      abortSignal = signal
      return new Promise(() => {})
    })
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)

    const wrapper = mountView()
    await flushPromises()
    expect(abortSignal).toBeDefined()
    expect(abortSignal?.aborted).toBe(false)

    wrapper.unmount()
    expect(abortSignal?.aborted).toBe(true)
  })

  it('aborts in-flight upload when unmounted', async () => {
    let uploadSignal: AbortSignal | undefined
    apiMocks.getUploadConfig.mockResolvedValue(baseConfig)
    apiMocks.getUploads.mockResolvedValue(baseHistoryEmpty)
    apiMocks.uploadAdminFile.mockImplementationOnce((params: any) => {
      uploadSignal = params.signal
      return new Promise(() => {})
    })

    const wrapper = mountView()
    await flushPromises()
    const vm = getVM(wrapper)
    vm.selectedBusinessType = 'taoke'
    await flushPromises()

    vm.fileList = [{ id: 'x', name: 'taoke.csv', status: 'pending', file: makeFile('taoke.csv', 100) }]
    await flushPromises()

    await wrapper.find('[data-testid="upload-button"]').trigger('click')
    await flushPromises()
    expect(uploadSignal).toBeDefined()
    expect(uploadSignal?.aborted).toBe(false)

    wrapper.unmount()
    expect(uploadSignal?.aborted).toBe(true)
  })
})