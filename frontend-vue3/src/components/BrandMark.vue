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
  <div class="brand-mark" :class="{ compact, inverse }" aria-label="SHINE MAGE">
    <img class="brand-image" :src="shineMageLogo" alt="SHINE MAGE" width="249" height="45" />
  </div>
</template>

<style scoped>
.brand-mark {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: var(--sm-dimension-px-12);
  padding: var(--sm-dimension-px-4);
  color: var(--sm-on-accent);
}

.brand-mark.inverse { color: var(--sm-ink); }
.brand-image { display: block; width: var(--sm-dimension-px-177); height: auto; object-fit: contain; }
.inverse .brand-image { filter: var(--sm-filter-brand-inverse); }
.compact .brand-image { width: var(--sm-dimension-px-140); }
</style>
