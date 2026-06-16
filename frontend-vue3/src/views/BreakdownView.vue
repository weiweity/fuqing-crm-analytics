<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import {
  NInputNumber, NDatePicker, NSlider,
  NRadioGroup, NRadioButton,
  NButton, NCard, NDataTable, NTag, NEmpty,
  NGrid, NGi, NTabs, NTabPane, useMessage,
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import MetricCard from '@/components/MetricCard.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { fetchBreakdownOneClick, type BreakdownRequest, type BreakdownResponse } from '@/api/breakdown'
import { formatDate } from '@/utils/date'

const message = useMessage()

/* ---------- 表单 ---------- */
const targetGmv = ref<number | null>(5_000_000)
const activityDateRange = ref<[number, number] | null>(null)
const lastYearDateRange = ref<[number, number] | null>(null)
const oldCustomerRatioTarget = ref(60)
const breakdownMode = ref<'forward' | 'reverse'>('forward')

function buildRequest(): BreakdownRequest {
  const [a0, a1] = activityDateRange.value ?? [null, null]
  const [l0, l1] = lastYearDateRange.value ?? [null, null]
  return {
    target_gmv: targetGmv.value ?? 0,
    activity_start: a0 ? formatDate(new Date(a0)) : '',
    activity_end: a1 ? formatDate(new Date(a1)) : '',
    ...(l0 && { last_year_start: formatDate(new Date(l0)) }),
    ...(l1 && { last_year_end: formatDate(new Date(l1)) }),
    old_customer_ratio_target: oldCustomerRatioTarget.value / 100,
    breakdown_mode: breakdownMode.value,
  }
}

/* ---------- API ---------- */
const { mutate: runBreakdown, data: result, isPending: loading, error }
  = useMutation<BreakdownResponse, Error, BreakdownRequest>({
    mutationFn: fetchBreakdownOneClick,
    onSuccess: () => message.success('拆解完成'),
    onError: (err) => message.error(err.message || '拆解请求失败'),
  })

function handleSubmit() {
  if (!targetGmv.value || targetGmv.value <= 0) { message.error('请输入目标GSV'); return }
  if (!activityDateRange.value) { message.error('请选择活动日期范围'); return }
  runBreakdown(buildRequest())
}

/* ---------- 渠道排序 ---------- */
import { CHANNEL_ORDER as CH_ORDER } from '@/constants/channels'

const isForward = computed(() => result.value?.mode === 'forward')

const sortedChannels = computed(() => {
  if (!result.value) return []
  const cb = result.value.new_customer?.channel_breakdown
  if (!Array.isArray(cb)) return []
  return [...cb].sort(
    (a, b) => CH_ORDER.indexOf(a.channel) - CH_ORDER.indexOf(b.channel)
  )
})

/* ---------- R 区间表格（顺拆） ---------- */
interface RIntervalRow {
  r_interval: string
  f_segment: string
  user_count: number
  ly_repurchase_rate: number
  est_repurchase_rate: number
  est_aus: number
  est_gmv: number
}

const rIntervalCols: DataTableColumns<RIntervalRow> = [
  { title: 'R区间', key: 'r_interval', width: 120, fixed: 'left', align: 'center' },
  { title: 'F段', key: 'f_segment', width: 80, align: 'center' },
  { title: '当前人数', key: 'user_count', width: 100, align: 'center', render: r => r.user_count.toLocaleString() },
  { title: '去年回购率', key: 'ly_repurchase_rate', width: 110, align: 'center', render: r => `${(r.ly_repurchase_rate * 100).toFixed(1)}%` },
  { title: '预估回购率', key: 'est_repurchase_rate', width: 110, align: 'center', render: r => `${(r.est_repurchase_rate * 100).toFixed(1)}%` },
  { title: '预估客单价', key: 'est_aus', width: 110, align: 'center', render: r => `¥${r.est_aus.toFixed(0)}` },
  { title: '预估GSV', key: 'est_gmv', width: 120, align: 'center', render: r => `¥${(r.est_gmv / 1e4).toFixed(1)}万` },
]

const rIntervalData = computed(() => {
  if (!result.value?.old_customer?.r_interval_breakdown) return []
  return result.value.old_customer.r_interval_breakdown.filter(
    (r: any) => r.est_gmv !== undefined
  ) as RIntervalRow[]
})

/* ---------- R 区间表格（倒拆） ---------- */
interface RIntervalReverseRow {
  r_interval: string
  f_segment: string
  current_users: number
  est_repurchase_rate: number
  est_aus: number
  interval_target_gmv: number
  needed_users: number
  user_gap: number
}

const rIntervalReverseCols: DataTableColumns<RIntervalReverseRow> = [
  { title: 'R区间', key: 'r_interval', width: 120, fixed: 'left', align: 'center' },
  { title: 'F段', key: 'f_segment', width: 80, align: 'center' },
  { title: '当前人数', key: 'current_users', width: 100, align: 'center', render: r => r.current_users.toLocaleString() },
  { title: '预估回购率', key: 'est_repurchase_rate', width: 110, align: 'center', render: r => `${(r.est_repurchase_rate * 100).toFixed(1)}%` },
  { title: '预估客单价', key: 'est_aus', width: 110, align: 'center', render: r => `¥${r.est_aus.toFixed(0)}` },
  { title: '区间目标GSV', key: 'interval_target_gmv', width: 130, align: 'center', render: r => `¥${(r.interval_target_gmv / 1e4).toFixed(1)}万` },
  { title: '所需人数', key: 'needed_users', width: 110, align: 'center', render: r => r.needed_users.toLocaleString() },
  { title: '人数缺口', key: 'user_gap', width: 110, align: 'center',
    render: r => h('span', {
      class: r.user_gap > 0 ? 'text-rose-600 font-semibold' : 'text-emerald-600 font-semibold'
    }, `${r.user_gap > 0 ? '+' : ''}${r.user_gap.toLocaleString()}`)
  },
]

const rIntervalReverseData = computed(() => {
  if (!result.value?.old_customer?.r_interval_breakdown) return []
  return result.value.old_customer.r_interval_breakdown.filter(
    (r: any) => r.needed_users !== undefined
  ) as RIntervalReverseRow[]
})

/* ---------- 渠道表格（顺拆） ---------- */
interface ChannelRow {
  channel: string
  ly_new_users: number
  est_new_users: number
  ly_new_aus: number
  est_new_aus: number
  est_new_gmv: number
}

const channelCols: DataTableColumns<ChannelRow> = [
  { title: '渠道', key: 'channel', width: 110, fixed: 'left', align: 'center' },
  { title: '去年新客人数', key: 'ly_new_users', width: 110, align: 'center', render: r => r.ly_new_users.toLocaleString() },
  { title: '预估新客人数', key: 'est_new_users', width: 110, align: 'center', render: r => r.est_new_users.toLocaleString() },
  { title: '去年客单价', key: 'ly_new_aus', width: 100, align: 'center', render: r => `¥${r.ly_new_aus.toFixed(0)}` },
  { title: '预估客单价', key: 'est_new_aus', width: 100, align: 'center', render: r => `¥${r.est_new_aus.toFixed(0)}` },
  { title: '预估新客GSV', key: 'est_new_gmv', width: 120, align: 'center', render: r => `¥${(r.est_new_gmv / 1e4).toFixed(1)}万` },
]

const channelData = computed(() => {
  return sortedChannels.value.filter((r: any) => r.est_new_gmv !== undefined) as ChannelRow[]
})

/* ---------- 渠道表格（倒拆） ---------- */
interface ChannelReverseRow {
  channel: string
  ly_new_users: number
  ly_new_aus: number
  channel_target_gmv: number
  needed_users: number
  user_gap: number
}

const channelReverseCols: DataTableColumns<ChannelReverseRow> = [
  { title: '渠道', key: 'channel', width: 110, fixed: 'left', align: 'center' },
  { title: '去年新客人数', key: 'ly_new_users', width: 110, align: 'center', render: r => r.ly_new_users.toLocaleString() },
  { title: '去年客单价', key: 'ly_new_aus', width: 100, align: 'center', render: r => `¥${r.ly_new_aus.toFixed(0)}` },
  { title: '渠道目标GSV', key: 'channel_target_gmv', width: 130, align: 'center', render: r => `¥${(r.channel_target_gmv / 1e4).toFixed(1)}万` },
  { title: '所需新客', key: 'needed_users', width: 110, align: 'center', render: r => r.needed_users.toLocaleString() },
  { title: '人数缺口', key: 'user_gap', width: 110, align: 'center',
    render: r => h('span', {
      class: r.user_gap > 0 ? 'text-rose-600 font-semibold' : 'text-emerald-600 font-semibold'
    }, `${r.user_gap > 0 ? '+' : ''}${r.user_gap.toLocaleString()}`)
  },
]

const channelReverseData = computed(() => {
  return sortedChannels.value.filter((r: any) => r.needed_users !== undefined) as unknown as ChannelReverseRow[]
})

/* ---------- 建议 ---------- */
const p0Suggestions = computed(() => result.value?.suggestions.filter(s => s.priority === 'P0') ?? [])
const p1Suggestions = computed(() => result.value?.suggestions.filter(s => s.priority === 'P1') ?? [])

function suggestionLabel(s: any): string {
  if (isForward.value) {
    return `Gap: ${fmtWan(s.gap_amount)}`
  }
  if (s.uv_gap != null) {
    return `UV缺口: ${fmtNum(s.uv_gap)}`
  }
  if (s.gap_users != null) {
    return `人数缺口: ${fmtNum(s.gap_users)}`
  }
  return ''
}

/* ---------- 格式化 ---------- */
function fmtWan(v?: number | null) { return v == null ? '—' : `¥${(v / 10000).toFixed(1)}万` }
function fmtNum(v?: number | null) { return v == null ? '—' : v.toLocaleString() }
function fmtPct(v?: number | null) { return v == null ? '—' : `${(v * 100).toFixed(1)}%` }
</script>

<template>
  <div class="relative">
    <!-- 待优化更新遮罩 -->
    <div class="absolute inset-0 z-50 flex items-center justify-center bg-slate-50/80 backdrop-blur-sm rounded-lg" style="min-height: 600px;">
      <div class="text-center">
        <div class="text-4xl mb-2">🔧</div>
        <div class="text-lg font-semibold text-slate-600">待优化更新</div>
        <div class="text-sm text-slate-400 mt-1">该模块正在重构中，敬请期待</div>
      </div>
    </div>

    <PageHeader title="一键拆解" subtitle="基于历史数据与目标GSV，自动拆解新老客贡献" />

    <!-- 配置表单 -->
    <n-card class="mb-5" :bordered="false" segmented>
      <template #header><span class="text-sm font-semibold text-slate-700">拆解配置</span></template>
      <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
        <n-gi>
          <div class="space-y-1">
            <label class="text-xs font-medium text-slate-500">拆解模式</label>
            <n-radio-group v-model:value="breakdownMode" size="small">
              <n-radio-button value="forward" label="顺拆" />
              <n-radio-button value="reverse" label="倒拆" />
            </n-radio-group>
          </div>
        </n-gi>
        <n-gi>
          <div class="space-y-1">
            <label class="text-xs font-medium text-slate-500">目标GSV（元）</label>
            <n-input-number v-model:value="targetGmv" :min="0" :step="100000" placeholder="请输入目标GSV" class="w-full" />
          </div>
        </n-gi>
        <n-gi>
          <div class="space-y-1">
            <label class="text-xs font-medium text-slate-500">活动日期范围</label>
            <n-date-picker v-model:value="activityDateRange" type="daterange" clearable class="w-full" />
          </div>
        </n-gi>
        <n-gi>
          <div class="space-y-1">
            <label class="text-xs font-medium text-slate-500">去年同期（可选）</label>
            <n-date-picker v-model:value="lastYearDateRange" type="daterange" clearable class="w-full" />
          </div>
        </n-gi>
        <n-gi span="2">
          <div class="space-y-1">
            <div class="flex items-center justify-between">
              <label class="text-xs font-medium text-slate-500">老客占比目标</label>
              <span class="text-xs font-semibold text-indigo-600">{{ oldCustomerRatioTarget }}%</span>
            </div>
            <n-slider v-model:value="oldCustomerRatioTarget" :min="0" :max="100" :step="1" />
          </div>
        </n-gi>
      </n-grid>
      <div class="mt-5 flex justify-end">
        <n-button type="primary" :loading="loading" @click="handleSubmit">开始拆解</n-button>
      </div>
    </n-card>

    <error-state v-if="error && !loading" :message="error.message" class="mb-5" />
    <loading-state v-if="loading && !result" class="mb-5" />

    <!-- 结果 -->
    <n-tabs v-if="result" type="line" animated>
      <!-- Tab 1 拆解总览 -->
      <n-tab-pane name="overview" tab="拆解总览">
        <n-grid :cols="4" :x-gap="16" :y-gap="16" class="mb-5" responsive="screen">
          <n-gi><metric-card title="目标GSV" :value="fmtWan(result.target_gmv)" format="currency" /></n-gi>
          <n-gi><metric-card title="预估GSV" :value="fmtWan(result.total_estimate)" format="currency" /></n-gi>
          <n-gi>
            <metric-card
              title="总Gap"
              :value="result.total_gap != null ? fmtWan(Math.abs(result.total_gap)) : '—'"
              :subtitle="result.total_gap != null ? ((result.total_gap >= 0) ? '缺口' : '超额') : '倒拆无总Gap'"
              format="currency"
            />
          </n-gi>
          <n-gi><metric-card title="Gap占比" :value="fmtPct(result.gap_ratio)" format="percent" /></n-gi>
        </n-grid>

        <n-grid :cols="2" :x-gap="16" :y-gap="16" class="mb-5" responsive="screen">
          <!-- 老客板块 -->
          <n-gi>
            <n-card title="老客板块" :bordered="false" segmented>
              <n-grid :cols="2" :x-gap="12" :y-gap="12">
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">老客人数</p><p class="text-lg font-semibold text-slate-900 tabular-nums">{{ fmtNum(result.old_customer.old_users_total) }}</p></div></n-gi>
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">老客目标</p><p class="text-lg font-semibold text-slate-900 tabular-nums">{{ fmtWan(result.old_customer.old_gmv_target) }}</p></div></n-gi>
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">老客预估</p><p class="text-lg font-semibold text-slate-900 tabular-nums">{{ fmtWan(result.old_customer.old_gmv_estimate) }}</p></div></n-gi>
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">老客Gap</p><p class="text-lg font-semibold tabular-nums" :class="(result.old_customer.old_gmv_gap ?? 0) >= 0 ? 'text-rose-600' : 'text-emerald-600'">{{ fmtWan(result.old_customer.old_gmv_gap) }}</p></div></n-gi>
              </n-grid>
              <!-- 倒拆：R区间用户缺口聚合 -->
              <div v-if="!isForward && rIntervalReverseData.length" class="mt-3 pt-3 border-t border-slate-100">
                <div class="flex items-center justify-between px-3 py-2 bg-slate-50 rounded">
                  <span class="text-xs text-slate-600">R区间总缺口人数</span>
                  <span class="text-sm font-semibold text-rose-600">
                    {{ fmtNum(rIntervalReverseData.reduce((a, r) => a + r.user_gap, 0)) }}
                  </span>
                </div>
              </div>
            </n-card>
          </n-gi>
          <!-- 新客板块 -->
          <n-gi>
            <n-card title="新客板块" :bordered="false" segmented>
              <n-grid :cols="2" :x-gap="12" :y-gap="12">
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">新客人数</p><p class="text-lg font-semibold text-slate-900 tabular-nums">{{ fmtNum(result.new_customer.new_users_total) }}</p></div></n-gi>
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">新客目标</p><p class="text-lg font-semibold text-slate-900 tabular-nums">{{ fmtWan(result.new_customer.new_gmv_target) }}</p></div></n-gi>
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">新客预估</p><p class="text-lg font-semibold text-slate-900 tabular-nums">{{ fmtWan(result.new_customer.new_gmv_estimate) }}</p></div></n-gi>
                <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">新客Gap</p><p class="text-lg font-semibold tabular-nums" :class="(result.new_customer.new_gmv_gap ?? 0) >= 0 ? 'text-rose-600' : 'text-emerald-600'">{{ fmtWan(result.new_customer.new_gmv_gap) }}</p></div></n-gi>
              </n-grid>
              <!-- 倒拆：UV缺口 -->
              <div v-if="!isForward" class="mt-3 pt-3 border-t border-slate-100 space-y-2">
                <div v-if="result.new_customer.needed_uv != null" class="flex items-center justify-between px-3 py-2 bg-slate-50 rounded">
                  <span class="text-xs text-slate-600">所需UV</span>
                  <span class="text-sm font-semibold text-slate-900">{{ fmtNum(result.new_customer.needed_uv) }}</span>
                </div>
                <div v-if="result.new_customer.uv_gap != null" class="flex items-center justify-between px-3 py-2 bg-slate-50 rounded">
                  <span class="text-xs text-slate-600">UV缺口</span>
                  <span class="text-sm font-semibold text-rose-600">{{ fmtNum(result.new_customer.uv_gap) }}</span>
                </div>
              </div>
            </n-card>
          </n-gi>
        </n-grid>

        <n-grid :cols="3" :x-gap="16" :y-gap="12" class="mb-5">
          <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">参考UV</p><p class="text-base font-semibold text-slate-900 tabular-nums">{{ fmtNum(result.new_customer.uv_reference) }}</p></div></n-gi>
          <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">入会率</p><p class="text-base font-semibold text-slate-900 tabular-nums">{{ fmtPct(result.new_customer.member_join_rate) }}</p></div></n-gi>
          <n-gi><div class="bi-card px-3 py-2"><p class="text-xs text-slate-500">活动类型</p><p class="text-base font-semibold text-slate-900 tabular-nums">{{ result.meta.activity_type }}</p></div></n-gi>
        </n-grid>

        <!-- R区间明细表格 -->
        <n-card v-if="isForward && rIntervalData.length" title="老客 R 区间 × F 段拆解明细" :bordered="false" segmented class="mb-5">
          <n-data-table :columns="rIntervalCols" :data="rIntervalData" :bordered="true" :single-line="false" size="small" :scroll-x="800" />
        </n-card>
        <n-card v-if="!isForward && rIntervalReverseData.length" title="老客 R 区间 × F 段缺口明细（倒拆）" :bordered="false" segmented class="mb-5">
          <n-data-table :columns="rIntervalReverseCols" :data="rIntervalReverseData" :bordered="true" :single-line="false" size="small" :scroll-x="950" />
        </n-card>

        <!-- 建议 -->
        <n-card :bordered="false" segmented>
          <template #header><span class="text-sm font-semibold text-slate-700">补Gap建议</span></template>
          <div v-if="p0Suggestions.length" class="mb-4">
            <div class="flex items-center gap-2 mb-2"><n-tag type="error" size="small">P0</n-tag><span class="text-xs font-semibold text-slate-600">高优先级</span></div>
            <div class="space-y-2">
              <div v-for="(item, i) in p0Suggestions" :key="`p0-${i}`" class="bi-card px-3 py-2">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm font-medium text-slate-800">{{ item.dimension }}</span>
                  <span class="text-xs text-rose-600 font-semibold">{{ suggestionLabel(item) }}</span>
                </div>
                <ul class="list-disc list-inside text-xs text-slate-600 space-y-0.5"><li v-for="(s, j) in item.suggestions" :key="j">{{ s }}</li></ul>
              </div>
            </div>
          </div>
          <div v-if="p1Suggestions.length">
            <div class="flex items-center gap-2 mb-2"><n-tag type="warning" size="small">P1</n-tag><span class="text-xs font-semibold text-slate-600">中优先级</span></div>
            <div class="space-y-2">
              <div v-for="(item, i) in p1Suggestions" :key="`p1-${i}`" class="bi-card px-3 py-2">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm font-medium text-slate-800">{{ item.dimension }}</span>
                  <span class="text-xs text-amber-600 font-semibold">{{ suggestionLabel(item) }}</span>
                </div>
                <ul class="list-disc list-inside text-xs text-slate-600 space-y-0.5"><li v-for="(s, j) in item.suggestions" :key="j">{{ s }}</li></ul>
              </div>
            </div>
          </div>
          <n-empty v-if="!p0Suggestions.length && !p1Suggestions.length" description="预估覆盖目标，无需补gap" />
        </n-card>
      </n-tab-pane>

      <!-- Tab 2 渠道明细 -->
      <n-tab-pane name="channel" tab="渠道明细">
        <n-card :bordered="false" segmented>
          <template #header>
            <div>
              <span class="text-sm font-semibold text-slate-700">{{ isForward ? '新客渠道预估' : '新客渠道缺口（倒拆）' }}</span>
              <p v-if="isForward" class="text-xs text-slate-500 mt-0.5">公式：预估新客数 = 去年新客数 × 1.1 | 预估GSV = 预估新客数 × 去年客单价</p>
              <p v-else class="text-xs text-slate-500 mt-0.5">公式：所需新客 = 渠道目标GSV ÷ 去年客单价 | 缺口 = 所需新客 − 去年新客</p>
              <p class="text-xs text-amber-600 mt-1"><span class="font-semibold">提示：</span>老客拆解基于 R 区间 × F 段维度（回购率随R变化），不区分渠道；渠道明细仅展示新客数据。老客明细参见「拆解总览」Tab的R区间表格。</p>
            </div>
          </template>
          <n-data-table
            v-if="isForward"
            :columns="channelCols"
            :data="channelData"
            :bordered="true"
            :single-line="false"
            size="small"
            :scroll-x="900"
          />
          <n-data-table
            v-else
            :columns="channelReverseCols"
            :data="channelReverseData"
            :bordered="true"
            :single-line="false"
            size="small"
            :scroll-x="900"
          />
        </n-card>
      </n-tab-pane>

      <!-- Tab 3 参考信息 -->
      <n-tab-pane name="ref" tab="参考信息">
        <n-card title="活动参数" :bordered="false" segmented class="mb-5">
          <n-grid :cols="4" :x-gap="16" :y-gap="12" responsive="screen">
            <n-gi><div class="text-xs text-slate-500">活动类型</div><div class="text-sm font-medium text-slate-800">{{ result.meta.activity_type }}</div></n-gi>
            <n-gi><div class="text-xs text-slate-500">回购率调整系数</div><div class="text-sm font-medium text-slate-800">{{ result.meta.repurchase_adjustment.toFixed(2) }}</div></n-gi>
            <n-gi><div class="text-xs text-slate-500">活动日期</div><div class="text-sm font-medium text-slate-800">{{ result.activity_period.start }} ~ {{ result.activity_period.end }}</div></n-gi>
            <n-gi><div class="text-xs text-slate-500">参考日期</div><div class="text-sm font-medium text-slate-800">{{ result.reference_period.start }} ~ {{ result.reference_period.end }}</div></n-gi>
          </n-grid>
        </n-card>
        <n-card title="拆解逻辑" :bordered="false" segmented class="mb-5">
          <div class="space-y-3">
            <div>
              <p class="text-xs font-semibold text-slate-600 mb-1">老客拆解</p>
              <p class="text-xs text-slate-500">{{ result.breakdown_logic.old_customer_formula }}</p>
              <p class="text-xs text-slate-400 mt-0.5">来源：{{ result.breakdown_logic.old_customer_source }}</p>
            </div>
            <div>
              <p class="text-xs font-semibold text-slate-600 mb-1">新客拆解</p>
              <p class="text-xs text-slate-500">{{ result.breakdown_logic.new_customer_formula }}</p>
              <p class="text-xs text-slate-400 mt-0.5">来源：{{ result.breakdown_logic.new_customer_source }}</p>
            </div>
          </div>
        </n-card>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>
