<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  approveMission,
  createDraftExport,
  diagnoseMission,
  downloadDraftExport,
  getTodayMission,
  type Diagnosis,
  type DraftExport,
  type Mission,
} from '@/features/mission/api'

const mission = ref<Mission | null>(null)
const diagnosis = ref<Diagnosis | null>(null)
const draftExport = ref<DraftExport | null>(null)
const question = ref('')
const loading = ref(true)
const asking = ref(false)
const acting = ref(false)
const errorMessage = ref('')
const operationKeys = new Map<string, string>()

const promptChips = [
  '哪个渠道粘性最强？',
  '有多少客户到了补货窗口？',
  '哪个产品更适合做老客？',
]

const maxCustomers = computed(() => {
  return Math.max(...(mission.value?.channel_metrics.map((item) => item.first_paid_customers) ?? [1]))
})

const statusLabel = computed(() => {
  if (draftExport.value) return '草稿名单已就绪'
  if (mission.value?.status === 'APPROVED') return '已审批，待生成名单'
  if (mission.value?.status === 'WAITING_MEASUREMENT') return '等待效果回收'
  return '等待 CEO 审批'
})

function operationKey(operation: string, missionId: string) {
  const identity = `${operation}:${missionId}`
  const existing = operationKeys.get(identity)
  if (existing) return existing
  const key = `${operation}-${missionId}-${globalThis.crypto.randomUUID()}`
  operationKeys.set(identity, key)
  return key
}

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

function channelTone(channel: string) {
  if (channel === '货架') return 'violet'
  if (channel === '直播') return 'cyan'
  return 'amber'
}

async function loadMission() {
  loading.value = true
  errorMessage.value = ''
  try {
    const nextMission = await getTodayMission()
    mission.value = nextMission
    draftExport.value = nextMission.latest_export
  } catch (error: any) {
    errorMessage.value = error?.message || '暂时无法读取今日 Mission'
  } finally {
    loading.value = false
  }
}

async function ask(nextQuestion?: string) {
  const submitted = (nextQuestion ?? question.value).trim()
  if (!submitted || asking.value) return
  question.value = submitted
  diagnosis.value = null
  asking.value = true
  errorMessage.value = ''
  try {
    diagnosis.value = await diagnoseMission(submitted)
  } catch (error: any) {
    errorMessage.value = error?.message || '问数失败'
  } finally {
    asking.value = false
  }
}

async function approveAndPrepareExport() {
  if (!mission.value || acting.value) return
  acting.value = true
  errorMessage.value = ''
  try {
    if (mission.value.status === 'AWAITING_APPROVAL') {
      mission.value = await approveMission(
        mission.value.mission_id,
        mission.value.version,
        operationKey('approve', mission.value.mission_id),
      )
    }
    if (mission.value.status === 'APPROVED') {
      draftExport.value = await createDraftExport(
        mission.value.mission_id,
        mission.value.version,
        operationKey('export', mission.value.mission_id),
      )
      mission.value.status = draftExport.value.mission_status
      mission.value.version = draftExport.value.mission_version
      mission.value.latest_export = draftExport.value
      mission.value.state_timeline = mission.value.state_timeline.map((item) => ({
        ...item,
        reached: true,
      }))
    }
  } catch (error: any) {
    errorMessage.value = error?.message || '审批或名单生成失败'
  } finally {
    acting.value = false
  }
}

async function downloadExport() {
  if (!draftExport.value || acting.value) return
  acting.value = true
  errorMessage.value = ''
  try {
    await downloadDraftExport(draftExport.value)
  } catch (error: any) {
    errorMessage.value = error?.message || '草稿名单下载失败'
  } finally {
    acting.value = false
  }
}

onMounted(loadMission)
</script>

