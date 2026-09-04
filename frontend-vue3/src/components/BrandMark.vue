<script setup lang="ts">
withDefaults(defineProps<{
  compact?: boolean
  inverse?: boolean
}>(), {
  compact: false,
  inverse: true,
})
</script>

<template>
  <div class="brand-mark" :class="{ compact, inverse }" aria-label="SHINE MAGE 伸美 AI 增长董事会">
    <span class="brand-symbol" aria-hidden="true">
      <svg viewBox="0 0 56 56" role="img">
        <path d="M17.2 35.4 27.8 12l11.4 23.4Z" />
        <path d="M11 37.5c9.7-4.4 24.5-4.4 34 0-7 7.7-27 7.7-34 0Z" />
        <path d="m37.8 10.7 1.5 3.4 3.6 1.4-3.6 1.5-1.5 3.5-1.5-3.5-3.6-1.5 3.6-1.4Z" class="spark" />
        <path d="m45.1 23.2.9 2 2.1.9-2.1.8-.9 2.1-.8-2.1-2.2-.8 2.2-.9Z" class="spark-small" />
      </svg>
    </span>
    <span class="brand-copy">
      <strong>SHINE MAGE</strong>
      <small v-if="!compact">伸美 AI 增长董事会</small>
    </span>
  </div>
</template>

<style scoped>
.brand-mark {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  color: #22172a;
}

.brand-mark.inverse { color: var(--sm-ink, #fefcff); }
.brand-symbol { display: grid; width: 40px; height: 40px; place-items: center; }
.brand-symbol svg { width: 100%; height: 100%; overflow: visible; }
.brand-symbol path { fill: currentColor; }
.brand-symbol .spark { fill: var(--sm-signal, #f2ffdc); }
.brand-symbol .spark-small { fill: var(--sm-lilac, #d3c3e8); }
.brand-copy { display: grid; gap: 2px; min-width: 0; }
.brand-copy strong {
  font-family: var(--sm-font-display, Outfit, sans-serif);
  font-size: 15px;
  font-weight: 650;
  letter-spacing: .13em;
  line-height: 1;
}
.brand-copy small { color: var(--sm-muted, #a99cb3); font-size: 11px; line-height: 1.2; white-space: nowrap; }
.compact { gap: 8px; }
.compact .brand-symbol { width: 31px; height: 31px; }
.compact .brand-copy strong { font-size: 12px; }

@media (max-width: 720px) {
  .brand-copy small { display: none; }
}
</style>
