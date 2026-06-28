<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NEmpty, NSpin } from 'naive-ui'
import { useQuery } from '@tanstack/vue-query'
import { fetchCohortRetention } from '@/api/sampling'
import type { SamplingCohortRetentionRow } from '@/api/sampling'

interface Props {
  startMonth: string
  endMonth: string
  channel?: string
}

const props = withDefaults(defineProps<Props>(), {
  channel: '全店',
})

const monthOffsets = Array.from({ length: 13 }, (_, idx) => idx)

const queryParams = computed(() => ({
  start_month: props.startMonth,
  end_month: props.endMonth,
  channel: props.channel,
}))

const { data, isLoading } = useQuery({
  queryKey: computed(() => ['sampling-cohort-retention', queryParams.value]),
  queryFn: () => fetchCohortRetention(queryParams.value),
  enabled: computed(() => !!props.startMonth && !!props.endMonth),
  placeholderData: previousData => previousData,
})

function retentionFor(row: SamplingCohortRetentionRow, monthOffset: number): number | undefined {
  return row.retention?.[monthOffset]
}

function formatRetention(row: SamplingCohortRetentionRow, monthOffset: number): string {
  const value = retentionFor(row, monthOffset)
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function cellStyle(row: SamplingCohortRetentionRow, monthOffset: number) {
  const value = retentionFor(row, monthOffset)
  if (value == null) return {}
  const intensity = Math.min(Math.max(value, 0), 1)
  return {
    backgroundColor: `rgba(14, 165, 233, ${0.08 + intensity * 0.58})`,
    color: intensity > 0.62 ? '#ffffff' : '#0f172a',
  }
}
</script>

<template>
  <n-card :bordered="false" segmented>
    <template #header>
      <span class="text-sm font-semibold text-slate-700">Cohort 留存矩阵</span>
    </template>

    <div class="mb-3 flex items-center gap-4 text-xs text-slate-500">
      <span>{{ props.startMonth }} ~ {{ props.endMonth }}</span>
      <span>{{ props.channel }}</span>
    </div>

    <div v-if="isLoading" class="flex justify-center py-10">
      <n-spin size="small" />
    </div>

    <n-empty v-else-if="!data?.rows?.length" description="暂无 cohort 留存数据" />

    <div v-else class="overflow-x-auto">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th class="cohort-th text-left">Cohort 月份</th>
            <th class="cohort-th text-right">Cohort 大小</th>
            <th
              v-for="monthOffset in monthOffsets"
              :key="monthOffset"
              class="cohort-th text-right"
            >
              M{{ monthOffset }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in data.rows" :key="row.cohort_month" class="hover:bg-slate-50">
            <td class="cohort-td font-medium text-slate-700">{{ row.cohort_month }}</td>
            <td class="cohort-td text-right text-slate-600">
              {{ row.cohort_size.toLocaleString() }}
            </td>
            <td
              v-for="monthOffset in monthOffsets"
              :key="monthOffset"
              class="cohort-td text-right font-medium"
              :style="cellStyle(row, monthOffset)"
            >
              {{ formatRetention(row, monthOffset) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </n-card>
</template>

<style scoped>
.cohort-th {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  white-space: nowrap;
}

.cohort-td {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  white-space: nowrap;
}
</style>
