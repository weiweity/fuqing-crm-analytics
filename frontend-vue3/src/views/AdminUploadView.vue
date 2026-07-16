<script setup lang="ts">
/**
 * Sprint 3A: admin 上传 staging-only 页面 (per Codex Sprint 3A 审计 prompt §十七).
 *
 * ⚠️ 重要：当前版本只负责文件上传和暂存，不会自动触发 ETL。
 * 上传成功不代表看板数据已经更新。future_post_actions 留 Sprint 2。
 *
 * 严格实现 per prompt §十七:
 * - 顶部固定 warning alert
 * - #upload 区: business type + file + progress + 成功/失败 + single source 确认
 * - #history 区: 列表 + filter + 分页 (limit=20, offset=(page-1)*limit)
 * - AbortController 在 onBeforeUnmount 取消所有 in-flight 请求
 * - Idempotency-Key 状态机 (per §十六)
 * - 8 个静态 data-testid (admin-upload-view / business-type-select / file-input / upload-button / upload-progress / upload-success / upload-error / upload-history) + 1 个动态 row-class (upload-row-{upload_id})
 */
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NDataTable,
  NSelect,
  NSpin,
  NTag,
  NUpload,
  NModal,
  type UploadFileInfo,
} from 'naive-ui'
import type { DataTableColumns, SelectOption } from 'naive-ui'
import {
  getAdminErrorCode,
  getAdminErrorMessage,
  getUploadConfig,
  getUploads,
  uploadAdminFile,
  type UploadConfigResponse,
  type UploadRecordOut,
  type UploadSourcePublic,
} from '@/api/admin'

type Status = 'idle' | 'validating' | 'confirming' | 'uploading' | 'success' | 'error'

// === State ===
const config = ref<UploadConfigResponse | null>(null)
const configError = ref<string | null>(null)
const sources = computed<UploadSourcePublic[]>(() => config.value?.sources ?? [])

const selectedBusinessType = ref<string | null>(null)
const currentSource = computed<UploadSourcePublic | null>(
  () => sources.value.find((s) => s.business_type === selectedBusinessType.value) ?? null,
)

const fileList = ref<UploadFileInfo[]>([])
const selectedFile = computed<File | null>(() => {
  const f = fileList.value[0]
  if (!f) return null
  // NUpload 的 file.file 是原生 File 对象
  return (f.file as File | undefined) ?? null
})

const idempotencyKey = ref('')
const status = ref<Status>('idle')
const progress = ref(0) // 0-100
const errorMessage = ref<string | null>(null)
const errorCode = ref<string | null>(null)

const successRecord = ref<UploadRecordOut | null>(null)
const successDuplicate = ref(false)

const historyItems = ref<UploadRecordOut[]>([])
const historyTotal = ref(0)
const historyLoading = ref(false)
const historyError = ref<string | null>(null)

const filterBusinessType = ref<string | null>(null)
const filterStatus = ref<string | null>(null)
const page = ref(1)
const limit = 20

// === AbortController 管理 ===
const aborters: AbortController[] = []

function makeAborted(): { controller: AbortController; signal: AbortSignal; cleanup: () => void } {
  const ac = new AbortController()
  aborters.push(ac)
  return {
    controller: ac,
    signal: ac.signal,
    cleanup: () => {
      const i = aborters.indexOf(ac)
      if (i >= 0) aborters.splice(i, 1)
    },
  }
}

function abortAll() {
  while (aborters.length) {
    const ac = aborters.pop()
    ac?.abort()
  }
}

// === History 竞态保护 (per Codex Stage 3 review [P1-1]) ===
// 单调递增 request sequence + latest-wins 状态提交
let historyController: AbortController | null = null
let historyRequestSeq = 0

function isCanceledRequest(err: unknown): boolean {
  // axios v1 CanceledError: name='CanceledError' + code='ERR_CANCELED' + axios.isCancel() true
  // 原生 fetch AbortError: name='AbortError'
  const e = err as any
  if (!e) return false
  if (e.name === 'AbortError') return true
  if (e.name === 'CanceledError') return true
  if (e.code === 'ERR_CANCELED') return true
  return false
}

// === 加载 config + history ===
async function loadConfig() {
  const { signal, cleanup } = makeAborted()
  configError.value = null
  try {
    config.value = await getUploadConfig(signal)
  } catch (err) {
    if (isCanceledRequest(err)) return
    configError.value = getAdminErrorMessage(err, '加载数据源配置失败')
  } finally {
    cleanup()
  }
}

