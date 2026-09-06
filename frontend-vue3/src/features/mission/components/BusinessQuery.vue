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
.query-panel { display: flex; min-height: 100%; flex-direction: column; padding: var(--sm-dimension-px-24); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--sm-dimension-px-14); }
.section-heading div > span { color: var(--sm-lilac); font: 650 var(--sm-dimension-px-9)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-14); }
h2 { margin: var(--sm-dimension-px-8) 0 0; color: var(--sm-ink); font-size: var(--sm-dimension-px-20); font-weight: 600; letter-spacing: var(--sm-dimension-em-minus-0-02); }
.guardrail { padding: var(--sm-dimension-px-7) var(--sm-dimension-px-9); border: var(--sm-dimension-px-1) solid var(--sm-signal-line); border-radius: var(--sm-radius-pill); color: var(--sm-signal); background: var(--sm-signal-soft); font: 650 var(--sm-dimension-px-8)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-08); }
.ask-form { display: grid; grid-template-columns: 1fr auto; margin-top: var(--sm-dimension-px-28); overflow: hidden; border: var(--sm-dimension-px-1) solid var(--sm-line-strong); border-radius: var(--sm-radius-control); background: var(--sm-glass-input); box-shadow: inset 0 var(--sm-dimension-px-1) var(--sm-white-faint); transition: border-color var(--sm-motion-fast), box-shadow var(--sm-motion-fast); }
.ask-form:focus-within { border-color: var(--sm-purple); box-shadow: var(--sm-shadow-focus); animation: query-focus-breath var(--sm-motion-focus-breath) infinite; }
@keyframes query-focus-breath {
  0%, 100% { box-shadow: var(--sm-shadow-focus-rest); }
  50% { box-shadow: var(--sm-shadow-focus); }
}
@media (prefers-reduced-motion: reduce) {
  .ask-form:focus-within { animation: none; }
}
.ask-form label { display: grid; gap: var(--sm-dimension-px-3); padding: var(--sm-dimension-px-10) var(--sm-dimension-px-14); }
.ask-form label span { color: var(--sm-faint); font-size: var(--sm-dimension-px-8); letter-spacing: var(--sm-dimension-em-0-08); }
.ask-form input { min-width: 0; padding: 0; border: 0; outline: 0; color: var(--sm-ink); background: transparent; font: var(--sm-dimension-px-14)/1.5 var(--sm-font-body); }
.ask-form input::placeholder { color: var(--sm-lilac-faint); }
.ask-form button { display: flex; min-width: var(--sm-dimension-px-116); align-items: center; justify-content: space-between; gap: var(--sm-dimension-px-13); border: 0; padding: 0 var(--sm-dimension-px-15); color: var(--sm-on-accent); background: var(--sm-signal); font-size: var(--sm-dimension-px-11); font-weight: 700; cursor: pointer; }
.ask-form button:disabled { opacity: .35; cursor: not-allowed; }
.ask-form button b { font-size: var(--sm-dimension-px-16); }
.prompt-chips { display: flex; flex-wrap: wrap; gap: var(--sm-dimension-px-6); margin-top: var(--sm-dimension-px-8); }
.prompt-chips button { min-height: var(--sm-dimension-px-34); padding: var(--sm-dimension-px-6) var(--sm-dimension-px-11); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-radius-pill); color: var(--sm-muted); background: var(--sm-gradient-chip); font-size: var(--sm-dimension-px-10); cursor: pointer; transition: color var(--sm-motion-fast), border-color var(--sm-motion-fast), transform var(--sm-motion-fast); }
.prompt-chips button:hover, .prompt-chips button:focus-visible { border-color: var(--sm-line-strong); color: var(--sm-ink); transform: translateY(var(--sm-dimension-px-minus-1)); }
.answer-card, .answer-placeholder { min-height: var(--sm-dimension-px-126); margin-top: var(--sm-dimension-px-16); padding: var(--sm-dimension-px-17); border-top: var(--sm-dimension-px-1) solid var(--sm-line); background: var(--sm-gradient-answer); }
.answer-meta { display: flex; justify-content: space-between; color: var(--sm-lilac); font: 650 var(--sm-dimension-px-8)/1 var(--sm-font-mono); letter-spacing: var(--sm-dimension-em-0-11); }
.answer-card p { margin: var(--sm-dimension-px-18) 0 var(--sm-dimension-px-10); color: var(--sm-copy-strong); font-size: var(--sm-dimension-px-14); line-height: 1.7; }
.answer-card small { color: var(--sm-faint); font-size: var(--sm-dimension-px-9); }
.answer-placeholder { display: flex; align-items: center; gap: var(--sm-dimension-px-13); color: var(--sm-muted); }
.answer-placeholder > span { color: var(--sm-signal); font-size: var(--sm-dimension-px-24); }
.answer-placeholder strong { color: var(--sm-copy-strong); font-size: var(--sm-dimension-px-13); }
.answer-placeholder p { margin: var(--sm-dimension-px-4) 0 0; font-size: var(--sm-dimension-px-10); line-height: 1.5; }

@media (max-width: 560px) {
  .section-heading { flex-direction: column; }
  .ask-form { grid-template-columns: 1fr; }
  .ask-form button { min-height: var(--sm-dimension-px-44); }
}
</style>