<template>
  <section class="growth-board" aria-labelledby="growth-board-title">
    <div class="grid-noise" aria-hidden="true" />

    <header class="command-header">
      <div>
        <p class="eyebrow"><span class="pulse-dot" /> AUTONOMOUS COMMERCE · CEO CONTROL ROOM</p>
        <h1 id="growth-board-title">AI 增长董事会</h1>
      </div>
      <div class="header-badges">
        <span class="badge badge-synthetic">SYNTHETIC DATA</span>
        <span class="badge">{{ mission?.data_provenance.analysis_as_of_date || '—' }}</span>
        <span class="badge badge-live"><span class="pulse-dot" /> MISSION ONLINE</span>
      </div>
    </header>

    <div v-if="loading" class="state-panel" role="status">
      <span class="scan-line" />
      正在拆解渠道、人群与复购信号…
    </div>

    <div v-else-if="!mission" class="state-panel state-error" role="alert">
      <strong>Mission 暂时不可用</strong>
      <span>{{ errorMessage }}</span>
      <button type="button" @click="loadMission">重试</button>
    </div>

    <template v-else>
      <div v-if="errorMessage" class="inline-error" role="alert">{{ errorMessage }}</div>

      <div class="board-grid board-grid-hero">
        <article class="panel mission-hero">
          <div class="panel-kicker">
            <span>MISSION / {{ mission.mission_id.slice(-8).toUpperCase() }}</span>
            <span class="decision-status">{{ statusLabel }}</span>
          </div>
          <p class="decision-label">今日唯一经营命题</p>
          <h2>{{ mission.title }}</h2>
          <p class="executive-summary">{{ mission.executive_summary }}</p>

          <div class="thesis-strip">
            <div>
              <span class="thesis-label">规模入口</span>
              <strong>{{ mission.decision.volume_leader }}</strong>
            </div>
            <span class="thesis-arrow" aria-hidden="true">→</span>
            <div>
              <span class="thesis-label">质量标杆</span>
              <strong>{{ mission.decision.quality_leader }}</strong>
            </div>
            <span class="thesis-arrow" aria-hidden="true">→</span>
            <div>
              <span class="thesis-label">执行抓手</span>
              <strong>{{ mission.target_audience.activation_product.product_name }}</strong>
            </div>
          </div>

          <p class="recommendation"><span>AI 建议</span>{{ mission.recommendation }}</p>
        </article>

        <aside class="panel impact-panel">
          <div class="panel-kicker"><span>EXPECTED IMPACT</span><span>90 / 10 TEST</span></div>
          <div class="impact-orbit">
            <div class="impact-core">
              <span>预估增量毛利</span>
              <strong>{{ formatMoney(mission.economics.expected_incremental_margin) }}</strong>
              <small>合成测算 · 待实验验证</small>
            </div>
          </div>
          <div class="impact-stats">
            <div><span>可激活人群</span><strong>{{ mission.target_audience.eligible_customers }}</strong></div>
            <div><span>预估增量客户</span><strong>+{{ mission.economics.expected_incremental_customers }}</strong></div>
            <div><span>假设提升</span><strong>+{{ formatPercent(mission.economics.assumed_conversion_uplift) }}</strong></div>
          </div>
        </aside>
      </div>

      <div class="board-grid board-grid-lower">
        <article class="panel channel-panel">
          <div class="section-heading">
            <div><span>CHANNEL TRUTH</span><h3>流量不等于客户资产</h3></div>
            <p>同一 user_id 跨渠道归因</p>
          </div>
          <div class="channel-table">
            <div class="channel-row channel-row-head">
              <span>首付费渠道</span><span>获客规模</span><span>30 天二单率</span><span>180 天净价值</span>
            </div>
            <div v-for="item in mission.channel_metrics" :key="item.channel" class="channel-row">
              <span class="channel-name"><i :class="`tone-${channelTone(item.channel)}`" />{{ item.channel }}</span>
              <span class="volume-cell">
                <span class="metric-number">{{ item.first_paid_customers.toLocaleString() }}</span>
                <span class="bar-track"><i :class="`tone-bg-${channelTone(item.channel)}`" :style="{ width: `${item.first_paid_customers / maxCustomers * 100}%` }" /></span>
              </span>
              <strong>{{ formatPercent(item.second_paid_rate_30d) }}</strong>
              <strong>{{ formatMoney(item.avg_net_value_180d) }}</strong>
            </div>
          </div>
          <div class="evidence-ribbon">
            <span v-for="item in mission.evidence" :key="item.metric">{{ item.finding }}</span>
          </div>
        </article>

        <article class="panel ask-panel">
          <div class="section-heading">
            <div><span>ASK YOUR BUSINESS</span><h3>自由问数</h3></div>
            <span class="safe-pill">受控语义层 · 无 SQL</span>
          </div>
          <form class="ask-form" @submit.prevent="ask()">
            <input v-model="question" maxlength="300" placeholder="问渠道、生命周期或商品角色…" aria-label="自由问数问题" />
            <button type="submit" :disabled="asking || !question.trim()">
              {{ asking ? '分析中' : '提问' }} <span aria-hidden="true">↗</span>
            </button>
          </form>
          <div class="prompt-chips">
            <button v-for="chip in promptChips" :key="chip" type="button" @click="ask(chip)">{{ chip }}</button>
          </div>
          <div v-if="diagnosis" class="answer-card" aria-live="polite">
            <div class="answer-meta"><span>AI DIAGNOSIS</span><span>{{ diagnosis.intent }}</span></div>
            <p>{{ diagnosis.answer }}</p>
            <small>{{ diagnosis.limitations[0] }}</small>
          </div>
          <div v-else class="answer-placeholder">
            <span>⌁</span>
            <p>从“看报表”变成“问生意”，结论可追溯到指标版本。</p>
          </div>
        </article>
      </div>

      <article class="panel action-panel">
        <div class="mission-timeline" aria-label="Mission 状态流">
          <template v-for="(item, index) in mission.state_timeline" :key="item.state">
            <div class="timeline-step" :class="{ reached: item.reached }">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <strong>{{ item.state }}</strong>
            </div>
            <i v-if="index < mission.state_timeline.length - 1" :class="{ reached: mission.state_timeline[index + 1]?.reached }" />
          </template>
        </div>

        <div class="action-copy">
          <span>NEXT BEST ACTION</span>
          <strong v-if="!draftExport">审批后才会生成合成人群草稿，不会自动触达用户。</strong>
          <strong v-else>{{ draftExport.row_count }} 条合成人群已分成实验组与对照组。</strong>
          <small>{{ mission.decision.guardrail }}</small>
        </div>

        <button
          v-if="!draftExport && mission.status !== 'WAITING_MEASUREMENT'"
          type="button"
          class="approve-button"
          :disabled="acting"
          @click="approveAndPrepareExport"
        >
          <span>{{ acting ? '正在执行' : '审批并生成 DRAFT_EXPORT' }}</span>
          <small>90% EXPERIMENT · 10% HOLDOUT</small>
        </button>
        <button v-else-if="draftExport" type="button" class="approve-button export-ready" :disabled="acting" @click="downloadExport">
          <span>下载合成人群草稿</span>
          <small>{{ draftExport.export_id }} · {{ draftExport.row_count }} ROWS</small>
        </button>
        <div v-else class="complete-state">已进入效果观测期</div>
      </article>

      <footer class="provenance-footer">
        <span>公网演示数据 · 无真实用户信息</span>
        <span>{{ mission.data_provenance.dataset_version }} · {{ mission.data_provenance.dataset_content_sha256.slice(0, 22) }}…</span>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.growth-board {
  --bg: #061018;
  --panel: rgba(10, 25, 35, 0.9);
  --line: rgba(135, 231, 255, 0.14);
  --text: #eefaff;
  --muted: #83a3b2;
  --cyan: #56e4ff;
  --violet: #a987ff;
  --amber: #ffbe63;
  position: relative;
  min-height: calc(100vh - 88px);
  overflow: hidden;
  margin: -20px;
  padding: 28px 30px 18px;
  color: var(--text);
  background:
    radial-gradient(circle at 76% 5%, rgba(31, 188, 255, 0.13), transparent 28%),
    radial-gradient(circle at 12% 38%, rgba(137, 91, 255, 0.11), transparent 28%),
    linear-gradient(145deg, #07141d 0%, #050c13 70%);
  font-variant-numeric: tabular-nums;
}

.grid-noise {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.5;
  background-image:
    linear-gradient(var(--line) 1px, transparent 1px),
    linear-gradient(90deg, var(--line) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: linear-gradient(to bottom, black, transparent 72%);
}

.command-header,
.board-grid,
.action-panel,
.provenance-footer,
.state-panel,
.inline-error { position: relative; z-index: 1; }

.command-header { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 22px; }
.eyebrow, .panel-kicker, .section-heading span, .action-copy > span {
  margin: 0 0 7px;
  color: var(--cyan);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.18em;
}
.command-header h1 { margin: 0; font-size: clamp(28px, 3vw, 46px); letter-spacing: -0.04em; font-weight: 680; }
.pulse-dot { display: inline-block; width: 6px; height: 6px; margin-right: 7px; border-radius: 50%; background: #46f2bb; box-shadow: 0 0 12px #46f2bb; }
.header-badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.badge { padding: 7px 10px; border: 1px solid var(--line); color: #9db7c4; background: rgba(9, 21, 30, 0.78); font: 600 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0.08em; }
.badge-synthetic { border-color: rgba(255, 190, 99, 0.35); color: var(--amber); }
.badge-live { color: #85f6d1; }

.board-grid { display: grid; gap: 14px; }
.board-grid-hero { grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.75fr); }
.board-grid-lower { grid-template-columns: minmax(0, 1.25fr) minmax(360px, 0.75fr); margin-top: 14px; }
.panel { border: 1px solid var(--line); background: linear-gradient(145deg, rgba(11, 29, 40, 0.96), rgba(7, 19, 28, 0.94)); box-shadow: inset 0 1px rgba(255,255,255,.035), 0 24px 70px rgba(0,0,0,.18); }
.mission-hero { position: relative; overflow: hidden; padding: 26px 28px 24px; }
.mission-hero::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: linear-gradient(var(--cyan), var(--violet)); box-shadow: 0 0 20px var(--cyan); }
.panel-kicker { display: flex; align-items: center; justify-content: space-between; color: #648391; }
.decision-status { color: var(--amber); letter-spacing: .08em; }
.decision-label { margin: 32px 0 8px; color: #7e9ba9; font-size: 13px; }
.mission-hero h2 { max-width: 820px; margin: 0; font-size: clamp(30px, 4vw, 57px); line-height: 1.03; letter-spacing: -0.055em; font-weight: 680; background: linear-gradient(105deg, #fff 12%, #a8efff 62%, #bcabff); -webkit-background-clip: text; color: transparent; }
.executive-summary { max-width: 900px; margin: 18px 0 22px; color: #aac1cb; font-size: 16px; line-height: 1.8; }
.thesis-strip { display: grid; grid-template-columns: 1fr auto 1fr auto 1.35fr; align-items: center; gap: 18px; padding: 15px 18px; border: 1px solid rgba(86, 228, 255, .14); background: rgba(5, 15, 23, .62); }
.thesis-strip div { display: flex; flex-direction: column; gap: 4px; }
.thesis-label { color: #65818e; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; }
.thesis-strip strong { font-size: 17px; color: #e9faff; }
.thesis-arrow { color: var(--cyan); opacity: .5; }
.recommendation { display: grid; grid-template-columns: 70px 1fr; gap: 14px; margin: 20px 0 0; color: #c0d2da; font-size: 16px; line-height: 1.7; }
.recommendation span { color: var(--cyan); font-size: 11px; font-weight: 700; }

.impact-panel { padding: 22px; }
.impact-orbit { display: grid; place-items: center; min-height: 210px; background: radial-gradient(circle, rgba(86,228,255,.08), transparent 64%); }
.impact-core { display: grid; place-items: center; width: 188px; height: 188px; border: 1px solid rgba(86, 228, 255, .3); border-radius: 50%; box-shadow: 0 0 0 14px rgba(86,228,255,.025), 0 0 0 29px rgba(169,135,255,.025), inset 0 0 35px rgba(86,228,255,.08); }
.impact-core span { color: #7896a3; font-size: 11px; }
.impact-core strong { color: #fff; font-size: 32px; letter-spacing: -.04em; }
.impact-core small { max-width: 120px; color: #66818d; font-size: 9px; text-align: center; }
.impact-stats { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--line); }
.impact-stats div { display: grid; gap: 4px; padding: 14px 8px 0; text-align: center; }
.impact-stats span { color: #698793; font-size: 10px; }
.impact-stats strong { color: #dffaff; font-size: 19px; }

.channel-panel, .ask-panel { padding: 22px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 15px; margin-bottom: 20px; }
.section-heading h3 { margin: 0; font-size: 19px; }
.section-heading p { margin: 4px 0 0; color: #657f8b; font-size: 11px; }
.channel-row { display: grid; grid-template-columns: .75fr 1.2fr .7fr .7fr; align-items: center; gap: 16px; min-height: 54px; border-top: 1px solid rgba(135,231,255,.09); color: #a8bec8; font-size: 12px; }
.channel-row-head { min-height: 30px; border: 0; color: #56727e; font-size: 9px; letter-spacing: .1em; text-transform: uppercase; }
.channel-name { display: flex; align-items: center; gap: 9px; color: #dcebf1; font-weight: 650; }
.channel-name i { width: 7px; height: 7px; border-radius: 50%; box-shadow: 0 0 9px currentColor; }
.tone-cyan { color: var(--cyan); background: var(--cyan); }.tone-violet { color: var(--violet); background: var(--violet); }.tone-amber { color: var(--amber); background: var(--amber); }
.volume-cell { display: grid; grid-template-columns: 40px 1fr; align-items: center; gap: 9px; }
.metric-number { color: #cde0e8; font-family: ui-monospace, monospace; }
.bar-track { display: block; height: 3px; background: rgba(255,255,255,.06); }
.bar-track i { display: block; height: 100%; box-shadow: 0 0 9px currentColor; }
.tone-bg-cyan { color: var(--cyan); background: var(--cyan); }.tone-bg-violet { color: var(--violet); background: var(--violet); }.tone-bg-amber { color: var(--amber); background: var(--amber); }
.channel-row strong { color: #edfaff; font-size: 15px; }
.evidence-ribbon { display: flex; gap: 8px; overflow: auto; margin-top: 16px; padding-top: 15px; border-top: 1px solid var(--line); }
.evidence-ribbon span { flex: 0 0 auto; padding: 7px 9px; color: #7895a1; background: rgba(86,228,255,.045); font-size: 9px; }

.section-heading .safe-pill { padding: 5px 8px; border: 1px solid rgba(70,242,187,.2); color: #68d8b4; font-size: 9px; letter-spacing: .05em; }
.ask-form { display: grid; grid-template-columns: 1fr auto; border: 1px solid rgba(86, 228, 255, .22); background: rgba(3, 13, 20, .8); }
.ask-form:focus-within { border-color: rgba(86, 228, 255, .55); box-shadow: 0 0 24px rgba(86,228,255,.05); }
.ask-form input { min-width: 0; padding: 14px; border: 0; color: #e9faff; background: transparent; font: inherit; font-size: 16px; }
.ask-form input::placeholder { color: #4c6875; }
.ask-form button { min-height: 44px; border: 0; padding: 0 17px; color: #041018; background: var(--cyan); font-size: 13px; font-weight: 750; cursor: pointer; }
.ask-form button:focus-visible { outline: 2px solid #ffffff; outline-offset: 3px; }
.ask-form button:disabled { opacity: .4; cursor: not-allowed; }
.prompt-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.prompt-chips button { min-height: 44px; padding: 6px 10px; border: 1px solid rgba(135,231,255,.11); color: #8da6b0; background: transparent; font-size: 12px; cursor: pointer; }
.prompt-chips button:hover, .prompt-chips button:focus-visible { color: var(--cyan); border-color: rgba(86,228,255,.35); outline: 2px solid rgba(86,228,255,.5); outline-offset: 2px; }
.answer-card, .answer-placeholder { min-height: 110px; margin-top: 15px; padding: 16px; border: 1px solid rgba(169,135,255,.16); background: linear-gradient(135deg, rgba(169,135,255,.07), rgba(86,228,255,.035)); }
.answer-meta { display: flex; justify-content: space-between; color: var(--violet); font: 700 9px/1 ui-monospace, monospace; letter-spacing: .1em; }
.answer-card p { margin: 16px 0 10px; color: #d9e8ee; font-size: 16px; line-height: 1.75; }
.answer-card small { color: #66818c; font-size: 9px; }
.answer-placeholder { display: flex; align-items: center; gap: 14px; color: #7895a1; font-size: 16px; line-height: 1.6; }
.answer-placeholder > span { color: var(--violet); font-size: 28px; }

.action-panel { display: grid; grid-template-columns: minmax(430px, 1.3fr) minmax(260px, .8fr) minmax(270px, .65fr); align-items: center; gap: 24px; margin-top: 14px; padding: 18px 22px; }
.mission-timeline { display: flex; align-items: center; min-width: 0; }
.timeline-step { display: grid; gap: 3px; color: #496470; }
.timeline-step span { font: 700 8px/1 ui-monospace, monospace; }
.timeline-step strong { font: 650 8px/1.2 ui-monospace, monospace; letter-spacing: .02em; }
.timeline-step.reached { color: var(--cyan); }
.mission-timeline > i { flex: 1; min-width: 12px; height: 1px; margin: 0 8px; background: rgba(135,231,255,.12); }
.mission-timeline > i.reached { background: linear-gradient(90deg, var(--cyan), var(--violet)); box-shadow: 0 0 8px rgba(86,228,255,.5); }
.action-copy { display: grid; gap: 4px; }
.action-copy > span { margin: 0; }
.action-copy strong { color: #dcecf2; font-size: 11px; line-height: 1.5; }
.action-copy small { color: #5e7985; font-size: 8px; }
.approve-button { display: grid; gap: 3px; width: 100%; min-height: 52px; padding: 13px 17px; border: 1px solid #71e8ff; color: #06141c; background: linear-gradient(110deg, #64e7ff, #9fcbff); box-shadow: 0 0 26px rgba(86,228,255,.12); text-align: left; cursor: pointer; }
.approve-button:focus-visible, .state-error button:focus-visible { outline: 2px solid #ffffff; outline-offset: 3px; }
.approve-button:disabled { opacity: .55; cursor: wait; }
.approve-button span { font-size: 12px; font-weight: 750; }
.approve-button small { font: 700 8px/1.2 ui-monospace, monospace; opacity: .62; }
.approve-button.export-ready { border-color: #4ef1bc; background: linear-gradient(110deg, #4ef1bc, #74e8ff); }
.complete-state { color: #75eec6; font-size: 12px; text-align: right; }
.provenance-footer { display: flex; justify-content: space-between; gap: 20px; padding: 12px 2px 0; color: #405b67; font: 600 8px/1.4 ui-monospace, monospace; letter-spacing: .08em; }
.inline-error { margin-bottom: 10px; padding: 8px 12px; border-left: 2px solid #ff6c75; color: #ff9ca3; background: rgba(255,66,78,.08); font-size: 11px; }
.state-panel { display: grid; place-items: center; min-height: 420px; border: 1px solid var(--line); color: #75929f; background: var(--panel); }
.state-error { gap: 10px; color: #ff9aa2; }.state-error span { color: #829da8; }.state-error button { min-height: 44px; padding: 8px 14px; border: 1px solid var(--line); color: var(--cyan); background: transparent; }

@media (max-width: 1100px) {
  .board-grid-hero, .board-grid-lower { grid-template-columns: 1fr; }
  .action-panel { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .growth-board { margin: -12px; padding: 18px 14px; }
  .command-header { align-items: flex-start; flex-direction: column; gap: 14px; }
  .header-badges { justify-content: flex-start; }
  .mission-hero, .impact-panel, .channel-panel, .ask-panel { padding: 18px; }
  .thesis-strip { grid-template-columns: 1fr; }.thesis-arrow { transform: rotate(90deg); }
  .channel-row { grid-template-columns: .65fr 1fr .65fr; }.channel-row > :last-child { display: none; }
  .action-panel { padding: 16px; }
  .mission-timeline { overflow-x: auto; padding-bottom: 8px; }
  .provenance-footer { flex-direction: column; }
}

@media (prefers-reduced-motion: no-preference) {
  .pulse-dot { animation: pulse 2s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: .45; box-shadow: 0 0 3px #46f2bb; } }
}
</style>
