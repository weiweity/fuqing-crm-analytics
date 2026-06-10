<script setup lang="ts">
/**
 * Ratio Convention Banner (Sprint 13)
 *
 * 顶栏彩色横条,告知用户 ratio 口径已统一 (pass-through 契约).
 * 给分析师/PM 一个视觉确认:"pp/% 数字是后端已 *100,前端不再 *100".
 *
 * 三态:
 *   - hidden: 3 天后自动消失 (localStorage: ratio_banner_dismissed_until)
 *   - visible: 默认显示
 *   - dismissed: 用户点击关闭,3 天内不再出现
 *
 * 数据: 无 API 调用,纯静态文案 + localStorage TTL
 */
import { ref, onMounted } from 'vue'
import { NIcon, NButton } from 'naive-ui'
import { CheckmarkCircle, CloseCircleOutline } from '@vicons/ionicons5'

const STORAGE_KEY = 'fq_crm_ratio_banner_dismissed_until'
const TTL_DAYS = 3
const TTL_MS = TTL_DAYS * 24 * 60 * 60 * 1000

const visible = ref(false)

function isDismissed(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return false
    const until = Number(raw)
    if (!Number.isFinite(until)) return false
    return Date.now() < until
  } catch {
    // localStorage 不可用 (SSR/隐私模式) → 当作未关闭,显示 banner
    return false
  }
}

function dismiss() {
  visible.value = false
  try {
    const until = Date.now() + TTL_MS
    localStorage.setItem(STORAGE_KEY, String(until))
  } catch {
    // localStorage 写入失败 → 仅本次隐藏,刷新后还会显示
  }
}

onMounted(() => {
  visible.value = !isDismissed()
})
</script>

<template>
  <div
    v-if="visible"
    class="ratio-convention-banner"
    role="status"
    aria-live="polite"
  >
    <div class="flex items-center gap-2 min-w-0 flex-1">
      <n-icon :component="CheckmarkCircle" :size="14" class="flex-shrink-0" />
      <span class="text-[12px] font-medium text-slate-700 flex-shrink-0">
        本周起 pp 口径统一
      </span>
      <span class="text-[11px] text-slate-400 flex-shrink-0">·</span>
      <span class="text-[12px] text-slate-600">
        以 <span class="font-mono font-semibold text-slate-900">5.28pp</span> 为例
        = 同比 <span class="text-emerald-700 font-medium">+5.28 百分点</span>
      </span>
      <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono flex-shrink-0">
        Sprint 13
      </span>
    </div>
    <n-button
      text
      size="tiny"
      @click="dismiss"
      class="flex-shrink-0"
      aria-label="关闭 banner"
    >
      <template #icon>
        <n-icon :component="CloseCircleOutline" />
      </template>
      关闭
    </n-button>
  </div>
</template>

<style scoped>
.ratio-convention-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  background-color: rgba(59, 130, 246, 0.06); /* blue-500 6% */
  border: 1px solid rgba(59, 130, 246, 0.18);
  min-height: 32px;
}
</style>
