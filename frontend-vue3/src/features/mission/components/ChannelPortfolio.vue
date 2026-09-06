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
.channel-panel { padding: var(--sm-dimension-px-24) var(--sm-dimension-px-26) var(--sm-dimension-px-20); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--sm-dimension-px-24); margin-bottom: var(--sm-dimension-px-18); }
.section-heading div:first-child > span { color: var(--sm-lilac); font: 650 var(--sm-dimension-px-9)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-14); }
h2 { max-width: var(--sm-dimension-px-680); margin: var(--sm-dimension-px-8) 0 0; color: var(--sm-ink); font-size: var(--sm-dimension-px-19); font-weight: 600; letter-spacing: var(--sm-dimension-em-minus-0-02); }
.leader-note { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--sm-dimension-px-7); }
.leader-note span { padding: var(--sm-dimension-px-7) var(--sm-dimension-px-9); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-radius-pill); color: var(--sm-muted); background: var(--sm-white-faint); font-size: var(--sm-dimension-px-9); }
.leader-note strong { margin-left: var(--sm-dimension-px-4); color: var(--sm-signal); }
.channel-row { display: grid; grid-template-columns: .7fr 1.2fr .72fr .72fr .78fr; align-items: center; gap: var(--sm-dimension-px-16); min-height: var(--sm-dimension-px-57); border-top: var(--sm-dimension-px-1) solid var(--sm-line); color: var(--sm-copy); font-size: var(--sm-dimension-px-12); }
.channel-head { min-height: var(--sm-dimension-px-34); border-top: 0; color: var(--sm-faint); font: 600 var(--sm-dimension-px-9)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-08); }
.channel-name { display: flex; align-items: center; gap: var(--sm-dimension-px-10); }
.channel-row--leader { border-color: var(--sm-line-strong); background: var(--sm-purple-soft); box-shadow: inset var(--sm-dimension-px-3) 0 0 var(--sm-lilac); }
.channel-name i { color: var(--sm-lilac-faint); font: 500 var(--sm-dimension-px-9)/1 var(--sm-font-display); }
.channel-name strong { color: var(--sm-ink); font-size: var(--sm-dimension-px-14); }
.channel-name em { padding: var(--sm-dimension-px-4) var(--sm-dimension-px-6); border: var(--sm-dimension-px-1) solid var(--sm-signal-line); border-radius: var(--sm-radius-pill); color: var(--sm-signal); font: 600 var(--sm-dimension-px-7)/1 var(--sm-font-display); font-style: normal; white-space: nowrap; }
.volume-cell { display: grid; grid-template-columns: var(--sm-dimension-px-48) 1fr; align-items: center; gap: var(--sm-dimension-px-10); }
.volume-cell b { color: var(--sm-copy-strong); font-family: var(--sm-font-display); font-weight: 560; }
.volume-cell > span { display: block; height: var(--sm-dimension-px-3); background: var(--sm-white-soft); }
.volume-cell > span i { display: block; height: 100%; background: var(--sm-gradient-secondary); box-shadow: 0 0 var(--sm-dimension-px-12) var(--sm-purple-glow); }
.channel-row > strong { color: var(--sm-copy-strong); font-family: var(--sm-font-display); font-size: var(--sm-dimension-px-14); font-weight: 560; }

@media (max-width: 840px) {
  .section-heading { flex-direction: column; }
  .leader-note { justify-content: flex-start; }
  .channel-table { overflow-x: auto; }
  .channel-row { min-width: var(--sm-dimension-px-720); }
}
</style>
