<template>
  <div class="login-container">
    <div class="illustration-section" ref="illustrationSectionRef">
      <canvas ref="riveCanvasRef"></canvas>
      <div class="illustration-shade" />
      <div class="illustration-copy">
        <BrandMark />
        <div>
          <span>AUTONOMOUS COMMERCE PROTOTYPE</span>
          <h1>把经营信号，变成一条<br>可审批的增长 Mission</h1>
          <p>统一 user_id，拆解首付费渠道、生命周期与商品角色；AI 先诊断，CEO 再决定是否执行。</p>
        </div>
        <ol>
          <li><i>01</i><span>发现机会<small>DATA DIAGNOSIS</small></span></li>
          <li><i>02</i><span>自由问数<small>CONTROLLED AI</small></span></li>
          <li><i>03</i><span>审批执行<small>DRAFT EXPORT</small></span></li>
        </ol>
      </div>
    </div>

    <div class="form-section">
      <div class="form-wrapper">
        <div class="header-group">
          <BrandMark class="mobile-brand" />
          <span>LOCAL DEMO ACCESS</span>
          <h2 class="welcome-title">进入增长董事会</h2>
          <p class="subtitle">本地演示环境 · 合成数据 · 不含真实用户信息</p>
        </div>

        <form class="login-form" @submit.prevent="handleSubmit">
          <div
            class="input-group"
            :class="{ 'error-state': usernameErr, shake: usernameShake }"
          >
            <input
              ref="usernameInputRef"
              v-model="username"
              type="text"
              placeholder=" "
              required
              @input="handleUsernameInput"
              @focus="updateStatus"
              @blur="updateStatusDelayed"
            >
            <label class="floating-label">账号</label>
          </div>
          <div class="error-message" v-show="usernameErr">{{ usernameErr }}</div>

          <div
            class="input-group"
            :class="{ 'error-state': passwordErr, shake: passwordShake }"
          >
            <input
              ref="passwordInputRef"
              v-model="password"
              :type="isPasswordVisible ? 'text' : 'password'"
              placeholder=" "
              required
              @input="handlePasswordInput"
              @focus="updateStatus"
              @blur="updateStatusDelayed"
            >
            <label class="floating-label">密码</label>
            <button type="button" class="toggle-password" tabindex="-1" @mousedown.prevent @click="togglePassword">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="eye-icon">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
          </div>
          <div class="error-message" v-show="passwordErr">{{ passwordErr }}</div>

          <button type="submit" class="btn-primary" :disabled="authStore.isLoading || applySubmitting || applyRequestSent">
            {{ authStore.isLoading ? '正在验证…' : '进入控制室' }}
          </button>

          <!-- L4.85 申请+同意 模式: 申请登录按钮 (跟后端 L4.85 1:1 stable 永久规则化沿用) -->
          <button
            type="button"
            class="btn-apply"
            :disabled="authStore.isLoading || applySubmitting || applyRequestSent"
            @click="handleApply"
          >
            {{ applySubmitting ? '正在申请…' : applyRequestSent ? `已发送申请 (${applyRemainingSeconds}s)` : '申请接管当前会话' }}
          </button>

          <!-- L4.85 申请+同意 模式: 申请状态消息 -->
          <div v-if="applyMessage" class="apply-message" :class="applyMessageType">
            {{ applyMessage }}
          </div>
        </form>
      </div>
    </div>
  </div>

  <!-- 登录成功弹窗 -->
  <div class="success-overlay" :class="{ visible: showSuccess }">
    <div class="success-card">
      <div class="check-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>
      <h2>登录成功！</h2>
      <p>{{ successMsg }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import BrandMark from '@/components/BrandMark.vue'
import { useAuthStore } from '@/stores/auth'
import { claimLoginRequest, loginRequest, getLoginRequestStatus } from '@/api/loginRequest'

import { Rive, RuntimeLoader } from '@rive-app/canvas'

// Rive 默认从 CDN 拉 WASM；强制改为同源资源，兼容 fallback 也不得出站。
// 必须在创建首个 Rive 实例前设置，RuntimeLoader 是进程级单例。
RuntimeLoader.setWasmUrl('/riv/rive.wasm')
RuntimeLoader.setWasmFallbackUrl('/riv/rive_fallback.wasm')

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// === Template refs ===
const riveCanvasRef = ref<HTMLCanvasElement>()
const illustrationSectionRef = ref<HTMLDivElement>()
const usernameInputRef = ref<HTMLInputElement>()
const passwordInputRef = ref<HTMLInputElement>()

// === Reactive state ===
const username = ref('')
const password = ref('')
const usernameErr = ref('')
const passwordErr = ref('')
const usernameShake = ref(false)
const passwordShake = ref(false)
const showSuccess = ref(false)
const successMsg = ref('欢迎回来')
const isPasswordVisible = ref(false)

// === L4.85 申请+同意 模式: 申请状态 (跟后端 L4.85 1:1 stable 永久规则化沿用) ===
const applyRequestSent = ref(false)
const applyRequestExpiresAt = ref(0)  // 申请过期时间戳 (毫秒)
const applyRemainingSeconds = ref(0)  // 申请剩余秒数
const applyMessage = ref('')  // 申请状态消息
const applyMessageType = ref<'info' | 'success' | 'error'>('info')
const applySubmitting = ref(false)
let applyTimer: number | null = null
let applyStatusTimer: number | null = null
let applyStatusPollInFlight = false
let applyPollingDisposed = false
let applyRequestController: AbortController | null = null
let applyStatusController: AbortController | null = null

function stopApplyStatusPolling() {
  if (applyStatusTimer !== null) {
    window.clearTimeout(applyStatusTimer)
    applyStatusTimer = null
  }
  applyStatusController?.abort()
  applyStatusController = null
}

function scheduleApplyStatusPoll(requestId: string, user: string, claimToken: string) {
  stopApplyStatusPolling()
  if (applyPollingDisposed || !applyRequestSent.value) return
  applyStatusTimer = window.setTimeout(() => {
    applyStatusTimer = null
    void pollApplyStatus(requestId, user, claimToken)
  }, 5000)
}

// === L4.85 申请+同意 模式: 申请登录 (跟后端 L4.85 1:1 stable 永久规则化沿用) ===
async function handleApply() {
  if (applySubmitting.value || applyRequestSent.value || applyPollingDisposed) return
  const user = username.value.trim()
  const pwd = password.value
  if (!user || !pwd) {
    applyMessage.value = '请先输入账号和密码'
    applyMessageType.value = 'error'
    return
  }

  applyMessage.value = '正在发送申请...'
  applyMessageType.value = 'info'
  applySubmitting.value = true
  const controller = new AbortController()
  applyRequestController = controller

  try {
    const res = await loginRequest(user, pwd, controller.signal)
    if (applyPollingDisposed) return
    applyRequestSent.value = true
    // Sprint 205+ v3 (跟 handoff-upload-admin-v3 1:1 stable 永久规则化沿用):
    // 跟 backend/routers/login_request.py:44 LOGIN_REQUEST_TIMEOUT_SECONDS=180 1:1 stable
    // 修复 frontend 倒计时 300s (5min) vs backend 180s (3min) desync pre-existing bug
    // (跟 L4.85.5 5min→3min 全栈统一永久规则化沿用)
    applyRequestExpiresAt.value = Date.now() + 180 * 1000  // 3 分钟, 跟 LOGIN_REQUEST_TIMEOUT_SECONDS=180 1:1 stable 配套
    applyRemainingSeconds.value = 180
    applyMessage.value = res.message || `账号 ${user} 正在被使用, 已发送申请给当前用户, 请等待响应`
    applyMessageType.value = 'success'
    // 启动倒计时
    if (applyTimer) clearInterval(applyTimer)
    applyTimer = window.setInterval(() => {
      const remaining = Math.max(0, Math.floor((applyRequestExpiresAt.value - Date.now()) / 1000))
      applyRemainingSeconds.value = remaining
      if (remaining <= 0) {
        clearInterval(applyTimer!)
        applyTimer = null
        applyRequestSent.value = false
        stopApplyStatusPolling()
        applyMessage.value = '申请已超时, 请重新登录或重新申请'
        applyMessageType.value = 'error'
      }
    }, 1000)
    // L4.85.1 治本: B 端 polling 5s 检测自己申请状态 (跟后端 /login-request/{id}/status 1:1 stable 永久规则化沿用)
    // 跟 user 7/10 拍板 "admin 账号只允许 1 个人在线" 1:1 stable 配套
    scheduleApplyStatusPoll(res.request_id, user, res.claim_token)
  } catch (err: any) {
    if (applyPollingDisposed) return
    const detail = err?.data?.detail || err?.response?.data?.detail || err?.message || '申请失败'
    applyMessage.value = detail
    applyMessageType.value = 'error'
  } finally {
    if (applyRequestController === controller) applyRequestController = null
    applySubmitting.value = false
  }
}

// === L4.85.1 治本: B 端 polling 5s 检测自己申请状态 (跟后端 /login-request/{id}/status 1:1 stable 永久规则化沿用) ===
async function pollApplyStatus(requestId: string, username: string, claimToken: string) {
  if (applyPollingDisposed || !applyRequestSent.value || applyStatusPollInFlight) return
  applyStatusPollInFlight = true
  const controller = new AbortController()
  applyStatusController = controller
  try {
    const status = await getLoginRequestStatus(requestId, claimToken, controller.signal)
    if (applyPollingDisposed) return
    if (status.status === 'approved') {
      const claimed = await claimLoginRequest(requestId, claimToken, controller.signal)
      if (applyPollingDisposed) return
      if (applyTimer) { clearInterval(applyTimer); applyTimer = null }
      authStore.setSession(
        claimed.token,
        claimed.username || status.username || username,
        claimed.is_admin,
      )
      applyMessage.value = '申请已通过, 正在登录...'
      applyMessageType.value = 'success'
      applyRequestSent.value = false
      const redirect = route.query.redirect as string
      await router.replace(redirect || '/growth-board')
    } else if (status.status === 'rejected') {
      if (applyTimer) { clearInterval(applyTimer); applyTimer = null }
      applyRequestSent.value = false
      applyMessage.value = '申请被拒绝, 请联系当前用户或稍后重试'
      applyMessageType.value = 'error'
    } else if (status.status === 'expired') {
      if (applyTimer) { clearInterval(applyTimer); applyTimer = null }
      applyRequestSent.value = false
      applyMessage.value = '申请已超时, 请重新登录或重新申请'
      applyMessageType.value = 'error'
    }
  } catch (err: any) {
    if (applyPollingDisposed) return
    if (err?.status === 404 || err?.status === 410) {
      if (applyTimer) { clearInterval(applyTimer); applyTimer = null }
      applyRequestSent.value = false
      applyMessage.value = '登录授权已失效, 请重新申请'
      applyMessageType.value = 'error'
    }
  } finally {
    if (applyStatusController === controller) applyStatusController = null
    applyStatusPollInFlight = false
    if (!applyPollingDisposed && applyRequestSent.value) {
      scheduleApplyStatusPoll(requestId, username, claimToken)
    }
  }
}

// === Rive ===
let riveInstance: any = null
let statusInput: any = null
let correctTrigger: any = null
let wrongTrigger: any = null
let riveReady = false

function syncCanvasSize() {
  const canvas = riveCanvasRef.value
  if (!canvas) return { width: 0, height: 0 }
  const rect = canvas.parentElement!.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  const w = Math.max(1, Math.floor(rect.width * dpr))
  const h = Math.max(1, Math.floor(rect.height * dpr))
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w
    canvas.height = h
  }
  return { width: w, height: h }
}

