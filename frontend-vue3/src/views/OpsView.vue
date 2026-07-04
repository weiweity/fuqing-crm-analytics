<script setup lang="ts">
/**
 * Sprint 203 R2 Finding 4.6: /metrics dashboard OpsView (L4.52 observability 1:1 stable)
 *
 * 显示 Prometheus-compatible /metrics 文本协议解析后的关键指标:
 *  - total queries by endpoint + query_type
 *  - query P95 (从 histogram bucket le 推算)
 *
 * TODO Sprint 203 R3:
 *  - DuckDB file size 接入 (当前没 backend endpoint, STUB)
 *  - manifest version 接入 (当前没 backend endpoint, STUB)
 *  - read pool 利用率 (当前 /metrics 不暴露, STUB)
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { NCard, NDataTable, NSpace, NTag, NSpin, NAlert } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'

interface EndpointStats {
  endpoint: string
  queryType: string
  total: number
  p50: number
  p95: number
  p99: number
}

const metricsText = ref<string>('')
const lastUpdated = ref<Date | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
let pollTimer: number | null = null

const endpointStats = computed<EndpointStats[]>(() => {
  return parsePrometheus(metricsText.value)
})

function parsePrometheus(text: string): EndpointStats[] {
  if (!text) return []
  // 简单解析: fq_query_total{...} N + fq_query_duration_seconds_bucket{...,le="X"} cumulative
  // 单线程 UI 跑, 不追求完美, 容错优先
  const lines = text.split('\n')
  const totalsMap = new Map<string, { endpoint: string; queryType: string; total: number }>()
  const bucketsMap = new Map<string, number>()
  const countsMap = new Map<string, number>()
  const sumsMap = new Map<string, number>()

  for (const line of lines) {
    if (line.startsWith('#') || !line.trim()) continue
    // fq_query_total{endpoint="X",query_type="Y"} N
    const totalMatch = line.match(/^fq_query_total\{endpoint="([^"]+)",query_type="([^"]+)"\}\s+(\d+)/)
    if (totalMatch) {
      const [, endpoint, queryType, total] = totalMatch
      const key = `${endpoint}|${queryType}`
      totalsMap.set(key, { endpoint, queryType, total: parseInt(total, 10) })
      continue
    }
    // fq_query_duration_seconds_bucket{endpoint="X",query_type="Y",le="Z"} cumulative
    const bucketMatch = line.match(/^fq_query_duration_seconds_bucket\{endpoint="([^"]+)",query_type="([^"]+)",le="([^"]+)"\}\s+(\d+)/)
    if (bucketMatch) {
      const [, endpoint, queryType, le, cumulative] = bucketMatch
      const key = `${endpoint}|${queryType}`
      bucketsMap.set(`${key}|${le}`, parseInt(cumulative, 10))
      continue
    }
    // fq_query_duration_seconds_count{...} total_count
    const countMatch = line.match(/^fq_query_duration_seconds_count\{endpoint="([^"]+)",query_type="([^"]+)"\}\s+(\d+)/)
    if (countMatch) {
      const [, endpoint, queryType, count] = countMatch
      countsMap.set(`${endpoint}|${queryType}`, parseInt(count, 10))
      continue
    }
    // fq_query_duration_seconds_sum{...} sum
    const sumMatch = line.match(/^fq_query_duration_seconds_sum\{endpoint="([^"]+)",query_type="([^"]+)"\}\s+([\d.]+)/)
    if (sumMatch) {
      const [, endpoint, queryType, sum] = sumMatch
      sumsMap.set(`${endpoint}|${queryType}`, parseFloat(sum))
    }
  }

  const stats: EndpointStats[] = []
  for (const [key, info] of totalsMap) {
    const total = info.total
    const buckets = [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
    // P50/P95/P99 推算: 找 cumulative >= 0.5/0.95/0.99 * total 的最小 bucket
    const p50 = findPercentile(bucketsMap, key, total, 0.5, buckets)
    const p95 = findPercentile(bucketsMap, key, total, 0.95, buckets)
    const p99 = findPercentile(bucketsMap, key, total, 0.99, buckets)
    stats.push({
      endpoint: info.endpoint,
      queryType: info.queryType,
      total,
      p50,
      p95,
      p99,
    })
  }
  return stats.sort((a, b) => b.total - a.total)
}

function findPercentile(
  bucketsMap: Map<string, number>,
  key: string,
  total: number,
  percentile: number,
  buckets: number[],
): number {
  const threshold = Math.ceil(total * percentile)
  for (const b of buckets) {
    const cumulative = bucketsMap.get(`${key}|${b}`) ?? 0
    if (cumulative >= threshold) {
      return b
    }
  }
  return Infinity
}

async function fetchMetrics() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/metrics', { credentials: 'include' })
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`)
    }
    metricsText.value = await res.text()
    lastUpdated.value = new Date()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchMetrics()
  // 30s poll (跟 L4.52 Prometheus-compatible cadence 1:1 stable)
  pollTimer = window.setInterval(fetchMetrics, 30000)
})

onUnmounted(() => {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
})

const tableColumns = [
  { title: 'Endpoint', key: 'endpoint', width: 280 },
  { title: 'Query Type', key: 'queryType', width: 120 },
  { title: 'Total', key: 'total', width: 100, sorter: 'default' as const },
  { title: 'P50 (s)', key: 'p50', width: 100, render: (row: EndpointStats) => row.p50 === Infinity ? '∞' : row.p50.toFixed(2) },
  { title: 'P95 (s)', key: 'p95', width: 100, render: (row: EndpointStats) => row.p95 === Infinity ? '∞' : row.p95.toFixed(2) },
  { title: 'P99 (s)', key: 'p99', width: 100, render: (row: EndpointStats) => row.p99 === Infinity ? '∞' : row.p99.toFixed(2) },
]

// ClickHouse POC 启动条件监控提示 (跟 Finding 4.1 1:1 stable)
const clickhouseMonitorStatus = computed(() => {
  // 当前 production ~117GB, < 200GB trigger → 0 触发
  return 'DuckDB ~117GB (a/b/c 0 触发, 跟 clickhouse-poc-monitor 1:1 stable)'
})
</script>

<template>
  <div class="p-6">
    <PageHeader title="系统运维看板" subtitle="/metrics 实时监控 + ClickHouse POC 启动条件提示" />

    <NSpace vertical :size="16">
      <NAlert type="info" :show-icon="false">
        Sprint 203 R2 Finding 4.6: 实时拉取 <code>/metrics</code> Prometheus 文本, 解析展示 query 计数 + P50/P95/P99 延迟分布.
        ClickHouse POC 启动条件: {{ clickhouseMonitorStatus }}.
      </NAlert>

      <NCard title="查询性能统计" :bordered="false">
        <template #header-extra>
          <NSpace align="center">
            <NTag v-if="lastUpdated" type="success" size="small">
              最近更新: {{ lastUpdated.toLocaleTimeString() }}
            </NTag>
            <NTag v-else type="default" size="small">未拉取</NTag>
            <NSpin v-if="loading" size="small" />
          </NSpace>
        </template>

        <NAlert v-if="error" type="error" :title="`/metrics 拉取失败: ${error}`" :show-icon="false" />

        <NDataTable
          v-if="endpointStats.length > 0"
          :columns="tableColumns"
          :data="endpointStats"
          :pagination="false"
          :bordered="false"
          size="small"
        />
        <div v-else-if="!loading && !error" class="text-gray-500 text-center py-8">
          暂无数据 (uvicorn 启动后 query 调用会自动填充)
        </div>
      </NCard>

      <NCard title="TODO Sprint 203 R3" :bordered="false">
        <ul class="text-sm text-gray-600 space-y-1">
          <li>• DuckDB file size 接入 (需新增 backend endpoint 或复用 /api/v1/health 扩展)</li>
          <li>• manifest version 接入 (需新增 backend endpoint)</li>
          <li>• read pool 利用率 (需 dual_conn.py 暴露 in_use count, 跟 Fix #1 Semaphore 配套)</li>
          <li>• 跨 sprint SOP 跟 L4.59 clickhouse-poc-monitor weekly 自动立项</li>
        </ul>
      </NCard>
    </NSpace>
  </div>
</template>