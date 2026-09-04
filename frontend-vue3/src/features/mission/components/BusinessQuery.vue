<script setup lang="ts">
import type { Diagnosis } from '@/features/mission/api'

defineProps<{
  modelValue: string
  asking: boolean
  diagnosis: Diagnosis | null
  promptChips: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  ask: [question?: string]
}>()
</script>

<template>
  <article class="glass-panel query-panel">
    <header class="section-heading">
      <div>
        <span>ASK YOUR BUSINESS</span>
        <h2>自由问数，不自由编数</h2>
      </div>
      <span class="guardrail">DETERMINISTIC TOOL</span>
    </header>

    <form class="ask-form" @submit.prevent="emit('ask')">
      <label>
        <span>向经营数据提问</span>
        <input
          :value="modelValue"
          maxlength="300"
          placeholder="问渠道粘性、生命周期或商品角色…"
          aria-label="自由问数问题"
          @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        />
      </label>
      <button type="submit" :disabled="asking || !modelValue.trim()">
        <span>{{ asking ? '正在诊断' : '生成诊断' }}</span>
        <b aria-hidden="true">↗</b>
      </button>
    </form>

    <div class="prompt-chips" aria-label="推荐问题">
      <button v-for="chip in promptChips" :key="chip" type="button" @click="emit('ask', chip)">{{ chip }}</button>
    </div>

    <div v-if="diagnosis" class="answer-card" aria-live="polite">
      <div class="answer-meta"><span>AI DIAGNOSIS</span><span>{{ diagnosis.intent }}</span></div>
      <p>{{ diagnosis.answer }}</p>
      <small>边界：{{ diagnosis.limitations[0] }}</small>
    </div>
    <div v-else class="answer-placeholder">
      <span aria-hidden="true">✦</span>
      <div>
        <strong>从“看报表”变成“问生意”</strong>
        <p>回答只调用已登记指标，并保留版本、证据和数据日期。</p>
      </div>
    </div>
  </article>
</template>

<style scoped>
.query-panel { display: flex; min-height: 100%; flex-direction: column; padding: 24px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.section-heading div > span { color: var(--sm-lilac); font: 650 9px/1 var(--sm-font-mono); letter-spacing: .14em; }
h2 { margin: 8px 0 0; color: var(--sm-ink); font-size: 20px; font-weight: 600; letter-spacing: -.02em; }
.guardrail { padding: 7px 9px; border: 1px solid var(--sm-signal-line); border-radius: var(--sm-radius-pill); color: var(--sm-signal); background: var(--sm-signal-soft); font: 650 8px/1 var(--sm-font-mono); letter-spacing: .08em; }
.ask-form { display: grid; grid-template-columns: 1fr auto; margin-top: 28px; overflow: hidden; border: 1px solid var(--sm-line-strong); border-radius: var(--sm-radius-control); background: var(--sm-glass-input); box-shadow: inset 0 1px var(--sm-white-faint); transition: border-color var(--sm-motion-fast), box-shadow var(--sm-motion-fast); }
.ask-form:focus-within { border-color: var(--sm-purple); box-shadow: var(--sm-shadow-focus); }
.ask-form label { display: grid; gap: 3px; padding: 10px 14px; }
.ask-form label span { color: var(--sm-faint); font-size: 8px; letter-spacing: .08em; }
.ask-form input { min-width: 0; padding: 0; border: 0; outline: 0; color: var(--sm-ink); background: transparent; font: 14px/1.5 var(--sm-font-body); }
.ask-form input::placeholder { color: var(--sm-lilac-faint); }
.ask-form button { display: flex; min-width: 116px; align-items: center; justify-content: space-between; gap: 13px; border: 0; padding: 0 15px; color: var(--sm-on-accent); background: var(--sm-signal); font-size: 11px; font-weight: 700; cursor: pointer; }
.ask-form button:disabled { opacity: .35; cursor: not-allowed; }
.ask-form button b { font-size: 16px; }
.prompt-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.prompt-chips button { min-height: 34px; padding: 6px 11px; border: 1px solid var(--sm-line); border-radius: var(--sm-radius-pill); color: var(--sm-muted); background: var(--sm-gradient-chip); font-size: 10px; cursor: pointer; transition: color var(--sm-motion-fast), border-color var(--sm-motion-fast), transform var(--sm-motion-fast); }
.prompt-chips button:hover, .prompt-chips button:focus-visible { border-color: var(--sm-line-strong); color: var(--sm-ink); transform: translateY(-1px); }
.answer-card, .answer-placeholder { min-height: 126px; margin-top: 16px; padding: 17px; border-top: 1px solid var(--sm-line); background: var(--sm-gradient-answer); }
.answer-meta { display: flex; justify-content: space-between; color: var(--sm-lilac); font: 650 8px/1 var(--sm-font-mono); letter-spacing: .11em; }
.answer-card p { margin: 18px 0 10px; color: var(--sm-copy-strong); font-size: 14px; line-height: 1.7; }
.answer-card small { color: var(--sm-faint); font-size: 9px; }
.answer-placeholder { display: flex; align-items: center; gap: 13px; color: var(--sm-muted); }
.answer-placeholder > span { color: var(--sm-signal); font-size: 24px; }
.answer-placeholder strong { color: var(--sm-copy-strong); font-size: 13px; }
.answer-placeholder p { margin: 4px 0 0; font-size: 10px; line-height: 1.5; }

@media (max-width: 560px) {
  .section-heading { flex-direction: column; }
  .ask-form { grid-template-columns: 1fr; }
  .ask-form button { min-height: 44px; }
}
</style>