function updateStatus() {
  if (!riveReady || !statusInput) return
  if (isPasswordVisible.value) {
    statusInput.value = 2
  } else if (
    document.activeElement === usernameInputRef.value ||
    document.activeElement === passwordInputRef.value
  ) {
    statusInput.value = 1
  } else {
    statusInput.value = 0
  }
}

function updateStatusDelayed() {
  setTimeout(updateStatus, 100)
}

function fireTrigger(t: any) {
  if (!riveReady || !t) return
  if (typeof t.trigger === 'function') { t.trigger() }
  else if (typeof t.fire === 'function') { t.fire() }
}

function handleUsernameInput() {
  usernameErr.value = ''
  usernameShake.value = false
  if (username.value.trim().length >= 3) {
    fireTrigger(correctTrigger)
  }
}

function handlePasswordInput() {
  passwordErr.value = ''
  passwordShake.value = false
  updateStatus()
}

function togglePassword() {
  isPasswordVisible.value = !isPasswordVisible.value
  updateStatus()
  const input = passwordInputRef.value
  if (input) {
    input.focus()
    setTimeout(() => input.setSelectionRange(input.value.length, input.value.length), 0)
  }
}

async function handleSubmit() {
  usernameErr.value = ''
  passwordErr.value = ''
  usernameShake.value = false
  passwordShake.value = false

  const user = username.value.trim()
  const pwd = password.value

  if (!user) {
    usernameErr.value = '请输入账号'
    usernameShake.value = true
    fireTrigger(wrongTrigger)
    usernameInputRef.value?.focus()
    return
  }

  if (!pwd) {
    passwordErr.value = '请输入密码'
    passwordShake.value = true
    fireTrigger(wrongTrigger)
    passwordInputRef.value?.focus()
    return
  }

  // === 调用后端登录接口 ===
  fireTrigger(correctTrigger)

  try {
    await authStore.login(user, pwd)
    successMsg.value = '欢迎回来，' + user + '！'
    showSuccess.value = true
    username.value = ''
    password.value = ''
    updateStatus()
    illustrationSectionRef.value?.classList.add('celebrating')
    setTimeout(() => illustrationSectionRef.value?.classList.remove('celebrating'), 600)
    // 自动跳转看板（无需点击"确认进入"）
    setTimeout(() => {
      showSuccess.value = false
      const redirect = route.query.redirect as string
      router.push(redirect || '/growth-board')
    }, 300)
  } catch (err: any) {
    // L4.85.2 治本: 普通 login 按钮也走申请+同意流程 (跟 user 7/10 拍板 1:1 stable 永久规则化沿用)
    // 跟 L4.85.1 B 端 polling 1:1 stable 永久规则化沿用, 跟 backend auth.py 409 1:1 stable 配套
    const status = err?.status ?? err?.response?.status
    const detail = err?.data?.detail ?? err?.response?.data?.detail ?? err?.message ?? ''
    if (status === 409 && detail.includes('正在被使用')) {
      await handleApply()  // 复用现有 申请+同意 流程 (5 分钟超时 + polling 5s)
      return
    }
    passwordErr.value = detail || '账号或密码错误'
    passwordShake.value = true
    fireTrigger(wrongTrigger)
    // L4.85.7 治本 Bug #1 真问题: fail path 清 input 字段, 防止 user 之前 input 残留
    // 跟 L4.85.5 plan-eng-review 缺陷 6 1:1 stable 永久规则化沿用 (fail path 不清 input 字段是真问题)
    // 配套 L4.85.6 Bug #2 治本 (Cmd+Q sendBeacon) 1:1 stable
    username.value = ''
    password.value = ''
  }
}

