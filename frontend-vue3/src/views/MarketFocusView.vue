<script setup lang="ts">
import { ref, watch } from 'vue'
import { NTabs, NTabPane, NSelect } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import ProductCustomerTab from './market-focus/ProductCustomerTab.vue'
import StoreAssetsTab from './market-focus/StoreAssetsTab.vue'
import ProductAssetsTab from './market-focus/ProductAssetsTab.vue'
import OtherProductAssetsTab from './market-focus/OtherProductAssetsTab.vue'

const activeTab = ref('product-customer')

// 每个Tab独立的周数控制
const productCustomerWeeks = ref(4)
const storeAssetsWeeks = ref(4)
const productAssetsWeeks = ref(4)
const otherProductAssetsWeeks = ref(4)

const weekOptions = [
  { label: '近4周', value: 4 },
  { label: '近8周', value: 8 },
  { label: '近12周', value: 12 },
]

// 当前Tab的周数（双向映射）
const currentWeeks = ref(4)
watch(activeTab, (tab) => {
  if (tab === 'product-customer') currentWeeks.value = productCustomerWeeks.value
  else if (tab === 'store-assets') currentWeeks.value = storeAssetsWeeks.value
  else if (tab === 'product-assets') currentWeeks.value = productAssetsWeeks.value
  else currentWeeks.value = otherProductAssetsWeeks.value
}, { immediate: true })

function onWeeksChange(val: number) {
  if (activeTab.value === 'product-customer') productCustomerWeeks.value = val
  else if (activeTab.value === 'store-assets') storeAssetsWeeks.value = val
  else if (activeTab.value === 'product-assets') productAssetsWeeks.value = val
  else otherProductAssetsWeeks.value = val
  currentWeeks.value = val
}

// 渠道筛选（仅影响核心单品新老客Tab）
// 注意：仅覆盖Tab1常用渠道，完整渠道列表见 backend/semantic/channels.py CHANNEL_ORDER
const channelOptions = [
  { label: '全店', value: '全店' },
  { label: 'affiliate', value: 'affiliate' },
  { label: '直播', value: '直播' },
  { label: '货架', value: '货架' },
]
const currentChannel = ref('全店')

// 懒加载：记录哪些Tab已加载过（用数组替代 Set，避免响应式复杂性）
const loadedTabs = ref<string[]>(['product-customer'])
watch(activeTab, (tab) => {
  if (!loadedTabs.value.includes(tab)) {
    loadedTabs.value = [...loadedTabs.value, tab]
  }
}, { immediate: false })

const tabList = [
  { name: 'product-customer', label: '核心单品新老客' },
  { name: 'store-assets', label: '全店资产' },
  { name: 'product-assets', label: '单品资产' },
  { name: 'other-product-assets', label: '单品资产-其他' },
]
</script>

<template>
  <div class="market-focus-view">
    <div class="flex items-center justify-between mb-4">
      <PageHeader title="市场对焦" subtitle="核心单品新老客占比 / 全店资产 / 单品资产 / 单品资产-其他 追踪" />
      <div class="flex items-center gap-3">
        <NSelect
          v-if="activeTab === 'product-customer'"
          v-model:value="currentChannel"
          :options="channelOptions"
          size="tiny"
          style="width: 100px"
        />
        <NSelect
          v-model:value="currentWeeks"
          :options="weekOptions"
          size="tiny"
          style="width: 100px"
          @update:value="onWeeksChange"
        />
      </div>
    </div>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane
        v-for="tab in tabList"
        :key="tab.name"
        :name="tab.name"
        :tab="tab.label"
      >
        <ProductCustomerTab
          v-if="tab.name === 'product-customer'"
          :weeks="productCustomerWeeks"
          :channel="currentChannel"
        />
        <StoreAssetsTab
          v-else-if="tab.name === 'store-assets' && loadedTabs.includes('store-assets')"
          :weeks="storeAssetsWeeks"
        />
        <ProductAssetsTab
          v-else-if="tab.name === 'product-assets' && loadedTabs.includes('product-assets')"
          :weeks="productAssetsWeeks"
        />
        <OtherProductAssetsTab
          v-else-if="tab.name === 'other-product-assets' && loadedTabs.includes('other-product-assets')"
          :weeks="otherProductAssetsWeeks"
        />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.market-focus-view {
  padding: 20px;
}
</style>
