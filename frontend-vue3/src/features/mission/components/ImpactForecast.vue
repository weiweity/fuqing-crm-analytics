<script setup lang="ts">
import type { Mission } from '@/features/mission/api'

defineProps<{ mission: Mission }>()

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>

<template>
  <aside class="glass-panel impact-panel">
    <div class="panel-meta">
      <span>EXPECTED IMPACT</span>
      <span>90 / 10 TEST</span>
    </div>

    <div class="impact-hero">
      <span>本次实验预估增量毛利</span>
      <strong>{{ formatMoney(mission.economics.expected_incremental_margin) }}</strong>
      <small>合成测算，不代表已实现收益</small>
    </div>

    <dl class="impact-grid">
      <div>
        <dt>可激活人群</dt>
        <dd>{{ mission.target_audience.eligible_customers }}</dd>
      </div>
      <div>
        <dt>预估增量客户</dt>
        <dd>+{{ mission.economics.expected_incremental_customers }}</dd>
      </div>
      <div>
        <dt>假设提升</dt>
        <dd>+{{ formatPercent(mission.economics.assumed_conversion_uplift) }}</dd>
      </div>
    </dl>

    <div class="experiment-line">
      <span :style="{ width: `${mission.economics.experiment_share * 100}%` }">实验组 {{ formatPercent(mission.economics.experiment_share) }}</span>
      <span :style="{ width: `${mission.economics.holdout_share * 100}%` }" aria-label="对照组" />
    </div>
    <p>{{ mission.economics.assumption_note }}</p>
  </aside>
</template>

<style scoped>
.impact-panel { display: flex; min-height: 100%; flex-direction: column; padding: var(--sm-dimension-px-24); }
.panel-meta { display: flex; justify-content: space-between; gap: var(--sm-dimension-px-12); color: var(--sm-muted); font: 600 var(--sm-dimension-px-9)/1.2 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-12); }
.impact-hero { display: grid; gap: var(--sm-dimension-px-10); margin: auto 0; padding: var(--sm-dimension-px-42) 0 var(--sm-dimension-px-36); }
.impact-hero span { color: var(--sm-copy); font-size: var(--sm-dimension-px-12); }
.impact-hero strong { color: var(--sm-ink); background: var(--sm-gradient-metric); background-clip: text; -webkit-background-clip: text; font-family: var(--sm-font-display); font-size: clamp(var(--sm-dimension-px-40), var(--sm-dimension-vw-4), var(--sm-dimension-px-62)); font-weight: 560; letter-spacing: var(--sm-dimension-em-minus-0-055); line-height: 1; text-shadow: var(--sm-shadow-metric); -webkit-text-fill-color: transparent; }
.impact-hero small { color: var(--sm-faint); font-size: var(--sm-dimension-px-10); }
.impact-grid { display: grid; grid-template-columns: repeat(3, 1fr); margin: 0; border-top: var(--sm-dimension-px-1) solid var(--sm-line); }
.impact-grid div { display: grid; gap: var(--sm-dimension-px-8); padding: var(--sm-dimension-px-18) var(--sm-dimension-px-10) var(--sm-dimension-px-16) 0; }
.impact-grid dt { color: var(--sm-muted); font-size: var(--sm-dimension-px-10); }
.impact-grid dd { margin: 0; color: var(--sm-ink); font-family: var(--sm-font-display); font-size: var(--sm-dimension-px-20); font-weight: 600; }
.experiment-line { display: flex; height: var(--sm-dimension-px-26); overflow: hidden; border: var(--sm-dimension-px-1) solid var(--sm-line-strong); border-radius: var(--sm-radius-pill); background: var(--sm-white-faint); }
.experiment-line span:first-child { display: flex; align-items: center; padding-left: var(--sm-dimension-px-9); color: var(--sm-on-accent); background: var(--sm-signal); font: 650 var(--sm-dimension-px-8)/1 var(--sm-font-display); white-space: nowrap; }
.experiment-line span:last-child { background: var(--sm-purple); }
.impact-panel > p { margin: var(--sm-dimension-px-9) 0 0; color: var(--sm-faint); font-size: var(--sm-dimension-px-9); line-height: 1.5; }

@media (max-width: 560px) {
  .impact-grid { grid-template-columns: 1fr; }
  .impact-grid div + div { border-top: var(--sm-dimension-px-1) solid var(--sm-line); }
}
</style>
