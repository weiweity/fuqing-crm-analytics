<script setup lang="ts">
import shineMageLogo from '@/assets/brand/shine-mage.png'

withDefaults(defineProps<{
  compact?: boolean
  inverse?: boolean
}>(), {
  compact: false,
  inverse: true,
})
</script>

<template>
  <div class="brand-mark" :class="{ compact, inverse }" aria-label="SHINE MAGE 伸美集团 CRM 增长分析平台">
    <img class="brand-image" :src="shineMageLogo" alt="SHINE MAGE" width="249" height="45" />
    <small v-if="!compact">伸美集团 · CRM 增长分析平台</small>
  </div>
</template>

<style scoped>
.brand-mark {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: var(--sm-dimension-px-12);
  padding: var(--sm-dimension-px-8);
  color: var(--sm-on-accent);
}

.brand-mark.inverse { color: var(--sm-ink); }
.brand-image { display: block; width: var(--sm-dimension-px-177); height: auto; object-fit: contain; }
.inverse .brand-image { filter: var(--sm-filter-brand-inverse); }
.brand-mark small { color: var(--sm-muted); font-size: var(--sm-dimension-px-11); line-height: 1.2; white-space: nowrap; }
.compact .brand-image { width: var(--sm-dimension-px-140); }

@media (max-width: 720px) {
  .brand-mark small { display: none; }
}
</style>
