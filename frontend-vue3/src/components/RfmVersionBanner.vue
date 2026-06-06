<script setup lang="ts">
/**
 * RFM Version Banner
 *
 * 顶栏彩色横条,展示当前 active RFM manifest 的版本与切换时间。
 * 给 PM / 分析师一个视觉确认:"我现在看到的是哪一批数据"。
 *
 * 三态:
 *   - loading: skeleton 占位,不闪烁
 *   - success: 绿色横条 + 版本号 + 切换时间 + active_view
 *   - error:   灰色细条,显示"无法获取版本信息",不阻塞主页面
 *
 * 交互:
 *   - 悬停主文本 → NTooltip 展示完整 manifest 路径
 *   - 右侧刷新按钮 → 重新拉取 (loading 时禁用)
 *
 * 数据源: GET /api/v1/rfm/version (api/rfm.ts)
 */
import { computed } from 'vue'
import { NTooltip, NButton, NSkeleton, NIcon } from 'naive-ui'
import { RefreshOutline, CheckmarkCircle, AlertCircleOutline, InformationCircleOutline } from '@vicons/ionicons5'
import { useQuery } from '@tanstack/vue-query'
import { fetchRfmManifestVersion } from '@/api/rfm'
import type { RfmVersionInfo } from '@/types/rfm'

const versionQueryKey = ['rfm-manifest-version'] as const

const {
  data: versionData,
  isLoading,
  isFetching,
  error,
  refetch,
} = useQuery<RfmVersionInfo>({
  queryKey: versionQueryKey,
  queryFn: () => fetchRfmManifestVersion(),
  // manifest 不会自己变,后台手动切批才会更新;30 分钟内复用缓存,
  // 切批后点 "刷新" 按钮即可看到新版本。
  staleTime: 30 * 60 * 1000,
  retry: 1,
})

const isError = computed(() => !!error.value)
const refreshing = computed(() => isFetching.value && !isLoading.value)

function formatTs(ts: string): string {
  if (!ts) return '—'
  // 形如 "2026-06-06T03:12:44Z" → "2026-06-06 03:12:44"
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function handleRefresh() {
  refetch()
}

const statusIcon = computed(() => {
  if (isError.value) return AlertCircleOutline
  if (versionData.value && !versionData.value.active_view) return InformationCircleOutline
  return CheckmarkCircle
})
</script>

<template>
  <!-- 加载中: 静默 skeleton,占据高度避免页面抖动 -->
  <div v-if="isLoading" class="rfm-version-banner rfm-version-banner--loading">
    <n-skeleton :width="160" :height="14" style="border-radius: 3px" />
    <n-skeleton :width="80" :height="14" style="border-radius: 3px" />
  </div>

  <!-- 错误态: 灰条,不阻塞 -->
  <div
    v-else-if="isError"
    class="rfm-version-banner rfm-version-banner--error"
  >
    <n-icon :component="AlertCircleOutline" :size="14" />
    <span class="text-[12px] text-slate-500">无法获取 RFM 版本信息</span>
    <n-button text size="tiny" @click="handleRefresh" :loading="refreshing">
      重试
    </n-button>
  </div>

  <!-- 正常态: 彩色横条 -->
  <div
    v-else-if="versionData"
    class="rfm-version-banner"
    :class="[
      versionData.active_view
        ? 'rfm-version-banner--ok'
        : 'rfm-version-banner--empty',
    ]"
  >
    <n-tooltip placement="bottom" trigger="hover" :delay="200">
      <template #trigger>
        <div class="flex items-center gap-2 min-w-0">
          <n-icon :component="statusIcon" :size="14" class="flex-shrink-0" />
          <span class="text-[12px] font-medium text-slate-700 flex-shrink-0">
            RFM 数据版本:
            <span class="font-semibold text-slate-900">v{{ versionData.version }}</span>
          </span>
          <span class="text-[11px] text-slate-400">·</span>
          <span class="text-[12px] text-slate-600 flex-shrink-0">
            切换于 {{ formatTs(versionData.ts) }}
          </span>
          <span
            v-if="versionData.active_view"
            class="text-[11px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono flex-shrink-0"
          >
            {{ versionData.active_view }}
          </span>
          <span
            v-else
            class="text-[11px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 flex-shrink-0"
          >
            active_view 为空 (ETL 未跑过)
          </span>
        </div>
      </template>
      <div class="text-[11px] font-mono max-w-[520px] break-all">
        {{ versionData.path }}
      </div>
    </n-tooltip>

    <n-button
      text
      size="tiny"
      :loading="refreshing"
      :disabled="refreshing"
      @click="handleRefresh"
      class="flex-shrink-0"
    >
      <template #icon>
        <n-icon :component="RefreshOutline" />
      </template>
      刷新
    </n-button>
  </div>
</template>

<style scoped>
.rfm-version-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid transparent;
  min-height: 32px;
}

.rfm-version-banner--loading {
  background-color: #f8fafc; /* slate-50 */
  border-color: #e2e8f0; /* slate-200 */
  gap: 16px;
}

.rfm-version-banner--ok {
  background-color: rgba(21, 190, 83, 0.06); /* 品牌绿 8% */
  border-color: rgba(21, 190, 83, 0.18);
}

.rfm-version-banner--empty {
  background-color: rgba(245, 158, 11, 0.06); /* amber 6% */
  border-color: rgba(245, 158, 11, 0.18);
}

.rfm-version-banner--error {
  background-color: #f1f5f9; /* slate-100 */
  border-color: #e2e8f0;
  color: #64748b;
}
</style>
