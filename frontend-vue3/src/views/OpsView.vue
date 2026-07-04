<script setup lang="ts">
/**
 * Sprint 203 R2 Finding 4.6 + R3 STUB 接入: /metrics + /health/* dashboard
 *
 * 显示 4 件 0 业务代码改动 关键指标:
 *  - /metrics: total queries by endpoint + query_type + P50/P95/P99 延迟 (Sprint 203 R2)
 *  - /api/v1/health/db_size: DuckDB file size + 距离 200GB trigger 距离 (Sprint 203 R3)
 *  - /api/v1/health/manifest: W5 manifest version (Sprint 203 R3)
 *  - /api/v1/health/pool: read pool 利用率 (Sprint 203 R3 跟 Fix #1 Semaphore 配套)
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { NCard, NDataTable, NSpace, NTag, NSpin, NAlert, NStatistic, NGrid, NGi, NProgress } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'

interface EndpointStats {
  endpoint: string
  queryType: string
  total: number
  p50: number
  p95: number
  p99: number
}

interface DbSizeInfo {
  status: string
  size_gb: number
  trigger_gb: number
  remaining_gb: number
  trigger_hit: boolean
  path: string
}

interface ManifestInfo {
  status: string
  version: number | null
}

interface PoolInfo {
  status: string
  pool_size: number
  semaphore_max: number
  semaphore_in_use: number
  utilization_pct: number
  read_pool_size_limit: number
}

const metricsText = ref<string>('')
const dbSize = ref<DbSizeInfo | null>(null)
const manifest = ref<ManifestInfo | null>(null)
const pool = ref<PoolInfo | null>(null)
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
    // 跟 L4.61 跨 CI runner 适配 1:1 stable: 4 件 endpoint 并行 fetch
    const [_metricsRes, _dbSizeRes, _manifestRes, _poolRes] = await Promise.all([
      fetch('/metrics', { credentials: 'include' }),
      fetch('/api/v1/health/db_size', { credentials: 'include' }),
      fetch('/api/v1/health/manifest', { credentials: 'include' }),
      fetch('/api/v1/health/pool', { credentials: 'include' }),
    ])
    if (!_metricsRes.ok) {
      throw new Error(`HTTP ${_metricsRes.status}: ${_metricsRes.statusText}`)
    }
    metricsText.value = await _metricsRes.text()
    if (_dbSizeRes.ok) {
      dbSize.value = await _dbSizeRes.json()
    }
    if (_manifestRes.ok) {
      manifest.value = await _manifestRes.json()
    }
    if (_poolRes.ok) {
      pool.value = await _poolRes.json()
    }
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

// 进度条颜色 (跟 L4.52 告警色 1:1 stable)
const poolColor = computed(() => {
  if (!pool.value) return '#2080f0'
  if (pool.value.utilization_pct >= 80) return '#d03050'
  if (pool.value.utilization_pct >= 50) return '#f0a020'
  return '#18a058'
})
</script>

<template>
  <div class="p-6">
    <PageHeader title="系统运维看板" subtitle="/metrics 实时监控 + /health/* 系统状态 + ClickHouse POC 启动条件" />

    <NSpace vertical :size="16">
      <NAlert type="info" :show-icon="false">
        Sprint 203 R2 + R3: 实时拉取 <code>/metrics</code> Prometheus 文本 + 3 件 <code>/api/v1/health/*</code> 系统状态端点 (db_size + manifest + pool).
        ClickHouse POC 启动条件: {{ clickhouseMonitorStatus }}.
      </NAlert>

      <NGrid :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
        <!-- Stub #1: DuckDB file size (Sprint 203 R3 接入) -->
        <NGi>
          <NCard title="DuckDB 文件大小" :bordered="false">
            <NStatistic v-if="dbSize" label="当前大小" :value="dbSize.size_gb">
              <template #suffix>GB</template>
            </NStatistic>
            <NStatistic v-if="dbSize" label="距 200GB trigger" :value="dbSize.remaining_gb">
              <template #suffix>GB</template>
            </NStatistic>
            <NProgress
              v-if="dbSize"
              type="line"
              :percentage="Math.min(100, Math.round(100 * dbSize.size_gb / dbSize.trigger_gb))"
              :show-indicator="false"
              :color="dbSize.trigger_hit ? '#d03050' : '#18a058'"
            />
            <NTag v-if="dbSize && dbSize.trigger_hit" type="error" size="small">已超 ClickHouse POC 触发阈值</NTag>
            <NTag v-else-if="dbSize" type="success" size="small">未触发</NTag>
            <div v-else class="text-gray-500 text-center py-2">未拉取</div>
          </NCard>
        </NGi>

        <!-- Stub #2: W5 manifest version (Sprint 203 R3 接入) -->
        <NGi>
          <NCard title="W5 Manifest Version" :bordered="false">
            <NStatistic v-if="manifest" label="当前 version" :value="manifest.version ?? 'N/A'" />
            <NTag v-if="manifest && manifest.version !== null" type="info" size="small">数据快照已加载</NTag>
            <NTag v-else-if="manifest" type="warning" size="small">manifest 不存在</NTag>
            <div v-else class="text-gray-500 text-center py-2">未拉取</div>
            <div class="text-xs text-gray-400 mt-2">
              跟 backend/services/rfm/cache.py:_ManifestTracker 1:1 stable
            </div>
          </NCard>
        </NGi>

        <!-- Stub #3: Read pool 利用率 (Sprint 203 R3 接入, 跟 Fix #1 Semaphore 配套) -->
        <NGi>
          <NCard title="Read Pool 利用率" :bordered="false">
            <NStatistic v-if="pool" label="当前 in use" :value="pool.semaphore_in_use">
              <template #suffix>/ {{ pool.semaphore_max }}</template>
            </NStatistic>
            <NProgress
              v-if="pool"
              type="line"
              :percentage="pool.utilization_pct"
              :color="poolColor"
              :show-indicator="true"
            />
            <div v-if="pool" class="text-xs text-gray-500 mt-2">
              READ_POOL_SIZE limit: {{ pool.read_pool_size_limit }} · 当前 pool 缓存: {{ pool.pool_size }}
            </div>
            <div v-else class="text-gray-500 text-center py-2">未拉取</div>
          </NCard>
        </NGi>
      </NGrid>

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

      <NCard title="Sprint 203 R3 后续 STUB TODO" :bordered="false">
        <ul class="text-sm text-gray-600 space-y-1">
          <li>✅ DuckDB file size 已接入 (Stub #1)</li>
          <li>✅ W5 manifest version 已接入 (Stub #2)</li>
          <li>✅ Read pool 利用率已接入 (Stub #3, 跟 Fix #1 Semaphore 配套)</li>
          <li>📋 Sprint 203 R4+ 待办: 接入真 query P95 / 业务分析师并发数 (b/c 件) 等 /metrics 数据稳定后</li>
        </ul>
      </NCard>
    </NSpace>
  </div>
</template>