// === 鼠标跟随 ===
function onMouseMove(e: MouseEvent) {
  const canvas = riveCanvasRef.value
  if (!riveReady || !canvas) return

  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  const localX = (e.clientX - rect.left) * scaleX
  const localY = (e.clientY - rect.top) * scaleY

  if (localX >= 0 && localX <= canvas.width && localY >= 0 && localY <= canvas.height) {
    return
  }

  const centerX = canvas.width / 2
  const centerY = canvas.height / 2
  if (!scaleX || !scaleY || !window.innerWidth || !window.innerHeight) return

  const mappedX = centerX + (e.clientX / window.innerWidth - 0.5) * canvas.width * 0.6
  const mappedY = centerY + (e.clientY / window.innerHeight - 0.5) * canvas.height * 0.4

  canvas.dispatchEvent(new MouseEvent('mousemove', {
    clientX: rect.left + mappedX / scaleX,
    clientY: rect.top + mappedY / scaleY,
    bubbles: false
  }))
}

function onResize() {
  if (riveInstance) {
    syncCanvasSize()
    riveInstance.resizeDrawingSurfaceToCanvas()
  }
}

onMounted(() => {
  const canvas = riveCanvasRef.value
  if (!canvas) return
  syncCanvasSize()

  try {
    riveInstance = new Rive({
      src: '/riv/illustration.riv',
      canvas,
      stateMachines: 'State Machine 1',
      autoplay: true,
      autoBind: true,
      enableRiveAssetCDN: false,
      onLoad: () => {
        const doResize = () => {
          syncCanvasSize()
          riveInstance.resizeDrawingSurfaceToCanvas()
          const w = canvas.width
          const h = canvas.height
          if (w < 10 || h < 10) {
            setTimeout(doResize, 100)
            return
          }
          riveReady = true
        }
        doResize()

        const viewModel = riveInstance.viewModelByName('Login')
        if (viewModel) {
          const instance = viewModel.defaultInstance()
          riveInstance.bindViewModelInstance(instance)
          statusInput = instance.number('status')
          correctTrigger = instance.trigger('correct')
          wrongTrigger = instance.trigger('wrong')
        }
        updateStatus()
      },
      onLoadError: () => {
        riveReady = false
      },
    })
  } catch {
    // Rive 初始化异常 — 静默降级，不影响登录功能
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('resize', onResize)
  usernameInputRef.value?.focus()
})

onUnmounted(() => {
  applyPollingDisposed = true
  applyRequestSent.value = false
  applyRequestController?.abort()
  applyRequestController = null
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('resize', onResize)
  if (riveInstance) {
    riveInstance.cleanup()
  }
  // L4.85: 清理申请倒计时 timer
  if (applyTimer) clearInterval(applyTimer)
  stopApplyStatusPolling()
  // L4.85.7 治本 Bug #1: 删 L4.85.5 onUnmounted sessionStorage.removeItem (时机错误, 引发 "登录后没跳转" + "Cmd+Q token 丢失")
  // 跟 L4.42 + L4.50 + L4.85 + L4.85.4 + L4.85.6 1:1 stable 永久规则链配套
  // token 失效清理由 main.ts:20/50/67 + auth.ts:34-35 (clearSession) + NavBar:181 (idle timer) 6 处统一管理
  // 完整 handoff: docs/architecture/l4_85_7_bug1_handoff.md
})
</script>

<style scoped>
* { margin: 0; padding: 0; box-sizing: border-box; }

.login-container {
  display: flex;
  width: 100%;
  height: var(--sm-dimension-vh-100);
  overflow: hidden;
  color: var(--sm-ink);
  background: var(--sm-bg);
}

/* 左侧插画区 */
.illustration-section {
  flex: 1 1 50%;
  max-width: 62%;
  background: var(--sm-gradient-login-hero);
  position: relative;
  overflow: hidden;
}

.illustration-section canvas {
  width: 100%;
  height: 100%;
  display: block;
  opacity: .34;
  filter: saturate(.5) contrast(1.08);
}

.illustration-shade {
  position: absolute;
  inset: 0;
  background: var(--sm-gradient-login-shade);
  pointer-events: none;
}

.illustration-copy {
  position: absolute;
  z-index: 1;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: clamp(var(--sm-dimension-px-30), var(--sm-dimension-vw-4), var(--sm-dimension-px-62));
}

.illustration-copy > div > span,
.header-group > span {
  color: var(--sm-lilac);
  font: 650 var(--sm-dimension-px-9)/1 var(--sm-font-display);
  letter-spacing: var(--sm-dimension-em-0-16);
}

.illustration-copy h1 {
  max-width: var(--sm-dimension-px-760);
  margin: var(--sm-dimension-px-18) 0 var(--sm-dimension-px-20);
  color: var(--sm-ink);
  font-family: var(--sm-font-display);
  font-size: clamp(var(--sm-dimension-px-38), var(--sm-dimension-vw-5), var(--sm-dimension-px-76));
  font-weight: 570;
  letter-spacing: var(--sm-dimension-em-minus-0-06);
  line-height: .98;
}

.illustration-copy > div > p { max-width: var(--sm-dimension-px-630); color: var(--sm-copy); font-size: var(--sm-dimension-px-14); line-height: 1.8; }
.illustration-copy ol { display: flex; gap: var(--sm-dimension-px-28); list-style: none; }
.illustration-copy li { display: flex; align-items: center; gap: var(--sm-dimension-px-10); color: var(--sm-copy-strong); font-size: var(--sm-dimension-px-11); }
.illustration-copy li > i { color: var(--sm-signal); font: 650 var(--sm-dimension-px-9)/1 var(--sm-font-display); }
.illustration-copy li > span { display: grid; gap: var(--sm-dimension-px-3); }
.illustration-copy li small { color: var(--sm-faint); font: 600 var(--sm-dimension-px-7)/1 var(--sm-font-display); letter-spacing: var(--sm-dimension-em-0-08); }

/* 角色庆祝动画 — 登录成功时触发 */
.illustration-section.celebrating {
  animation: sectionCelebrate 600ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes sectionCelebrate {
  0%   { transform: scale(1); }
  50%  { transform: scale(1.02); }
  100% { transform: scale(1); }
}

/* 右侧表单区 */
.form-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--sm-dimension-px-40) clamp(var(--sm-dimension-px-28), var(--sm-dimension-vw-5), var(--sm-dimension-px-78));
  background: var(--sm-gradient-login-panel);
}

