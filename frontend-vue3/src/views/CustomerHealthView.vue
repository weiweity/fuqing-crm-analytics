<script setup lang="ts">
import { ref, watch } from 'vue'
import { NTabs, NTabPane, NButton } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import HealthOverviewTab from './health/HealthOverviewTab.vue'
import RIntervalTab from './health/RIntervalTab.vue'
import RepurchaseCycleTab from './health/RepurchaseCycleTab.vue'
import ValueTierTab from './health/ValueTierTab.vue'
import FIntervalTab from './health/FIntervalTab.vue'
import MIntervalTab from './health/MIntervalTab.vue'
import HealthConfigPanel from './health/HealthConfigPanel.vue'

const activeTab = ref('overview')
const showConfig = ref(false)

// 懒加载：记录哪些 Tab 已经加载过，首次切换时才创建组件
const loadedTabs = ref<Set<string>>(new Set(['overview']))

watch(activeTab, (tab) => {
  loadedTabs.value = new Set([...loadedTabs.value, tab])
}, { immediate: false })

const tabList: { name: string; label: string; disabled?: boolean }[] = [
  { name: 'overview', label: '现状概览' },
  { name: 'tiers', label: 'RFM分析' },
  { name: 'r-interval', label: 'R区间分析' },
  { name: 'f-interval', label: 'F区间分析' },
  { name: 'm-interval', label: 'M区间分析' },
  { name: 'repurchase', label: '复购周期' },
]
</script>

<template>
  <div class="customer-health-view">
    <div class="flex items-center justify-between mb-4">
      <PageHeader title="老客分析" subtitle="从数据报告到运营行动指引" />
      <NButton size="tiny" @click="showConfig = true">配置</NButton>
    </div>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane
        v-for="tab in tabList"
        :key="tab.name"
        :name="tab.name"
        :tab="tab.label"
        :disabled="tab.disabled"
      >
        <HealthOverviewTab v-if="tab.name === 'overview'" @navigate-tab="activeTab = $event" />
        <RIntervalTab v-else-if="tab.name === 'r-interval' && loadedTabs.has('r-interval')" />
        <RepurchaseCycleTab v-else-if="tab.name === 'repurchase' && loadedTabs.has('repurchase')" />
        <ValueTierTab v-else-if="tab.name === 'tiers' && loadedTabs.has('tiers')" />
        <FIntervalTab v-else-if="tab.name === 'f-interval' && loadedTabs.has('f-interval')" />
        <MIntervalTab v-else-if="tab.name === 'm-interval' && loadedTabs.has('m-interval')" />
      </n-tab-pane>
    </n-tabs>

    <HealthConfigPanel v-model:show="showConfig" />
  </div>
</template>

<style scoped>
.customer-health-view {
  padding: 20px;
}
.placeholder-tab {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}
</style>
