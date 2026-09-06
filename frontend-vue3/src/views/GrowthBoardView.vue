<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import BusinessQuery from '@/features/mission/components/BusinessQuery.vue'
import ChannelPortfolio from '@/features/mission/components/ChannelPortfolio.vue'
import ImpactForecast from '@/features/mission/components/ImpactForecast.vue'
import MissionActionRail from '@/features/mission/components/MissionActionRail.vue'
import MissionHero from '@/features/mission/components/MissionHero.vue'
import {
  approveMission,
  createDraftExport,
  diagnoseMission,
  downloadDraftExport,
  getTodayMission,
  resetMission,
  type Diagnosis,
  type DraftExport,
  type Mission,
} from '@/features/mission/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const mission = ref<Mission | null>(null)
const diagnosis = ref<Diagnosis | null>(null)
const draftExport = ref<DraftExport | null>(null)
const question = ref('')
const loading = ref(true)
const asking = ref(false)
const acting = ref(false)
const errorMessage = ref('')
const operationKeys = new Map<string, string>()
let queryGeneration = 0

const promptChips = [
  '哪个渠道粘性最强？',
  '有多少客户到了补货窗口？',
  '哪个产品更适合做老客？',
]

const statusLabel = computed(() => {
  if (draftExport.value) return '草稿名单已就绪'
  if (mission.value?.status === 'APPROVED') return '已审批，待生成名单'
  if (mission.value?.status === 'WAITING_MEASUREMENT') return '等待效果回收'
  return '等待 CEO 审批'
})

const canReset = computed(() => Boolean(
  mission.value?.demo_controls.reset_enabled && (authStore.isAdmin || authStore.localDemoNoLogin),
))

