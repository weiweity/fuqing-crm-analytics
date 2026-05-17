<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NUpload, NButton, NIcon, NSpace, NCard, NResult, useMessage } from 'naive-ui'
import { CloudUploadOutline, ArrowBackOutline } from '@vicons/ionicons5'
import { productApi } from '@/api/scriptLibrary'
import type { UploadFileInfo } from 'naive-ui'

const router = useRouter()
const message = useMessage()

const uploading = ref(false)
const result = ref<{
  imported: number
  skipped: number
  total_products: number
} | null>(null)

// 处理上传
async function handleUpload({ file }: { file: UploadFileInfo }) {
  if (!file.file) return

  uploading.value = true
  result.value = null

  try {
    const res = await productApi.import(file.file)
    result.value = res
    message.success(`导入成功！新增 ${res.imported} 条话术`)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '导入失败')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="import-page">
    <div class="page-header">
      <n-button quaternary @click="router.back()">
        <template #icon>
          <n-icon><arrow-back-outline /></n-icon>
        </template>
        返回
      </n-button>
      <h1>导入产品话术</h1>
    </div>

    <n-card class="import-card">
      <div class="upload-area">
        <n-upload
          :max="1"
          accept=".xlsx,.xls"
          :default-upload="false"
          @change="handleUpload"
        >
          <n-button type="primary" size="large" :loading="uploading">
            <template #icon>
              <n-icon><cloud-upload-outline /></n-icon>
            </template>
            选择 Excel 文件
          </n-button>
        </n-upload>

        <p class="tip">支持 .xlsx / .xls 格式，文件大小不超过 10MB</p>
      </div>

      <!-- 导入结果 -->
      <div v-if="result" class="result-area">
        <n-result status="success" title="导入完成">
          <template #footer>
            <div class="result-stats">
              <div class="stat-item">
                <span class="stat-value">{{ result.imported }}</span>
                <span class="stat-label">新增话术</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ result.skipped }}</span>
                <span class="stat-label">跳过重复</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ result.total_products }}</span>
                <span class="stat-label">产品总数</span>
              </div>
            </div>
            <n-space justify="center" style="margin-top: 24px">
              <n-button type="primary" @click="router.push('/scripts')">
                返回话术库
              </n-button>
              <n-button @click="result = null">
                继续导入
              </n-button>
            </n-space>
          </template>
        </n-result>
      </div>
    </n-card>
  </div>
</template>

<style scoped>
.import-page {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.import-card {
  padding: 40px;
}

.upload-area {
  text-align: center;
  padding: 40px 0;
}

.tip {
  color: #999;
  font-size: 13px;
  margin-top: 12px;
}

.result-area {
  margin-top: 40px;
  padding-top: 40px;
  border-top: 1px solid #eee;
}

.result-stats {
  display: flex;
  justify-content: center;
  gap: 48px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 32px;
  font-weight: 600;
  color: #7c3aed;
}

.stat-label {
  display: block;
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}
</style>
