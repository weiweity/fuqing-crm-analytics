<script setup lang="ts">
import { computed } from 'vue'
import type { ChannelMetric } from '@/features/mission/api'

const props = defineProps<{ metrics: ChannelMetric[] }>()

const maxCustomers = computed(() => Math.max(...props.metrics.map((item) => item.first_paid_customers), 1))
const stickinessLeader = computed(() => props.metrics.reduce((best, item) => item.second_paid_rate_30d > best.second_paid_rate_30d ? item : best, props.metrics[0]))
const valueLeader = computed(() => props.metrics.reduce((best, item) => item.avg_net_value_180d > best.avg_net_value_180d ? item : best, props.metrics[0]))

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(value)
}
</script>

<template>
  <article class="glass-panel channel-panel">
    <header class="section-heading">
      <div>
        <span>CHANNEL ASSET TRUTH</span>
        <h2>渠道带来流量，跨渠道 user_id 才沉淀客户资产</h2>
      </div>
      <div class="leader-note">
        <span>粘性领先 <strong>{{ stickinessLeader?.channel }}</strong></span>
        <span>净价值领先 <strong>{{ valueLeader?.channel }}</strong></span>
      </div>
    </header>

    <div class="channel-table" role="table" aria-label="渠道客户资产对比">
      <div class="channel-row channel-head" role="row">
        <span role="columnheader">首付费渠道</span>
        <span role="columnheader">获客规模</span>
        <span role="columnheader">30 天二单率</span>
        <span role="columnheader">跨渠道率</span>
        <span role="columnheader">180 天净价值</span>
      </div>
      <div
        v-for="(item, index) in metrics"
        :key="item.channel"
        class="channel-row"
        :class="{ 'channel-row--leader': item.channel === stickinessLeader?.channel }"
        role="row"
      >
        <span class="channel-name" role="cell">
          <i>{{ String(index + 1).padStart(2, '0') }}</i><strong>{{ item.channel }}</strong>
          <em v-if="item.channel === stickinessLeader?.channel">粘性第一</em>
        </span>
        <span class="volume-cell" role="cell">
          <b>{{ item.first_paid_customers.toLocaleString() }}</b>
          <span><i :style="{ width: `${item.first_paid_customers / maxCustomers * 100}%` }" /></span>
        </span>
        <strong role="cell">{{ formatPercent(item.second_paid_rate_30d) }}</strong>
        <strong role="cell">{{ formatPercent(item.cross_channel_rate) }}</strong>
        <strong role="cell">{{ formatMoney(item.avg_net_value_180d) }}</strong>
      </div>
    </div>
  </article>
</template>

<style scoped>
.channel-panel { padding: 24px 26px 20px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 18px; }
.section-heading div:first-child > span { color: var(--sm-lilac); font: 650 9px/1 var(--sm-font-mono); letter-spacing: .14em; }
h2 { max-width: 680px; margin: 8px 0 0; color: var(--sm-ink); font-size: 19px; font-weight: 600; letter-spacing: -.02em; }
.leader-note { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }
.leader-note span { padding: 7px 9px; border: 1px solid var(--sm-line); border-radius: var(--sm-radius-pill); color: var(--sm-muted); background: var(--sm-white-faint); font-size: 9px; }
.leader-note strong { margin-left: 4px; color: var(--sm-signal); }
.channel-row { display: grid; grid-template-columns: .7fr 1.2fr .72fr .72fr .78fr; align-items: center; gap: 16px; min-height: 57px; border-top: 1px solid var(--sm-line); color: var(--sm-copy); font-size: 12px; }
.channel-head { min-height: 34px; border-top: 0; color: var(--sm-faint); font: 600 9px/1 var(--sm-font-mono); letter-spacing: .08em; }
.channel-name { display: flex; align-items: center; gap: 10px; }
.channel-row--leader { border-color: var(--sm-line-strong); background: var(--sm-purple-soft); box-shadow: inset 3px 0 0 var(--sm-lilac); }
.channel-name i { color: var(--sm-lilac-faint); font: 500 9px/1 var(--sm-font-mono); }
.channel-name strong { color: var(--sm-ink); font-size: 14px; }
.channel-name em { padding: 4px 6px; border: 1px solid var(--sm-signal-line); border-radius: var(--sm-radius-pill); color: var(--sm-signal); font: 600 7px/1 var(--sm-font-mono); font-style: normal; white-space: nowrap; }
.volume-cell { display: grid; grid-template-columns: 48px 1fr; align-items: center; gap: 10px; }
.volume-cell b { color: var(--sm-copy-strong); font-family: var(--sm-font-display); font-weight: 560; }
.volume-cell > span { display: block; height: 3px; background: var(--sm-white-soft); }
.volume-cell > span i { display: block; height: 100%; background: var(--sm-gradient-secondary); box-shadow: 0 0 12px var(--sm-purple-glow); }
.channel-row > strong { color: var(--sm-copy-strong); font-family: var(--sm-font-display); font-size: 14px; font-weight: 560; }

@media (max-width: 840px) {
  .section-heading { flex-direction: column; }
  .leader-note { justify-content: flex-start; }
  .channel-table { overflow-x: auto; }
  .channel-row { min-width: 720px; }
}
</style>
