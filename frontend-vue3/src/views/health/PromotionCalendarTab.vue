<script setup lang="ts">
import { computed, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NGrid, NGi, NDataTable, NButton } from 'naive-ui'
import { exportToCsv } from '@/utils/export'
import type { DataTableColumns } from 'naive-ui'
import { useFilterStore } from '@/stores/filterStore'
import { fetchPromotionCalendar } from '@/api/health'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'

const filterStore = useFilterStore()
import { LOW_PRICE_CHANNELS } from '@/constants/channels'

const queryParams = computed(() => ({
  year: parseInt(filterStore.dateRange[1].slice(0, 4), 10),
  exclude_channels: filterStore.excludeLowPrice ? LOW_PRICE_CHANNELS : undefined,
}))

const { data, isLoading, error, refetch } = useQuery({
  queryKey: ['promotion-calendar', queryParams],
  queryFn: () => {
    const p = toValue(queryParams)
    return fetchPromotionCalendar({
      year: p.year,
      exclude_channels: p.exclude_channels,
    })
  },
  staleTime: 60_000,
})

const promoColumns: DataTableColumns<any> = [
  { title: '活动', key: 'promotion.name' },
  { title: '老客人数', key: 'promo_old_customer_count', align: 'right' },
  { title: '老客GSV', key: 'promo_old_customer_gsv', align: 'right',
    render: (row) => `¥${Math.round(row.promo_old_customer_gsv).toLocaleString()}`,
  },
  { title: '老客AUS', key: 'promo_old_customer_aus', align: 'right',
    render: (row) => `¥${row.promo_old_customer_aus}`,
  },
  { title: '日常AUS', key: 'daily_old_customer_aus', align: 'right',
    render: (row) => `¥${row.daily_old_customer_aus}`,
  },
  { title: 'GSV提升', key: 'gsv_lift', align: 'right',
    render: (row) => row.gsv_lift != null ? `${(row.gsv_lift * 100).toFixed(1)}%` : '—',
  },
]

function     exportPromotions() {
  if (!data.value?.promotions) return
  const rows = data.value.promotions.map((r: any) => [
    r.promotion.name,
    r.promo_old_customer_count,
    `¥${Math.round(r.promo_old_customer_gsv)}`,
    `¥${r.promo_old_customer_aus}`,
    `¥${r.daily_old_customer_aus}`,
    r.gsv_lift != null ? `${(r.gsv_lift * 100).toFixed(1)}%` : '—',
  ])
  exportToCsv(
    `大促日历_${data.value?.analysis_year || new Date().getFullYear()}`,
    ['活动', '老客人数', '老客GSV', '老客AUS', '日常AUS', 'GSV提升'],
    rows,
  )
}

const dependencyColor = computed(() => {
  const level = data.value?.dependency_level
  if (level === 'high') return '#f5222d'
  if (level === 'medium') return '#faad14'
  return '#52c41a'
})
</script>

<template>
  <div class="promotion-calendar-tab">
    <LoadingState v-if="isLoading" />
    <ErrorState v-else-if="error" :message="error.message" @retry="refetch" />

    <template v-else-if="data">
      <!-- 年度汇总 -->
      <NGrid :cols="3" :x-gap="16" class="mb-4">
        <NGi>
          <div class="bi-card bi-card-hover px-4 py-3 text-center">
            <p class="text-xs text-slate-500">大促GSV占比</p>
            <p class="text-2xl font-bold">{{ ((data.annual_promo_gsv_ratio || 0) * 100).toFixed(1) }}%</p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-4 py-3 text-center">
            <p class="text-xs text-slate-500">大促依赖度</p>
            <p class="text-2xl font-bold" :style="{ color: dependencyColor }">
              {{ ((data.promo_dependency_score || 0) * 100).toFixed(1) }}%
            </p>
          </div>
        </NGi>
        <NGi>
          <div class="bi-card bi-card-hover px-4 py-3 text-center">
            <p class="text-xs text-slate-500">依赖评级</p>
            <p class="text-2xl font-bold" :style="{ color: dependencyColor }">
              {{ data.dependency_level === 'high' ? '重度' : data.dependency_level === 'medium' ? '中度' : '健康' }}
            </p>
          </div>
        </NGi>
      </NGrid>

      <!-- 活动对比表 -->
      <div class="bi-card p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-slate-700">大促 vs 日常对比</h3>
          <NButton size="tiny" @click="exportPromotions">导出CSV</NButton>
        </div>
        <NDataTable
          :columns="promoColumns"
          :data="data.promotions"
          :pagination="false"
          size="small"
          striped
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.promotion-calendar-tab {
  padding-top: 8px;
}
</style>
