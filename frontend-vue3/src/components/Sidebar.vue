<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const menuOptions = [
  { label: '人群看板', key: '/audience' },
  { label: '老客分析', key: '/customer-health' },
  { label: '品类看板', key: '/category' },
  { label: '市场对焦', key: '/market-focus' },
  { label: '派样看板', key: '/sampling' },
  { label: '一键拆解', key: '/breakdown' },
  { label: '流失分析', key: '/churn' },
  { label: '地域分析', key: '/geo' },
]

const activeKey = computed(() => route.path)
</script>

<template>
  <aside class="sidebar-wrapper">
    <!-- Logo -->
    <div class="sidebar-logo">
      <div class="flex items-center gap-3">
        <div class="sidebar-logo-icon">芙</div>
        <div>
          <h1 class="sidebar-logo-title">芙清 CRM</h1>
          <p class="sidebar-logo-subtitle">数据分析平台</p>
        </div>
      </div>
    </div>

    <!-- Nav -->
    <nav class="sidebar-nav">
      <router-link
        v-for="item in menuOptions"
        :key="item.key"
        :to="item.key"
        :class="[
          'sidebar-nav-item',
          activeKey === item.key ? 'sidebar-nav-item--active' : 'sidebar-nav-item--inactive',
        ]"
      >
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- Footer -->
    <div class="sidebar-footer">
      <p>© 2026 芙清数据团队</p>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-wrapper {
  width: 256px;
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #0f172a;
  color: #cbd5e1;
  z-index: 20;
}
.sidebar-logo {
  padding: 24px 24px;
  border-bottom: 1px solid #1e293b;
}
.sidebar-logo-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background-color: #7c3aed;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 22px;
  font-weight: 700;
}
.sidebar-logo-title {
  font-size: 18px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: -0.01em;
  line-height: 1.4;
}
.sidebar-logo-subtitle {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
  line-height: 1.4;
}
.sidebar-nav {
  flex: 1;
  padding: 20px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sidebar-nav-item {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 18px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  transition: background-color 0.15s, color 0.15s;
  text-decoration: none;
}
.sidebar-nav-item--active {
  background-color: rgba(124, 58, 237, 0.12);
  color: #a78bfa;
}
.sidebar-nav-item--inactive {
  color: #94a3b8;
}
.sidebar-nav-item--inactive:hover {
  background-color: #1e293b;
  color: #e2e8f0;
}
.sidebar-footer {
  padding: 14px 24px;
  border-top: 1px solid #1e293b;
}
.sidebar-footer p {
  font-size: 12px;
  color: #64748b;
}
</style>
