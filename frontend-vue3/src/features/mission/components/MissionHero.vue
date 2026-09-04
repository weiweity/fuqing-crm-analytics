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
.mission-hero { position: relative; overflow: hidden; padding: 28px 30px; }
.mission-hero::after {
  position: absolute;
  width: 260px;
  height: 260px;
  top: -130px;
  right: -80px;
  border: 1px solid var(--sm-signal-line);
  border-radius: 50%;
  box-shadow: 0 0 0 38px var(--sm-purple-soft), 0 0 0 76px var(--sm-white-faint);
  content: '';
  pointer-events: none;
}
.panel-meta { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 16px; color: var(--sm-muted); font: 600 10px/1.2 var(--sm-font-mono); letter-spacing: .12em; }
.mission-status { display: inline-flex; align-items: center; gap: 7px; color: var(--sm-signal); }
.mission-status i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; box-shadow: 0 0 15px currentColor; }
.mission-copy { position: relative; z-index: 1; max-width: 900px; padding: 54px 0 27px; }
.section-kicker { margin: 0 0 10px; color: var(--sm-lilac); font-size: 12px; font-weight: 650; letter-spacing: .08em; }
h1 { max-width: 820px; margin: 0; color: var(--sm-ink); font-family: var(--sm-font-display); font-size: clamp(36px, 4.4vw, 68px); font-weight: 610; letter-spacing: -.055em; line-height: .98; }
.executive-summary { max-width: 780px; margin: 20px 0 0; color: var(--sm-copy); font-size: 15px; line-height: 1.75; }
.decision-route { display: grid; grid-template-columns: 1fr auto 1fr auto 1.5fr; align-items: center; gap: 10px; }
.decision-route div { display: grid; min-height: 86px; align-content: center; gap: 6px; padding: 14px 16px; border: 1px solid var(--sm-line); border-radius: var(--sm-radius-pill); background: var(--sm-glass-subtle); box-shadow: inset 0 1px 0 var(--sm-white-top-line); }
.decision-route span { color: var(--sm-muted); font-size: 10px; letter-spacing: .08em; }
.decision-route strong { color: var(--sm-ink); font-size: 18px; font-weight: 650; }
.decision-route small { color: var(--sm-faint); font-size: 10px; }
.decision-route b { align-self: center; padding: 0 4px; color: var(--sm-lilac-faint); font: 500 9px/1 var(--sm-font-mono); }
.ai-recommendation { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 13px; padding-top: 20px; }
.ai-orb { display: grid; width: 38px; height: 38px; place-items: center; border: 1px solid var(--sm-line-accent); color: var(--sm-signal); background: var(--sm-signal-soft); box-shadow: inset 0 1px var(--sm-white-top-line); }
.ai-recommendation div { display: grid; gap: 4px; }
.ai-recommendation div > span { color: var(--sm-signal); font: 650 9px/1 var(--sm-font-mono); letter-spacing: .14em; }
.ai-recommendation p { margin: 0; color: var(--sm-copy-strong); font-size: 14px; line-height: 1.55; }

@media (max-width: 720px) {
  .mission-hero { padding: 22px 18px; }
  .panel-meta { align-items: flex-start; flex-direction: column; }
  .mission-copy { padding: 38px 0 22px; }
  .decision-route { grid-template-columns: 1fr; }
  .decision-route b { display: none; }
  .decision-route div + div { border-top: 1px solid var(--sm-line); }
}
</style>
