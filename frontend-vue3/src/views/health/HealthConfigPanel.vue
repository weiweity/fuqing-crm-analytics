<script setup lang="ts">
import { ref, computed } from 'vue'
import { NModal, NButton, NSpace, NDivider, NTag, NTabs, NTabPane, NEmpty } from 'naive-ui'
import { useQuery } from '@tanstack/vue-query'
import {
  fetchHealthConfig,
  fetchConfigHistory,
  fetchAuditLog,
} from '@/api/health'
import LoadingState from '@/components/LoadingState.vue'

const show = defineModel<boolean>('show', { default: false })

const WEIGHT_LABELS: Record<string, string> = {
  all_store_repurchase_rate: '全店复购率',
  same_product_repurchase_rate: '本品复购率',
  old_customer_gsv_ratio: '老客占比',
  old_customer_aus: '老客AUS',
  recent_7d_repurchase_users: '周均复购人数',
}

const { data: config, isLoading } = useQuery({
  queryKey: ['health-config'],
  queryFn: fetchHealthConfig,
  staleTime: 60_000,
})

// ── 配置历史 ──
const activeTab = ref('view')

const { data: historyData, isLoading: historyLoading } = useQuery({
  queryKey: ['health-config-history'],
  queryFn: () => fetchConfigHistory(20),
  enabled: computed(() => show.value && activeTab.value === 'history'),
  staleTime: 30_000,
})

// ── 审计日志 ──
const { data: auditData, isLoading: auditLoading } = useQuery({
  queryKey: ['health-config-audit'],
  queryFn: () => fetchAuditLog(50),
  enabled: computed(() => show.value && activeTab.value === 'audit'),
  staleTime: 30_000,
})

const ACTION_LABELS: Record<string, string> = {
  update: '更新配置',
  reset: '恢复默认',
  restore: '回滚版本',
}

// 格式化百分比
function fmtPct(val: number): string {
  return `${Math.round(val * 100)}%`
}

// 格式化数字
function fmtNum(val: number): string {
  return val.toLocaleString()
}
</script>