// === History query key (per Codex 三审 [P2] 旧历史不冒充新筛选) ===
// 记录上次成功请求的 query key。失败时：
// - 同 query → 保留旧数据 + 显示错误
// - 不同 query → 清空结果
let lastSuccessfulQueryKey = ''

type HistoryQueryParams = {
  business_type?: string
  status?: string
  limit: number
  offset: number
}

function buildHistoryQueryParams(): HistoryQueryParams {
  const params: HistoryQueryParams = {
    limit,
    offset: (page.value - 1) * limit,
  }
  if (filterBusinessType.value && filterBusinessType.value !== ALL_FILTER) {
    params.business_type = filterBusinessType.value
  }
  if (filterStatus.value && filterStatus.value !== ALL_FILTER) {
    params.status = filterStatus.value
  }
  return params
}

function historyQueryKey(params: HistoryQueryParams): string {
  return JSON.stringify(params)
}

async function loadHistory() {
  const requestSeq = ++historyRequestSeq
  const queryParams = buildHistoryQueryParams()
  const queryKey = historyQueryKey(queryParams)
  const isSameSuccessfulQuery = lastSuccessfulQueryKey !== '' && queryKey === lastSuccessfulQueryKey

  if (historyController) { historyController.abort() }

  const { controller, signal, cleanup } = makeAborted()
  historyController = controller
  historyLoading.value = true
  historyError.value = null

  // 不同 query: pending 阶段立即清空旧数据
  if (!isSameSuccessfulQuery) {
    historyItems.value = []
    historyTotal.value = 0
  }

  try {
    const resp = await getUploads({ ...queryParams, signal })
    if (requestSeq !== historyRequestSeq) return
    historyItems.value = resp.items
    historyTotal.value = resp.total
    lastSuccessfulQueryKey = queryKey
  } catch (err) {
    if (isCanceledRequest(err)) return
    if (requestSeq !== historyRequestSeq) return
    if (queryKey !== lastSuccessfulQueryKey) {
      historyItems.value = []
      historyTotal.value = 0
    }
    historyError.value = getAdminErrorMessage(err, '加载上传历史失败')
  } finally {
    cleanup()
    if (historyController === controller) { historyController = null }
    if (requestSeq === historyRequestSeq) { historyLoading.value = false }
  }
}

onMounted(() => {
  void loadConfig()
  void loadHistory()
})

onBeforeUnmount(() => {
  abortAll()
})

// === Idempotency-Key 状态机 (per §十六) ===
function clearKeyAndFile() {
  fileList.value = []
  idempotencyKey.value = ''
}

