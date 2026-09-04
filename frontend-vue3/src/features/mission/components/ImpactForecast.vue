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
      <span>VALUE HYPOTHESIS</span>
      <span>90 / 10 TEST</span>
    </div>

    <div class="impact-hero">
      <span>本次实验预估增量毛利</span>
      <strong>{{ formatMoney(mission.economics.expected_incremental_margin) }}</strong>
      <small>合成测算，不代表已实现收益</small>
    </div>

    <dl class="impact-grid">
      <div>
        <dt>可激活客户</dt>
        <dd>{{ mission.target_audience.eligible_customers }}</dd>
      </div>
      <div>
        <dt>预估增量客户</dt>
        <dd>+{{ mission.economics.expected_incremental_customers }}</dd>
      </div>
      <div>
        <dt>转化提升假设</dt>
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
.impact-panel { display: flex; min-height: 100%; flex-direction: column; padding: 24px; }
.panel-meta { display: flex; justify-content: space-between; gap: 12px; color: var(--sm-muted); font: 600 9px/1.2 var(--sm-font-mono); letter-spacing: .12em; }
.impact-hero { display: grid; gap: 10px; margin: auto 0; padding: 42px 0 36px; }
.impact-hero span { color: var(--sm-copy); font-size: 12px; }
.impact-hero strong { color: var(--sm-signal); font-family: var(--sm-font-display); font-size: clamp(40px, 4vw, 62px); font-weight: 560; letter-spacing: -.055em; line-height: 1; text-shadow: 0 0 30px rgba(242, 255, 220, .12); }
.impact-hero small { color: var(--sm-faint); font-size: 10px; }
.impact-grid { display: grid; grid-template-columns: repeat(3, 1fr); margin: 0; border-top: 1px solid var(--sm-line); }
.impact-grid div { display: grid; gap: 8px; padding: 18px 10px 16px 0; }
.impact-grid dt { color: var(--sm-muted); font-size: 10px; }
.impact-grid dd { margin: 0; color: var(--sm-ink); font-family: var(--sm-font-display); font-size: 20px; font-weight: 600; }
.experiment-line { display: flex; height: 26px; overflow: hidden; border: 1px solid var(--sm-line-strong); background: rgba(255,255,255,.025); }
.experiment-line span:first-child { display: flex; align-items: center; padding-left: 9px; color: #201326; background: var(--sm-signal); font: 650 8px/1 var(--sm-font-mono); white-space: nowrap; }
.experiment-line span:last-child { background: var(--sm-purple); }
.impact-panel > p { margin: 9px 0 0; color: var(--sm-faint); font-size: 9px; line-height: 1.5; }

@media (max-width: 560px) {
  .impact-grid { grid-template-columns: 1fr; }
  .impact-grid div + div { border-top: 1px solid var(--sm-line); }
}
</style>