<template>
  <NModal v-model:show="show" title="健康分析配置" preset="card" style="width: 820px; max-width: 95vw; max-height: 90vh;" :segmented="{ content: true }">
    <LoadingState v-if="isLoading" />
    <template v-else-if="config">
      <NTabs v-model:value="activeTab" type="line" size="small">
        <!-- 当前配置（只读） -->
        <NTabPane name="view" tab="当前配置">
          <div style="max-height: 65vh; overflow-y: auto; padding-right: 8px;">
            <!-- 权重配置 -->
            <h3 class="text-sm font-semibold text-slate-700 mb-3">健康评分权重</h3>
            <div class="grid grid-cols-2 gap-x-6 gap-y-2">
              <div v-for="(val, key) in config.weights" :key="key" class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-24 shrink-0 text-right">{{ WEIGHT_LABELS[key as string] || key }}</span>
                <span class="text-sm font-medium text-slate-800">{{ val }}</span>
              </div>
            </div>

            <NDivider />

            <!-- 目标阈值 -->
            <h3 class="text-sm font-semibold text-slate-700 mb-3">目标阈值（满分100对应值）</h3>
            <div class="grid grid-cols-3 gap-x-6 gap-y-2">
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">全店复购率</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtPct(config.targets.all_store_repurchase_rate) }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">本品复购率</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtPct(config.targets.same_product_repurchase_rate) }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">老客占比</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtPct(config.targets.old_customer_gsv_ratio) }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">老客AUS</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtNum(config.targets.old_customer_aus) }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">周均复购人数</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtNum(config.targets.recent_7d_repurchase_users) }}</span>
              </div>
            </div>

            <NDivider />

            <!-- 告警阈值 -->
            <h3 class="text-sm font-semibold text-slate-700 mb-3">告警阈值</h3>
            <div class="grid grid-cols-3 gap-x-6 gap-y-2">
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">复购率低</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtPct(config.alert_thresholds.all_store_repurchase_rate_low) }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">老客占比低</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtPct(config.alert_thresholds.old_customer_gsv_ratio_low) }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">AUS低</span>
                <span class="text-sm font-medium text-slate-800">{{ fmtNum(config.alert_thresholds.old_customer_aus_low) }}</span>
              </div>
            </div>

            <NDivider />

            <!-- 等级边界 -->
            <h3 class="text-sm font-semibold text-slate-700 mb-3">健康等级边界</h3>
            <div class="grid grid-cols-2 gap-x-6 gap-y-2">
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">健康线</span>
                <span class="text-sm font-medium text-emerald-600">{{ config.health_level_bounds.healthy }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-500 w-20 shrink-0 text-right">关注线</span>
                <span class="text-sm font-medium text-amber-600">{{ config.health_level_bounds.warning }}</span>
              </div>
            </div>

            <NDivider />

            <div class="p-2 bg-slate-50 border border-slate-200 rounded text-xs text-slate-500">
              如需修改配置，请编辑后端 <code class="bg-slate-100 px-1 rounded">config/health_config.json</code> 文件后重启服务。
            </div>
          </div>

          <NSpace justify="end" class="mt-3">
            <NButton size="small" @click="show = false">关闭</NButton>
          </NSpace>
        </NTabPane>

        <!-- 配置历史 -->
        <NTabPane name="history" tab="配置历史">
          <div style="max-height: 65vh; overflow-y: auto; padding-right: 8px;">
            <div v-if="historyLoading" class="text-center text-slate-400 py-8">加载中...</div>
            <div v-else-if="!historyData?.history?.length" class="text-center text-slate-400 py-8">
              <NEmpty description="暂无配置历史" />
            </div>
            <table v-else class="w-full text-sm">
              <thead>
                <tr class="border-b border-slate-200">
                  <th class="text-left py-2 px-2 text-xs font-medium text-slate-500">时间</th>
                  <th class="text-left py-2 px-2 text-xs font-medium text-slate-500">动作</th>
                  <th class="text-left py-2 px-2 text-xs font-medium text-slate-500">文件名</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in historyData.history" :key="item.backup_id" class="border-b border-slate-100">
                  <td class="py-2 px-2 text-slate-600">{{ item.timestamp.replace('T', ' ').slice(0, 19) }}</td>
                  <td class="py-2 px-2">
                    <NTag size="tiny" :type="item.action === 'update' ? 'info' : item.action === 'reset' ? 'warning' : 'default'">
                      {{ ACTION_LABELS[item.action] || item.action }}
                    </NTag>
                  </td>
                  <td class="py-2 px-2 text-slate-500 text-xs">{{ item.file_name }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </NTabPane>

        <!-- 审计日志 -->
        <NTabPane name="audit" tab="审计日志">
          <div style="max-height: 65vh; overflow-y: auto; padding-right: 8px;">
            <div v-if="auditLoading" class="text-center text-slate-400 py-8">加载中...</div>
            <div v-else-if="!auditData?.logs?.length" class="text-center text-slate-400 py-8">
              <NEmpty description="暂无审计日志" />
            </div>
            <table v-else class="w-full text-sm">
              <thead>
                <tr class="border-b border-slate-200">
                  <th class="text-left py-2 px-2 text-xs font-medium text-slate-500">时间</th>
                  <th class="text-left py-2 px-2 text-xs font-medium text-slate-500">动作</th>
                  <th class="text-left py-2 px-2 text-xs font-medium text-slate-500">详情</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(log, idx) in auditData.logs" :key="idx" class="border-b border-slate-100">
                  <td class="py-2 px-2 text-slate-600 whitespace-nowrap">{{ log.timestamp.replace('T', ' ').slice(0, 19) }}</td>
                  <td class="py-2 px-2 whitespace-nowrap">
                    <NTag size="tiny" :type="log.action === 'update' ? 'info' : log.action === 'reset' ? 'warning' : 'default'">
                      {{ ACTION_LABELS[log.action] || log.action }}
                    </NTag>
                  </td>
                  <td class="py-2 px-2 text-slate-500 text-xs">
                    <span v-if="log.action === 'update' && log.details?.changed_keys">
                      变更: {{ log.details.changed_keys.join(', ') }}
                    </span>
                    <span v-else-if="log.action === 'restore' && log.details?.backup_id">
                      回滚到: {{ log.details.backup_id }}
                    </span>
                    <span v-else>-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </NTabPane>
      </NTabs>
    </template>
  </NModal>
</template>

<style scoped>
</style>
