<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NCard, NButton, NIcon, NSpin, NList, NListItem, NTag, NInput, NEmpty } from 'naive-ui'
import { ArrowBackOutline, SearchOutline, CheckmarkCircleOutline, AlertCircleOutline } from '@vicons/ionicons5'
import { productApi } from '@/api/scriptLibrary'
import type { ProductDetail } from '@/api/scriptLibrary'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const product = ref<ProductDetail | null>(null)
const searchKeyword = ref('')

const productName = decodeURIComponent(route.params.name as string)

// 过滤后的话术列表
const filteredQA = computed(() => {
  if (!product.value) return []
  if (!searchKeyword.value) return product.value.qa_list

  const keyword = searchKeyword.value.toLowerCase()
  return product.value.qa_list.filter(qa =>
    qa.question.toLowerCase().includes(keyword) ||
    qa.answer.toLowerCase().includes(keyword)
  )
})

async function loadProduct() {
  loading.value = true
  try {
    product.value = await productApi.get(productName)
  } catch (error) {
    console.error('加载产品数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(loadProduct)
</script>

<template>
  <div class="product-script-page">
    <div class="page-header">
      <n-button quaternary @click="router.back()">
        <template #icon>
          <n-icon><arrow-back-outline /></n-icon>
        </template>
        返回
      </n-button>
      <h1>{{ productName }}</h1>
      <span class="qa-count" v-if="product">{{ product.qa_list.length }} 条话术</span>
    </div>

    <n-spin :show="loading">
      <div v-if="product" class="content">
        <!-- 搜索栏 -->
        <div class="search-bar">
          <n-input
            v-model:value="searchKeyword"
            placeholder="搜索问题或答案..."
            clearable
          >
            <template #prefix>
              <n-icon><search-outline /></n-icon>
            </template>
          </n-input>
        </div>

        <!-- 话术列表 -->
        <n-card v-if="filteredQA.length > 0">
          <n-list>
            <n-list-item v-for="(qa, index) in filteredQA" :key="index">
              <div class="qa-item">
                <div class="question-row">
                  <div class="question">
                    <strong>Q:</strong> {{ qa.question }}
                  </div>
                  <n-tag
                    :type="qa.has_answer ? 'success' : 'warning'"
                    size="small"
                  >
                    <template #icon>
                      <n-icon v-if="qa.has_answer"><checkmark-circle-outline /></n-icon>
                      <n-icon v-else><alert-circle-outline /></n-icon>
                    </template>
                    {{ qa.has_answer ? '已有话术' : '待补充' }}
                  </n-tag>
                </div>
                <div class="answer" v-if="qa.answer">
                  <strong>A:</strong> {{ qa.answer }}
                </div>
                <div class="answer empty" v-else>
                  <em>暂无话术，请补充</em>
                </div>
              </div>
            </n-list-item>
          </n-list>
        </n-card>

        <n-empty v-else description="没有找到匹配的话术" />
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.product-script-page {
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.qa-count {
  color: #666;
  font-size: 14px;
}

.search-bar {
  margin-bottom: 16px;
}

.qa-item {
  padding: 8px 0;
}

.question-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 8px;
}

.question {
  flex: 1;
  color: #333;
}

.answer {
  color: #666;
  padding-left: 24px;
  line-height: 1.6;
}

.answer.empty {
  color: #999;
  font-style: italic;
}
</style>
