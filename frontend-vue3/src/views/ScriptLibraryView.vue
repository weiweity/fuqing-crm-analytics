<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NTabs, NTabPane, NList, NListItem, NTag, NButton, NIcon, NSpace, NEmpty, NSpin } from 'naive-ui'
import { SearchOutline, StarOutline } from '@vicons/ionicons5'
import { useRouter } from 'vue-router'
import { productApi, celebrityApi } from '@/api/scriptLibrary'
import type { ProductScript, Celebrity } from '@/api/scriptLibrary'

const router = useRouter()
const loading = ref(false)
const activeTab = ref('products')

// 产品话术数据
const products = ref<ProductScript[]>([])

// 明星专项数据
const celebrities = ref<Celebrity[]>([])

// 加载数据
async function loadData() {
  loading.value = true
  try {
    const [productsRes, celebritiesRes] = await Promise.all([
      productApi.list(),
      celebrityApi.list()
    ])
    products.value = productsRes
    celebrities.value = celebritiesRes
  } catch (error) {
    console.error('加载话术库失败:', error)
  } finally {
    loading.value = false
  }
}

// 跳转到产品详情
function goToProduct(name: string) {
  router.push(`/scripts/product/${encodeURIComponent(name)}`)
}

// 跳转到明星详情
function goToCelebrity(name: string) {
  router.push(`/scripts/celebrity/${encodeURIComponent(name)}`)
}

// 获取状态标签颜色
function getStatusColor(status: string) {
  return status === '已上线' ? 'success' : 'warning'
}

onMounted(loadData)
</script>

<template>
  <div class="script-library-page">
    <div class="page-header">
      <h1>话术库</h1>
      <p class="subtitle">产品话术管理与明星专项</p>
    </div>

    <n-spin :show="loading">
      <n-tabs v-model:value="activeTab" type="line" animated>
        <!-- 产品话术 Tab -->
        <n-tab-pane name="products" tab="产品话术">
          <div class="tab-content">
            <div class="toolbar">
              <n-button type="primary" @click="router.push('/scripts/import')">
                导入话术
              </n-button>
            </div>

            <n-list v-if="products.length > 0" hoverable clickable>
              <n-list-item
                v-for="product in products"
                :key="product.name"
                @click="goToProduct(product.name)"
              >
                <div class="product-item">
                  <div class="product-info">
                    <h3>{{ product.name }}</h3>
                    <span class="qa-count">{{ product.qa_count }} 条话术</span>
                  </div>
                  <n-icon :size="20" color="#999">
                    <search-outline />
                  </n-icon>
                </div>
              </n-list-item>
            </n-list>

            <n-empty v-else description="暂无产品话术，请先导入" />
          </div>
        </n-tab-pane>

        <!-- 明星专项 Tab -->
        <n-tab-pane name="celebrities" tab="明星专项">
          <div class="tab-content">
            <div class="celebrity-grid">
              <div
                v-for="celeb in celebrities"
                :key="celeb.name"
                class="celebrity-card"
                @click="goToCelebrity(celeb.name)"
              >
                <div class="celebrity-avatar">
                  <n-icon :size="40" color="#7c3aed">
                    <star-outline />
                  </n-icon>
                </div>
                <div class="celebrity-info">
                  <h3>{{ celeb.name }}</h3>
                  <p>{{ celeb.title }}</p>
                  <n-tag :type="getStatusColor(celeb.status)" size="small">
                    {{ celeb.status }}
                  </n-tag>
                </div>
              </div>
            </div>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-spin>
  </div>
</template>

<style scoped>
.script-library-page {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 4px 0;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.tab-content {
  min-height: 400px;
}

.toolbar {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-end;
}

.product-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}

.product-info h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 500;
}

.qa-count {
  color: #666;
  font-size: 13px;
}

.celebrity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.celebrity-card {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.celebrity-card:hover {
  border-color: #7c3aed;
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.1);
}

.celebrity-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #f3f0ff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.celebrity-info h3 {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 600;
}

.celebrity-info p {
  color: #666;
  font-size: 13px;
  margin: 0 0 12px 0;
}
</style>
