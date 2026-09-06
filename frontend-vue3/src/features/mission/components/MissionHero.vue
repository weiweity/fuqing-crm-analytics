<script setup lang="ts">
import type { Mission } from '@/features/mission/api'

defineProps<{
  mission: Mission
  statusLabel: string
}>()
</script>

<template>
  <article class="glass-panel mission-hero">
    <div class="panel-meta">
      <span>MISSION / {{ mission.mission_id.slice(-8).toUpperCase() }}</span>
      <span class="mission-status"><i />{{ statusLabel }}</span>
    </div>

    <div class="mission-copy">
      <p class="section-kicker">今日唯一经营命题</p>
      <h1 id="growth-board-title">{{ mission.title }}</h1>
      <p class="executive-summary">{{ mission.executive_summary }}</p>
    </div>

    <div class="decision-route" aria-label="经营决策链路">
      <div>
        <span>规模入口</span>
        <strong>{{ mission.decision.volume_leader }}</strong>
        <small>负责把客户带进来</small>
      </div>
      <b aria-hidden="true">01</b>
      <div>
        <span>质量标杆</span>
        <strong>{{ mission.decision.quality_leader }}</strong>
        <small>负责沉淀客户价值</small>
      </div>
      <b aria-hidden="true">02</b>
      <div>
        <span>执行抓手</span>
        <strong>{{ mission.target_audience.activation_product.product_name }}</strong>
        <small>{{ mission.target_audience.segment_name }}</small>
      </div>
    </div>

    <div class="ai-recommendation">
      <span class="ai-orb" aria-hidden="true">✦</span>
      <div>
        <span>AI BOARD NOTE</span>
        <p>{{ mission.recommendation }}</p>
      </div>
    </div>
  </article>
</template>

<style scoped>
.mission-hero { position: relative; overflow: hidden; padding: var(--sm-dimension-px-28) var(--sm-dimension-px-30); }
.mission-hero::after {
  position: absolute;
  width: var(--sm-dimension-px-260);
  height: var(--sm-dimension-px-260);
  top: var(--sm-dimension-px-minus-130);
  right: var(--sm-dimension-px-minus-80);
  border: var(--sm-dimension-px-1) solid var(--sm-signal-line);
  border-radius: 50%;
  box-shadow: 0 0 0 var(--sm-dimension-px-38) var(--sm-purple-soft), 0 0 0 var(--sm-dimension-px-76) var(--sm-white-faint);
  content: '';
  pointer-events: none;
}
.panel-meta { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: var(--sm-dimension-px-16); color: var(--sm-muted); font: 600 var(--sm-dimension-px-10)/1.2 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-12); }
.mission-status { display: inline-flex; align-items: center; gap: var(--sm-dimension-px-7); color: var(--sm-signal); }
.mission-status i { width: var(--sm-dimension-px-6); height: var(--sm-dimension-px-6); border-radius: 50%; background: currentColor; box-shadow: 0 0 var(--sm-dimension-px-15) currentColor; }
.mission-copy { position: relative; z-index: 1; max-width: var(--sm-dimension-px-900); padding: var(--sm-dimension-px-54) 0 var(--sm-dimension-px-27); }
.section-kicker { margin: 0 0 var(--sm-dimension-px-10); color: var(--sm-lilac); font-size: var(--sm-dimension-px-12); font-weight: 650; letter-spacing: var(--sm-dimension-em-0-08); }
h1 { max-width: var(--sm-dimension-px-820); margin: 0; color: var(--sm-ink); font-family: var(--sm-font-display); font-size: clamp(var(--sm-dimension-px-36), var(--sm-dimension-vw-4-4), var(--sm-dimension-px-68)); font-weight: 610; letter-spacing: var(--sm-dimension-em-minus-0-055); line-height: .98; }
.executive-summary { max-width: var(--sm-dimension-px-780); margin: var(--sm-dimension-px-20) 0 0; color: var(--sm-copy); font-size: var(--sm-dimension-px-15); line-height: 1.75; }
.decision-route { display: grid; grid-template-columns: 1fr auto 1fr auto 1.5fr; align-items: center; gap: var(--sm-dimension-px-10); }
.decision-route div { display: grid; min-height: var(--sm-dimension-px-86); align-content: center; gap: var(--sm-dimension-px-6); padding: var(--sm-dimension-px-14) var(--sm-dimension-px-16); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-radius-pill); background: var(--sm-glass-subtle); box-shadow: inset 0 var(--sm-dimension-px-1) 0 var(--sm-white-top-line); }
.decision-route span { color: var(--sm-muted); font-size: var(--sm-dimension-px-10); letter-spacing: var(--sm-dimension-em-0-08); }
.decision-route strong { color: var(--sm-ink); font-size: var(--sm-dimension-px-18); font-weight: 650; }
.decision-route small { color: var(--sm-faint); font-size: var(--sm-dimension-px-10); }
.decision-route b { align-self: center; padding: 0 var(--sm-dimension-px-4); color: var(--sm-lilac-faint); font: 500 var(--sm-dimension-px-9)/1 var(--sm-font-display); }
.ai-recommendation { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: var(--sm-dimension-px-13); padding-top: var(--sm-dimension-px-20); }
.ai-orb { display: grid; width: var(--sm-dimension-px-38); height: var(--sm-dimension-px-38); place-items: center; border: var(--sm-dimension-px-1) solid var(--sm-line-accent); color: var(--sm-signal); background: var(--sm-signal-soft); box-shadow: inset 0 var(--sm-dimension-px-1) var(--sm-white-top-line); }
.ai-recommendation div { display: grid; gap: var(--sm-dimension-px-4); }
.ai-recommendation div > span { color: var(--sm-signal); font: 650 var(--sm-dimension-px-9)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-14); }
.ai-recommendation p { margin: 0; color: var(--sm-copy-strong); font-size: var(--sm-dimension-px-14); line-height: 1.55; }

@media (max-width: 720px) {
  .mission-hero { padding: var(--sm-dimension-px-22) var(--sm-dimension-px-18); }
  .panel-meta { align-items: flex-start; flex-direction: column; }
  .mission-copy { padding: var(--sm-dimension-px-38) 0 var(--sm-dimension-px-22); }
  .decision-route { grid-template-columns: 1fr; }
  .decision-route b { display: none; }
  .decision-route div + div { border-top: var(--sm-dimension-px-1) solid var(--sm-line); }
}
</style>