.form-wrapper {
  width: 100%;
  max-width: var(--sm-dimension-px-420);
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.header-group {
  text-align: left;
  margin-bottom: var(--sm-dimension-px-38);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.mobile-brand { display: none; margin-bottom: var(--sm-dimension-px-44); }

.welcome-title {
  margin: var(--sm-dimension-px-13) 0 var(--sm-dimension-px-10);
  color: var(--sm-ink);
  font-family: var(--sm-font-display);
  font-size: var(--sm-dimension-px-34);
  font-weight: 580;
  letter-spacing: var(--sm-dimension-em-minus-0-04);
}

.subtitle {
  color: var(--sm-muted);
  font-size: var(--sm-dimension-px-12);
  font-weight: 450;
}

.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--sm-dimension-px-12);
}

.input-group {
  position: relative;
  width: 100%;
  height: var(--sm-dimension-px-64);
  border-bottom: var(--sm-dimension-px-1) solid var(--sm-line-strong);
  display: flex;
  align-items: flex-end;
}

.input-group input {
  width: 100%;
  height: var(--sm-dimension-px-40);
  padding-bottom: var(--sm-dimension-px-8);
  border: none;
  outline: none;
  font-size: var(--sm-dimension-px-16);
  font-weight: 500;
  color: var(--sm-ink);
  background: transparent;
  padding-right: var(--sm-dimension-px-40);
  position: relative;
  z-index: 1;
}

