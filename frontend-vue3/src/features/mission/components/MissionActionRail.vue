<script setup lang="ts">
import type { DraftExport, Mission } from '@/features/mission/api'

defineProps<{
  mission: Mission
  draftExport: DraftExport | null
  acting: boolean
  canReset: boolean
}>()

defineEmits<{
  approve: []
  download: []
  reset: []
}>()

const stateLabels: Record<string, string> = {
  DISCOVERED: '发现机会',
  EVIDENCE_READY: '证据就绪',
  AWAITING_APPROVAL: '等待审批',
  APPROVED: '已审批',
  WAITING_MEASUREMENT: '效果观测',
}
</script>

<template>
  <article class="glass-panel action-panel">
    <div class="state-flow" aria-label="Mission 状态流">
      <template v-for="(item, index) in mission.state_timeline" :key="item.state">
        <div class="state-step" :class="{ reached: item.reached }">
          <i>{{ String(index + 1).padStart(2, '0') }}</i>
          <strong>{{ stateLabels[item.state] || item.state }}</strong>
          <small>{{ item.state }}</small>
        </div>
        <span v-if="index < mission.state_timeline.length - 1" :class="{ reached: mission.state_timeline[index + 1]?.reached }" />
      </template>
    </div>

    <div class="action-copy">
      <span>NEXT BEST ACTION</span>
      <strong v-if="!draftExport">批准后仅生成合成人群草稿，不会自动触达用户。</strong>
      <strong v-else>{{ draftExport.row_count }} 条合成人群已按 90/10 分成实验组与对照组。</strong>
      <small>{{ mission.decision.guardrail }}</small>
    </div>

    <div class="action-controls">
      <button
        v-if="!draftExport && mission.status !== 'WAITING_MEASUREMENT'"
        type="button"
        class="approve-button"
        :disabled="acting"
        @click="$emit('approve')"
      >
        <span>{{ acting ? '正在执行' : '审批并生成 DRAFT_EXPORT' }}</span>
        <small>(90% EXPERIMENT · 10% HOLDOUT)</small>
      </button>
      <button
        v-else-if="draftExport"
        type="button"
        class="approve-button export-ready"
        :disabled="acting"
        @click="$emit('download')"
      >
        <span>下载合成人群草稿</span>
        <small>{{ draftExport.export_id }} · {{ draftExport.row_count }} ROWS</small>
      </button>
      <div v-else class="complete-state">已进入效果观测期</div>
      <button v-if="canReset" type="button" class="reset-demo-button" :disabled="acting" @click="$emit('reset')">重置演示</button>
    </div>
  </article>
</template>

<style scoped>
.action-panel { display: grid; grid-template-columns: minmax(520px, 1.35fr) minmax(240px, .75fr) minmax(270px, .65fr); align-items: center; gap: 24px; padding: 18px 22px; }
.state-flow { display: flex; align-items: center; min-width: 0; }
.state-step { display: grid; gap: 3px; color: var(--sm-lilac-faint); }
.state-step i { font: 650 8px/1 var(--sm-font-mono); }
.state-step strong { font-size: 9px; font-weight: 650; white-space: nowrap; }
.state-step small { font: 500 7px/1 var(--sm-font-mono); white-space: nowrap; }
.state-step.reached { color: var(--sm-signal); }
.state-flow > span { flex: 1; min-width: 13px; height: 1px; margin: 0 8px; background: var(--sm-line); }
.state-flow > span.reached { background: var(--sm-gradient-secondary); box-shadow: var(--sm-shadow-signal); }
.action-copy { display: grid; gap: 5px; }
.action-copy > span { color: var(--sm-lilac); font: 650 8px/1 var(--sm-font-mono); letter-spacing: .12em; }
.action-copy strong { color: var(--sm-copy-strong); font-size: 11px; line-height: 1.5; }
.action-copy small { color: var(--sm-faint); font-size: 8px; }
.action-controls { display: grid; gap: 7px; }
.approve-button { display: grid; gap: 4px; min-height: 55px; padding: 12px 16px; border: 1px solid var(--sm-white-top-line); border-radius: var(--sm-radius-control); color: var(--sm-ink); background: var(--sm-gradient-primary); box-shadow: var(--sm-shadow-button); text-align: left; cursor: pointer; transition: transform var(--sm-motion-standard), box-shadow var(--sm-motion-standard), border-color var(--sm-motion-standard); }
.approve-button:hover:not(:disabled), .approve-button:focus-visible:not(:disabled) { border-color: var(--sm-line-accent); box-shadow: var(--sm-shadow-button-hover); transform: translateY(-2px); }
.approve-button:disabled { opacity: .5; cursor: wait; }
.approve-button span { font-size: 12px; font-weight: 750; }
.approve-button small { font: 650 8px/1.2 var(--sm-font-mono); opacity: .58; }
.approve-button.export-ready { color: var(--sm-on-accent); background: var(--sm-lilac); border-color: var(--sm-lilac); }
.reset-demo-button { min-height: 32px; border: 1px solid var(--sm-line); border-radius: var(--sm-radius-control); color: var(--sm-muted); background: var(--sm-white-faint); font-size: 9px; cursor: pointer; }
.reset-demo-button:hover, .reset-demo-button:focus-visible { color: var(--sm-ink); border-color: var(--sm-line-strong); }
.complete-state { color: var(--sm-signal); font-size: 11px; text-align: right; }

@media (max-width: 1220px) {
  .action-panel { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .state-flow { overflow-x: auto; padding-bottom: 8px; }
}
</style>