function newIdempotencyKey(): string {
  // 优先 crypto.randomUUID(); fallback 简单 hex
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'idem-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

watch(selectedBusinessType, (newVal, oldVal) => {
  if (oldVal && newVal !== oldVal) {
    // 切换 business type → 清空文件 + key
    clearKeyAndFile()
    status.value = 'idle'
    errorMessage.value = null
    errorCode.value = null
    successRecord.value = null
    successDuplicate.value = false
    progress.value = 0
  }
})

watch(
  fileList,
  (list) => {
    if (list.length > 0) {
      // 选了新文件 → 生成新 key
      idempotencyKey.value = newIdempotencyKey()
    }
  },
  { deep: true },
)

// === 本地预检 (per §17.5) ===
type PreflightError = string | null
function preflight(): PreflightError {
  if (!selectedBusinessType.value) return '请先选择业务类型'
  if (!selectedFile.value) return '请选择要上传的文件'
  const src = currentSource.value
  if (!src) return '数据源配置缺失，请刷新页面'
  const file = selectedFile.value

  // 扩展名
  const dotIdx = file.name.lastIndexOf('.')
  const ext = dotIdx >= 0 ? file.name.slice(dotIdx).toLowerCase() : ''
  if (!src.allowed_extensions.map((e) => e.toLowerCase()).includes(ext)) {
    return `扩展名 ${ext} 不在允许列表 (${src.allowed_extensions.join(', ')})`
  }

  // 大小
  if (file.size > src.max_size_bytes) {
    return `文件大小 ${(file.size / 1024 / 1024).toFixed(2)} MB 超过上限 ${(src.max_size_bytes / 1024 / 1024).toFixed(2)} MB`
  }
  return null
}

// === 文件选择 handler ===
function handleFileChange(options: { fileList: UploadFileInfo[] }) {
  fileList.value = options.fileList.slice(0, 1) // max=1
}

// === 取消文件 ===
function cancelFile() {
  clearKeyAndFile()
  status.value = 'idle'
  errorMessage.value = null
  errorCode.value = null
}

// === 上传 (主流程) ===
const confirmModalVisible = ref(false)
const confirmSource = ref<UploadSourcePublic | null>(null)

async function onUploadClick() {
  status.value = 'validating'
  errorMessage.value = null
  errorCode.value = null

  const preErr = preflight()
  if (preErr) {
    status.value = 'error'
    errorMessage.value = preErr
    return
  }

  const src = currentSource.value!
  const file = selectedFile.value!

  if (src.mode === 'single') {
    // 弹窗确认 (per §17.6)
    confirmSource.value = src
    confirmModalVisible.value = true
    status.value = 'confirming'
    return
  }

  await doUpload(src, file)
}

async function confirmSingleUpload() {
  confirmModalVisible.value = false
  const src = confirmSource.value
  const file = selectedFile.value
  if (!src || !file) {
    status.value = 'error'
    errorMessage.value = '确认时文件丢失，请重新选择'
    return
  }
  await doUpload(src, file)
}

function cancelConfirm() {
  confirmModalVisible.value = false
  confirmSource.value = null
  // 取消 → 不发请求, 保留文件 + key (per §17.6)
  status.value = 'idle'
}

async function doUpload(src: UploadSourcePublic, file: File) {
  status.value = 'uploading'
  progress.value = 0
  errorMessage.value = null
  errorCode.value = null
  successRecord.value = null
  successDuplicate.value = false

  const { signal, cleanup } = makeAborted()
  try {
    const resp = await uploadAdminFile({
      businessType: src.business_type,
      file,
      idempotencyKey: idempotencyKey.value,
      signal,
      onProgress: (_loaded, _total, percent) => {
        progress.value = percent
      },
    })
    successRecord.value = resp.upload
    successDuplicate.value = resp.duplicate
    status.value = 'success'
    // 成功 / duplicate → 清空文件 + key (per §十六)
    clearKeyAndFile()
    // 刷新历史
    void loadHistory()
  } catch (err) {
    if ((err as any)?.name === 'AbortError' || (err as any)?.code === 'ERR_CANCELED') return
    // 网络失败 / 500 → 保留文件 + key (per §十六)
    status.value = 'error'
    errorCode.value = getAdminErrorCode(err) ?? null
    errorMessage.value = getAdminErrorMessage(err)
  } finally {
    cleanup()
  }
}

// === History ===
const totalPages = computed(() => Math.max(1, Math.ceil(historyTotal.value / limit)))

// Filter / page watcher 去重 (per Codex Stage 3 review [P1-1]):
// 筛选变化时如果 page != 1, 改 page=1 让 page watcher 接手 (只发 1 个请求)
watch([filterBusinessType, filterStatus], () => {
  if (page.value !== 1) {
    page.value = 1
  } else {
    void loadHistory()
  }
})

watch(page, () => {
  void loadHistory()
})

const ALL_FILTER = 'all' as const
const businessTypeOptions = computed<SelectOption[]>(() => [
  { label: '全部', value: ALL_FILTER },
  ...sources.value.map((s) => ({ label: s.display_name, value: s.business_type })),
])

const statusOptions: SelectOption[] = [
  { label: '全部', value: ALL_FILTER },
  { label: 'staged', value: 'staged' },
]

const historyColumns = computed<DataTableColumns<UploadRecordOut>>(() => [
  { title: '上传时间', key: 'uploaded_at', width: 180 },
  { title: '业务类型', key: 'business_type', width: 140 },
  { title: '文件名', key: 'original_filename', ellipsis: true },
  {
    title: '大小',
    key: 'size_bytes',
    width: 100,
    render: (row) => formatBytes(row.size_bytes),
  },
  { title: '上传人', key: 'uploaded_by', width: 100 },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) => h(NTag, { type: 'success', size: 'small' }, { default: () => row.status }),
  },
  {
    title: '校验',
    key: 'validation',
    width: 80,
    render: (row) =>
      row.validation.valid
        ? h(NTag, { type: 'success', size: 'small' }, { default: () => 'OK' })
        : h(NTag, { type: 'error', size: 'small' }, { default: () => 'FAIL' }),
  },
  { title: 'upload_id', key: 'upload_id', width: 220 },
])

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