.input-group input:-webkit-autofill,
.input-group input:-webkit-autofill:hover,
.input-group input:-webkit-autofill:focus,
.input-group input:-webkit-autofill:active {
  -webkit-box-shadow: 0 0 0 var(--sm-dimension-px-30) var(--sm-bg-bottom) inset !important;
  -webkit-text-fill-color: var(--sm-ink) !important;
}

.input-group input::placeholder { color: transparent; }

.floating-label {
  position: absolute;
  left: 0; bottom: var(--sm-dimension-px-14);
  font-size: var(--sm-dimension-px-16);
  color: var(--sm-muted);
  pointer-events: none;
  transition: all 0.2s ease-out;
  font-weight: 500;
  z-index: 0;
}

.input-group input:focus ~ .floating-label,
.input-group input:not(:placeholder-shown) ~ .floating-label {
  bottom: var(--sm-dimension-px-42);
  font-size: var(--sm-dimension-px-12);
  color: var(--sm-lilac);
}

/* 错误状态 */
.input-group.error-state { border-bottom-color: var(--sm-danger); }
.input-group.error-state .floating-label { color: var(--sm-danger) !important; }
.shake { animation: shake 0.4s ease-in-out; }
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(var(--sm-dimension-px-minus-6)); }
  50% { transform: translateX(var(--sm-dimension-px-6)); }
  75% { transform: translateX(var(--sm-dimension-px-minus-6)); }
}

