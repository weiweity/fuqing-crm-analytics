<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NCard, NTag, NButton, NIcon, NEmpty, NSpin, NList, NListItem } from 'naive-ui'
import { ArrowBackOutline, StarOutline, LockClosedOutline } from '@vicons/ionicons5'
import { celebrityApi } from '@/api/scriptLibrary'
import type { Celebrity } from '@/api/scriptLibrary'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const celebrity = ref<Celebrity | null>(null)

const celebrityName = decodeURIComponent(route.params.name as string)

async function loadCelebrity() {
  loading.value = true
  try {
    celebrity.value = await celebrityApi.get(celebrityName)
  } catch (error) {
    console.error('加载明星数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(loadCelebrity)
</script>

<template>
  <div class="celebrity-detail-page">
    <div class="page-header">
      <n-button quaternary @click="router.back()">
        <template #icon>
          <n-icon><arrow-back-outline /></n-icon>
        </template>
        返回
      </n-button>
    </div>

    <n-spin :show="loading">
      <div v-if="celebrity" class="content">
        <!-- 明星信息卡片 -->
        <n-card class="celebrity-card">
          <div class="celebrity-profile">
            <div class="avatar">
              <n-icon :size="48" color="#7c3aed">
                <star-outline />
              </n-icon>
            </div>
            <div class="info">
              <h1>{{ celebrity.name }}</h1>
              <p>{{ celebrity.title }}</p>
              <n-tag :type="celebrity.status === '已上线' ? 'success' : 'warning'">
                {{ celebrity.status }}
              </n-tag>
            </div>
          </div>
        </n-card>

        <!-- 话术内容 -->
        <n-card title="话术内容" class="scripts-card">
          <div v-if="celebrity.scripts.length > 0">
            <n-list>
              <n-list-item v-for="(script, index) in celebrity.scripts" :key="index">
                <div class="script-item">
                  <div class="question">
                    <strong>Q{{ index + 1 }}:</strong> {{ script.question }}
                  </div>
                  <div class="answer">
                    <strong>A:</strong> {{ script.answer }}
                  </div>
                </div>
              </n-list-item>
            </n-list>
          </div>

          <div v-else class="empty-state">
            <n-empty description="该明星话术待开发">
              <template #extra>
                <div class="coming-soon">
                  <n-icon :size="48" color="#ccc">
                    <lock-closed-outline />
                  </n-icon>
                  <p>话术正在开发中，敬请期待...</p>
                </div>
              </template>
            </n-empty>
          </div>
        </n-card>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.celebrity-detail-page {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.celebrity-card {
  margin-bottom: 24px;
}

.celebrity-profile {
  display: flex;
  align-items: center;
  gap: 24px;
}

.avatar {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: #f3f0ff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.info h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 600;
}

.info p {
  color: #666;
  margin: 0 0 12px 0;
}

.scripts-card {
  min-height: 300px;
}

.script-item {
  padding: 8px 0;
}

.question {
  margin-bottom: 8px;
  color: #333;
}

.answer {
  color: #666;
  padding-left: 24px;
}

.empty-state {
  padding: 60px 0;
  text-align: center;
}

.coming-soon {
  margin-top: 16px;
}

.coming-soon p {
  color: #999;
  margin-top: 12px;
}
</style>