// naive-ui NTag 渲染需要 h 已在顶部 import

// === Test-only expose: 让 vitest 能直接修改 setup state (per prompt §18 + test 实施) ===
// 不影响 production usage — 仅测试通过 wrapper.vm 访问 reactive state.
defineExpose({
  selectedBusinessType,
  fileList,
  idempotencyKey,
  page,
  filterBusinessType,
  filterStatus,
  status,
  // 供 test 直接调用 (per 三审 [P2] query key 测试)
  loadHistory,
  historyItems,
  historyTotal,
  historyError,
  historyLoading,
})
</script>

<template>
  <div class="admin-upload-shell" data-testid="admin-upload-view">
    <!-- 顶部固定 warning -->
    <NAlert
      type="warning"
      :show-icon="true"
      title="Staging-only"
      style="margin-bottom: 16px"
    >
      当前版本只负责文件上传和暂存，不会自动触发 ETL。上传成功不代表看板数据已经更新。
    </NAlert>

    <div id="upload" class="admin-upload-section">
      <h2>上传文件</h2>

      <div v-if="configError" class="admin-upload-config-error">
        <NAlert type="error" :show-icon="false" title="加载数据源失败">
          {{ configError }} (历史列表仍可查看)
        </NAlert>
      </div>

      <div v-else-if="!config" class="admin-upload-loading">
        <NSpin />
      </div>

      <template v-else>
        <div class="admin-upload-row">
          <label>业务类型</label>
          <NSelect
            v-model:value="selectedBusinessType"
            :options="sources.map((s) => ({ label: `${s.display_name} (${s.business_type})`, value: s.business_type }))"
            placeholder="选择要上传的数据源"
            :disabled="status === 'uploading'"
            data-testid="business-type-select"
            style="max-width: 360px"
          />
        </div>

        <div v-if="currentSource" class="admin-upload-source-info">
          <p>
            <strong>允许扩展名:</strong> {{ currentSource.allowed_extensions.join(', ') }}
            &nbsp;|&nbsp;
            <strong>最大:</strong> {{ formatBytes(currentSource.max_size_bytes) }}
            &nbsp;|&nbsp;
            <strong>模式:</strong> {{ currentSource.mode }}
          </p>
          <p v-if="currentSource.future_post_actions?.length">
            <strong>Sprint 2 后置动作:</strong> {{ currentSource.future_post_actions?.join(', ') }}
          </p>
        </div>

        <div class="admin-upload-row">
          <label>文件</label>
          <NUpload
            :default-upload="false"
            :max="1"
            :accept="currentSource?.allowed_extensions.join(',') ?? ''"
            :file-list="fileList"
            @change="handleFileChange"
            @remove="cancelFile"
            :disabled="!selectedBusinessType || status === 'uploading'"
            data-testid="file-input"
          >
            <NButton :disabled="!selectedBusinessType || status === 'uploading'">选择文件</NButton>
          </NUpload>
        </div>

        <div v-if="status === 'uploading'" class="admin-upload-progress" data-testid="upload-progress">
          <p>上传中: {{ selectedFile?.name ?? '' }} — {{ progress }}%</p>
          <div class="admin-upload-progress-bar">
            <div class="admin-upload-progress-bar-fill" :style="{ width: progress + '%' }" />
          </div>
        </div>

        <div v-if="status === 'success' && successRecord" class="admin-upload-success" data-testid="upload-success">
          <NAlert type="success" :show-icon="true" :title="successDuplicate ? '该请求已处理，已返回原暂存记录' : '上传成功'">
            <p>upload_id: <code>{{ successRecord.upload_id }}</code></p>
            <p>status: staged</p>
            <p v-if="successDuplicate">duplicate: true</p>
            <p>文件名: {{ successRecord.original_filename }} ({{ formatBytes(successRecord.size_bytes) }})</p>
            <p>上传时间: {{ successRecord.uploaded_at }}</p>
            <p>校验: {{ successRecord.validation.validator }} / {{ successRecord.validation.detected_format }} / 样本 {{ successRecord.validation.row_sample_count ?? '—' }} 行</p>
            <p v-if="successRecord.validation.warnings?.length">警告: {{ successRecord.validation.warnings?.join('; ') }}</p>
            <p v-if="successRecord.future_post_actions?.length">
              future_post_actions: {{ successRecord.future_post_actions?.join(', ') }}
              <em>(尚未在 Sprint 3A 执行)</em>
            </p>
          </NAlert>
        </div>

        <div v-if="status === 'error'" class="admin-upload-error" data-testid="upload-error">
          <NAlert type="error" :show-icon="true" title="上传失败">
            <p v-if="errorCode"><code>{{ errorCode }}</code></p>
            <p>{{ errorMessage }}</p>
            <p class="admin-upload-error-hint">
              文件已保留，可调整后再次点击上传（保持同一 Idempotency-Key 重试）。
            </p>
          </NAlert>
        </div>

        <div class="admin-upload-actions">
          <NButton
            type="primary"
            :loading="status === 'uploading'"
            :disabled="!selectedBusinessType || !selectedFile || status === 'uploading'"
            data-testid="upload-button"
            @click="onUploadClick"
          >
            上传并暂存
          </NButton>
        </div>
      </template>
    </div>

    <!-- single source 替换确认弹窗 -->
    <NModal
      v-model:show="confirmModalVisible"
      preset="dialog"
      title="替换确认"
      positive-text="确认替换"
      negative-text="取消"
      @positive-click="confirmSingleUpload"
      @negative-click="cancelConfirm"
      @close="cancelConfirm"
    >
      <p>{{ confirmSource?.replacement_warning ?? '此操作将替换现有数据' }}</p>
    </NModal>

    <div id="history" class="admin-upload-section" data-testid="upload-history">
      <h2>上传记录</h2>

      <div class="admin-upload-history-filters">
        <NSelect
          v-model:value="filterBusinessType"
          :options="businessTypeOptions"
          placeholder="按业务类型筛选"
          style="max-width: 200px"
        />
        <NSelect
          v-model:value="filterStatus"
          :options="statusOptions"
          placeholder="按状态筛选"
          style="max-width: 160px"
        />
        <NButton @click="loadHistory">刷新</NButton>
      </div>

      <NSpin v-if="historyLoading && historyItems.length === 0" />

      <div v-if="historyError" class="admin-upload-history-error">
        <NAlert type="error" :show-icon="true" title="加载历史失败">
          {{ historyError }}
          <NButton size="small" @click="loadHistory" style="margin-left: 8px">重试</NButton>
        </NAlert>
      </div>

      <!-- 表与 error 不再互斥 (per Codex 二审 Comment 3): 刷新失败时旧表仍可见 -->
      <NDataTable
        v-if="historyItems.length > 0 || (!historyLoading && !historyError)"
        :columns="historyColumns"
        :data="historyItems"
        :pagination="false"
        :bordered="false"
        :row-key="(row: UploadRecordOut) => row.upload_id"
        :row-class-name="(row: UploadRecordOut) => `upload-row-${row.upload_id}`"
      >
        <template #empty>
          <div style="padding: 24px; text-align: center; color: #94a3b8">暂无上传记录</div>
        </template>
      </NDataTable>

      <div v-if="historyItems.length > 0 || historyTotal > 0" class="admin-upload-history-pagination">
        <span>共 {{ historyTotal }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
        <NButton :disabled="page <= 1" @click="page = page - 1">上一页</NButton>
        <NButton :disabled="page >= totalPages" @click="page = page + 1">下一页</NButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-upload-shell {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px;
}
.admin-upload-section {
  margin-bottom: 32px;
  padding: 20px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}
.admin-upload-section h2 {
  margin: 0 0 16px 0;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}
.admin-upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.admin-upload-row label {
  min-width: 80px;
  font-weight: 500;
  color: #475569;
}
.admin-upload-source-info {
  margin: 8px 0 12px 92px;
  font-size: 13px;
  color: #475569;
}
.admin-upload-source-info p {
  margin: 4px 0;
}
.admin-upload-progress {
  margin: 12px 0;
}
.admin-upload-progress-bar {
  width: 100%;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}
.admin-upload-progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #38bdf8);
  transition: width 0.16s ease;
}
.admin-upload-actions {
  margin-top: 16px;
}
.admin-upload-error-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}
.admin-upload-history-filters {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.admin-upload-history-pagination {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  font-size: 13px;
  color: #475569;
}
.admin-upload-loading,
.admin-upload-config-error {
  padding: 24px 0;
}
</style>