.toggle-password {
  position: absolute;
  right: 0; bottom: var(--sm-dimension-px-4);
  background: none; border: none;
  cursor: pointer; color: var(--sm-lilac);
  display: flex; align-items: center; justify-content: center;
  padding: var(--sm-dimension-px-8); z-index: 2;
}
.eye-icon { width: var(--sm-dimension-px-24); height: var(--sm-dimension-px-24); pointer-events: none; }

.btn-primary {
  width: 100%; height: var(--sm-dimension-px-48);
  background-color: var(--sm-signal); color: var(--sm-on-accent);
  border: var(--sm-dimension-px-1) solid var(--sm-line-accent-strong); border-radius: var(--sm-radius-control);
  font-size: var(--sm-dimension-px-16); font-weight: 500;
  cursor: pointer; margin-top: var(--sm-dimension-px-24);
  transition: background-color 0.2s;
  font-family: inherit;
}
.btn-primary:hover { background-color: var(--sm-ink); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

/* L4.85 申请+同意 模式: 申请登录按钮 (跟后端 L4.85 1:1 stable 永久规则化沿用) */
.btn-apply {
  width: 100%; height: var(--sm-dimension-px-48);
  background-color: var(--sm-white-faint); color: var(--sm-copy);
  border: var(--sm-dimension-px-1) solid var(--sm-line-strong); border-radius: var(--sm-radius-control);
  font-size: var(--sm-dimension-px-16); font-weight: 500;
  cursor: pointer; margin-top: var(--sm-dimension-px-12);
  transition: background-color 0.2s, color 0.2s;
  font-family: inherit;
}
.btn-apply:hover { border-color: var(--sm-lilac); color: var(--sm-ink); background-color: var(--sm-purple-soft); }
.btn-apply:disabled { opacity: 0.6; cursor: not-allowed; }

/* L4.85 申请状态消息 */
.apply-message {
  font-size: var(--sm-dimension-px-13);
  margin-top: var(--sm-dimension-px-12);
  padding: var(--sm-dimension-px-8) var(--sm-dimension-px-12);
  border-radius: var(--sm-radius-soft);
  text-align: center;
}
.apply-message.info { color: var(--sm-lilac); background-color: var(--sm-purple-soft); }
.apply-message.success { color: var(--sm-signal); background-color: var(--sm-signal-soft); }
.apply-message.error { color: var(--sm-danger); background-color: var(--sm-danger-soft); }

/* 错误消息 */
.error-message {
  display: none;
  font-size: var(--sm-dimension-px-12);
  color: var(--sm-danger);
  margin-top: var(--sm-dimension-px-4);
  padding-left: var(--sm-dimension-px-2);
}
.error-message:not(:empty) { display: block; }

/* ====== 登录成功弹窗 ====== */
.success-overlay {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: var(--sm-overlay);
  backdrop-filter: var(--sm-blur-overlay);
  z-index: 9999;
  align-items: center;
  justify-content: center;
}
.success-overlay.visible { display: flex; }

.success-card {
  color: var(--sm-ink);
  background: var(--sm-glass-strong);
  border: var(--sm-dimension-px-1) solid var(--sm-line-strong);
  border-radius: var(--sm-radius-panel);
  padding: var(--sm-dimension-px-48) var(--sm-dimension-px-40);
  text-align: center;
  max-width: var(--sm-dimension-px-380);
  width: 90%;
  box-shadow: var(--sm-shadow-panel);
  animation: popIn 500ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes popIn {
  0%   { transform: scale(0.5) translateY(var(--sm-dimension-px-40)); opacity: 0; }
  100% { transform: scale(1) translateY(0); opacity: 1; }
}

.success-card .check-icon {
  width: var(--sm-dimension-px-64); height: var(--sm-dimension-px-64);
  border-radius: 50%;
  background: var(--sm-signal);
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto var(--sm-dimension-px-20);
}
.success-card .check-icon svg { width: var(--sm-dimension-px-32); height: var(--sm-dimension-px-32); color: var(--sm-on-accent); }
.success-card h2 { font-size: var(--sm-dimension-px-22); font-weight: 700; color: var(--sm-ink); margin-bottom: var(--sm-dimension-px-8); }
.success-card p { font-size: var(--sm-dimension-px-14); color: var(--sm-muted); }

/* 响应式 */
@media (max-width: 900px) {
  .illustration-section { display: none; }
  .form-section { padding: var(--sm-dimension-px-60) var(--sm-dimension-px-20); }
  .mobile-brand { display: inline-flex; }
}
</style>