function operationKey(operation: string, missionId: string) {
  const identity = `${operation}:${missionId}`
  const existing = operationKeys.get(identity)
  if (existing) return existing
  const key = `${operation}-${missionId}-${globalThis.crypto.randomUUID()}`
  operationKeys.set(identity, key)
  return key
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
  if (!submitted || asking.value || acting.value) return
  const generation = ++queryGeneration
  question.value = submitted
  diagnosis.value = null
  asking.value = true
  errorMessage.value = ''
  try {
    const result = await diagnoseMission(submitted)
    if (generation === queryGeneration) diagnosis.value = result
  } catch (error: any) {
    if (generation === queryGeneration) errorMessage.value = error?.message || '问数失败'
  } finally {
    if (generation === queryGeneration) asking.value = false
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
      mission.value.state_timeline = mission.value.state_timeline.map((item) => ({ ...item, reached: true }))
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

async function resetDemo() {
  if (!mission.value || acting.value || !canReset.value) return
  // Invalidate before awaiting reset, including its failure path.
  ++queryGeneration
  asking.value = false
  acting.value = true
  errorMessage.value = ''
  try {
    mission.value = await resetMission(
      mission.value.mission_id,
      mission.value.version,
      operationKey('reset', mission.value.mission_id),
    )
    diagnosis.value = null
    draftExport.value = null
    question.value = ''
    operationKeys.clear()
  } catch (error: any) {
    errorMessage.value = error?.message || '演示重置失败'
  } finally {
    acting.value = false
  }
}

onMounted(loadMission)
onBeforeUnmount(() => { ++queryGeneration })
</script>

<template>
  <section class="growth-board" aria-labelledby="growth-board-title">
    <div class="ambient ambient-one" aria-hidden="true" />
    <div class="ambient ambient-two" aria-hidden="true" />
    <div class="board-gridlines" aria-hidden="true" />

    <header class="command-header">
      <div class="board-title">
        <span>CEO GROWTH BOARD / 01</span>
        <strong>客户运营全局营销</strong>
      </div>
      <div class="header-badges">
        <span class="badge badge-synthetic">SYNTHETIC DATA</span>
        <span class="badge">{{ mission?.data_provenance.analysis_as_of_date || '—' }}</span>
        <span class="badge badge-live"><i /> MISSION ONLINE</span>
      </div>
    </header>

    <div v-if="loading" class="state-panel" role="status">
      <span class="loader-mark">✦</span>
      <strong>正在生成今日经营命题</strong>
      <small>拆解首付费渠道、客户生命周期与复购信号</small>
    </div>

    <div v-else-if="!mission" class="state-panel state-error" role="alert">
      <strong>Mission 暂时不可用</strong>
      <span>{{ errorMessage }}</span>
      <button type="button" @click="loadMission">重新读取</button>
    </div>

    <template v-else>
      <div v-if="errorMessage" class="inline-error" role="alert">{{ errorMessage }}</div>

      <div class="hero-grid">
        <MissionHero :mission="mission" :status-label="statusLabel" />
        <ImpactForecast :mission="mission" />
      </div>

      <div class="intelligence-grid">
        <ChannelPortfolio :metrics="mission.channel_metrics" />
        <BusinessQuery
          v-model="question"
          :asking="asking"
          :diagnosis="diagnosis"
          :prompt-chips="promptChips"
          @ask="ask"
        />
      </div>

      <div class="evidence-ribbon" aria-label="指标证据">
        <span>METRIC EVIDENCE</span>
        <p v-for="item in mission.evidence" :key="item.metric">{{ item.finding }} <small>{{ item.metric_version }}</small></p>
      </div>

      <MissionActionRail
        :mission="mission"
        :draft-export="draftExport"
        :acting="acting"
        :can-reset="canReset"
        @approve="approveAndPrepareExport"
        @download="downloadExport"
        @reset="resetDemo"
      />

      <footer class="provenance-footer">
        <span>公开演示只使用合成数据 · 不含真实用户信息</span>
        <span>{{ mission.data_provenance.dataset_version }} · {{ mission.data_provenance.dataset_content_sha256.slice(0, 22) }}…</span>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.growth-board {
  position: relative;
  min-height: calc(var(--sm-dimension-vh-100) - var(--sm-dimension-px-76));
  overflow: hidden;
  margin: var(--sm-dimension-px-minus-20);
  padding: var(--sm-dimension-px-22) var(--sm-dimension-px-26) var(--sm-dimension-px-17);
  color: var(--sm-ink);
  background:
    radial-gradient(circle at 87% 9%, var(--sm-purple-glow), transparent 30%),
    radial-gradient(circle at 10% 84%, var(--sm-signal-soft), transparent 25%),
    var(--sm-gradient-bg);
  font-variant-numeric: tabular-nums;
}
.ambient { position: absolute; border-radius: 50%; filter: blur(var(--sm-dimension-px-70)); opacity: .28; pointer-events: none; }
.ambient-one { width: var(--sm-dimension-px-280); height: var(--sm-dimension-px-280); top: var(--sm-dimension-px-120); right: 18%; background: var(--sm-purple); }
.ambient-two { width: var(--sm-dimension-px-180); height: var(--sm-dimension-px-180); bottom: var(--sm-dimension-px-20); left: var(--sm-dimension-px-minus-80); background: var(--sm-lilac); opacity: .08; }
.board-gridlines { position: absolute; inset: 0; opacity: .17; pointer-events: none; background-image: linear-gradient(var(--sm-grid-line) var(--sm-dimension-px-1), transparent var(--sm-dimension-px-1)), linear-gradient(90deg, var(--sm-grid-line) var(--sm-dimension-px-1), transparent var(--sm-dimension-px-1)); background-size: var(--sm-dimension-px-88) var(--sm-dimension-px-88); mask-image: linear-gradient(to bottom, black, transparent 72%); }
.command-header, .hero-grid, .intelligence-grid, .evidence-ribbon, .provenance-footer, .state-panel, .inline-error { position: relative; z-index: 1; }
.command-header { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: var(--sm-dimension-px-27); margin-bottom: var(--sm-dimension-px-20); }
.board-title { display: grid; gap: var(--sm-dimension-px-3); }
.board-title span { color: var(--sm-faint); font: 600 var(--sm-dimension-px-8)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-13); }
.board-title strong { color: var(--sm-copy); font-size: var(--sm-dimension-px-12); font-weight: 560; }
.header-badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--sm-dimension-px-6); }
.badge { display: inline-flex; align-items: center; min-height: var(--sm-dimension-px-27); padding: 0 var(--sm-dimension-px-9); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-radius-pill); color: var(--sm-muted); background: var(--sm-glass-input); backdrop-filter: var(--sm-blur-overlay); font: 600 var(--sm-dimension-px-8)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-08); }
.badge-synthetic { border-color: var(--sm-signal-line); color: var(--sm-signal); }
.badge-live { color: var(--sm-lilac); }
.badge-live i { width: var(--sm-dimension-px-5); height: var(--sm-dimension-px-5); margin-right: var(--sm-dimension-px-6); border-radius: 50%; background: var(--sm-signal); box-shadow: 0 0 var(--sm-dimension-px-12) var(--sm-signal); }
.hero-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(var(--sm-dimension-px-330), .72fr); gap: var(--sm-dimension-px-12); }
.intelligence-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(var(--sm-dimension-px-370), .72fr); gap: var(--sm-dimension-px-12); margin-top: var(--sm-dimension-px-12); }
.evidence-ribbon { display: flex; align-items: center; gap: var(--sm-dimension-px-16); overflow-x: auto; margin: var(--sm-dimension-px-12) 0; padding: var(--sm-dimension-px-10) var(--sm-dimension-px-13); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-radius-control); color: var(--sm-muted); background: var(--sm-glass-input); backdrop-filter: var(--sm-blur-overlay); }
.evidence-ribbon > span { flex: 0 0 auto; color: var(--sm-lilac); font: 650 var(--sm-dimension-px-8)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-13); }
.evidence-ribbon p { display: inline-flex; flex: 0 0 auto; align-items: center; gap: var(--sm-dimension-px-8); margin: 0; font-size: var(--sm-dimension-px-9); }
.evidence-ribbon small { padding: var(--sm-dimension-px-3) var(--sm-dimension-px-5); border-radius: var(--sm-radius-pill); color: var(--sm-faint); background: var(--sm-white-faint); font: 500 var(--sm-dimension-px-7)/1 var(--sm-font-mono); }
.provenance-footer { display: flex; justify-content: space-between; gap: var(--sm-dimension-px-20); padding: var(--sm-dimension-px-11) var(--sm-dimension-px-2) 0; color: var(--sm-faint); font: 600 var(--sm-dimension-px-8)/1.4 var(--sm-font-mono); letter-spacing: var(--sm-dimension-em-0-07); }
.inline-error { margin-bottom: var(--sm-dimension-px-10); padding: var(--sm-dimension-px-9) var(--sm-dimension-px-12); border-left: var(--sm-dimension-px-2) solid var(--sm-danger); color: var(--sm-danger); background: var(--sm-danger-soft); font-size: var(--sm-dimension-px-11); }
.state-panel { display: grid; min-height: var(--sm-dimension-px-520); place-items: center; align-content: center; gap: var(--sm-dimension-px-8); border: var(--sm-dimension-px-1) solid var(--sm-line); border-radius: var(--sm-radius-panel); color: var(--sm-copy); background: var(--sm-glass); backdrop-filter: var(--sm-blur-panel); }
.state-panel strong { color: var(--sm-ink); font-size: var(--sm-dimension-px-17); }
.state-panel small { color: var(--sm-faint); }
.loader-mark { color: var(--sm-signal); font-size: var(--sm-dimension-px-30); animation: breathe 1.8s ease-in-out infinite; }
.state-error { color: var(--sm-danger); }
.state-error button { min-height: var(--sm-dimension-px-40); padding: 0 var(--sm-dimension-px-14); border: var(--sm-dimension-px-1) solid var(--sm-line-strong); border-radius: var(--sm-radius-control); color: var(--sm-ink); background: var(--sm-glass-subtle); cursor: pointer; }
@keyframes breathe { 50% { transform: scale(1.12) rotate(10deg); opacity: .65; } }

@media (max-width: 980px) {
  .hero-grid, .intelligence-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 720px) {
  .growth-board { margin: var(--sm-dimension-px-minus-12); padding: var(--sm-dimension-px-17) var(--sm-dimension-px-13); }
  .command-header { grid-template-columns: 1fr; gap: var(--sm-dimension-px-12); }
  .header-badges { justify-content: flex-start; }
  .provenance-footer { flex-direction: column; }
}
</style>
