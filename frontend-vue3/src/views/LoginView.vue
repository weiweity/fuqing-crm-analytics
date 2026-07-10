<template>
  <div class="login-container">
    <!-- 左侧 Rive 动画 -->
    <div class="illustration-section" ref="illustrationSectionRef">
      <canvas ref="riveCanvasRef"></canvas>
    </div>

    <!-- 右侧表单 -->
    <div class="form-section">
      <div class="form-wrapper">
        <div class="header-group">
          <img src="/svg/logo.svg" alt="Logo" class="logo-icon">
          <h1 class="welcome-title">欢迎回来！</h1>
          <p class="subtitle">请输入您的账号和密码</p>
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

          <button type="submit" class="btn-primary" :disabled="authStore.isLoading || applyRequestSent">
            {{ authStore.isLoading ? '登录中...' : '登 录' }}
          </button>

          <!-- L4.85 申请+同意 模式: 申请登录按钮 (跟后端 L4.85 1:1 stable 永久规则化沿用) -->
          <button
            type="button"
            class="btn-apply"
            :disabled="authStore.isLoading || applyRequestSent"
            @click="handleApply"
          >
            {{ applyRequestSent ? `已发送申请 (${applyRemainingSeconds}s)` : '申请登录' }}
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
import { useAuthStore } from '@/stores/auth'
import { loginRequest, getLoginRequestStatus } from '@/api/loginRequest'

// Rive npm 包是 UMD 构建，Vite 的 commonjs 插件会自动转换，
// 但为了保险仍做一层类型探测
import RiveModule from '@rive-app/canvas'
const Rive: any = typeof RiveModule === 'function'
  ? RiveModule
  : (RiveModule as any)?.default || (RiveModule as any)?.Rive || Object.values(RiveModule as any).find((v: any) => typeof v === 'function')

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
let applyTimer: number | null = null

// === L4.85 申请+同意 模式: 申请登录 (跟后端 L4.85 1:1 stable 永久规则化沿用) ===
async function handleApply() {
  const user = username.value.trim()
  const pwd = password.value
  if (!user || !pwd) {
    applyMessage.value = '请先输入账号和密码'
    applyMessageType.value = 'error'
    return
  }

  applyMessage.value = '正在发送申请...'
  applyMessageType.value = 'info'

  try {
    const res = await loginRequest(user, pwd)
    applyRequestSent.value = true
    applyRequestExpiresAt.value = Date.now() + 300 * 1000  // 5 分钟, 跟 L4.85 LOGIN_REQUEST_TIMEOUT_SECONDS 1:1 stable 配套
    applyRemainingSeconds.value = 300
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
        applyMessage.value = '申请已超时, 请重新登录或重新申请'
        applyMessageType.value = 'error'
      }
    }, 1000)
    // L4.85.1 治本: B 端 polling 5s 检测自己申请状态 (跟后端 /login-request/{id}/status 1:1 stable 永久规则化沿用)
    // 跟 user 7/10 拍板 "admin 账号只允许 1 个人在线" 1:1 stable 配套
    pollApplyStatus(res.request_id, user)
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || '申请失败'
    applyMessage.value = detail
    applyMessageType.value = 'error'
  }
}

// === L4.85.1 治本: B 端 polling 5s 检测自己申请状态 (跟后端 /login-request/{id}/status 1:1 stable 永久规则化沿用) ===
async function pollApplyStatus(requestId: string, username: string) {
  const pollTimer = window.setInterval(async () => {
    if (!applyRequestSent.value) {
      window.clearInterval(pollTimer)
      return
    }
    try {
      const status = await getLoginRequestStatus(requestId)
      if (status.status === 'approved' && status.new_token) {
        // 申请已通过: 写入 sessionStorage + 跳 dashboard
        window.clearInterval(pollTimer)
        if (applyTimer) { clearInterval(applyTimer); applyTimer = null }
        sessionStorage.setItem('fq_crm_auth_token', status.new_token)
        sessionStorage.setItem('fq_crm_auth_user', status.username || username)
        applyMessage.value = '申请已通过, 正在登录...'
        applyMessageType.value = 'success'
        applyRequestSent.value = false
        setTimeout(() => {
          const redirect = route.query.redirect as string
          router.push(redirect || '/audience')
        }, 800)
      } else if (status.status === 'rejected') {
        window.clearInterval(pollTimer)
        if (applyTimer) { clearInterval(applyTimer); applyTimer = null }
        applyRequestSent.value = false
        applyMessage.value = '申请被拒绝, 请联系当前用户或稍后重试'
        applyMessageType.value = 'error'
      } else if (status.status === 'expired') {
        window.clearInterval(pollTimer)
        if (applyTimer) { clearInterval(applyTimer); applyTimer = null }
        applyRequestSent.value = false
        applyMessage.value = '申请已超时, 请重新登录或重新申请'
        applyMessageType.value = 'error'
      }
    } catch (err) {
      // 静默: 401/网络异常等下次 polling
    }
  }, 5000)
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
      router.push(redirect || '/audience')
    }, 300)
  } catch (err: any) {
    passwordErr.value = err.message || '账号或密码错误'
    passwordShake.value = true
    fireTrigger(wrongTrigger)
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
      onError: () => {
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
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('resize', onResize)
  if (riveInstance) {
    riveInstance.cleanup()
  }
  // L4.85: 清理申请倒计时 timer
  if (applyTimer) clearInterval(applyTimer)
})
</script>

<style scoped>
* { margin: 0; padding: 0; box-sizing: border-box; }

.login-container {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

/* 左侧插画区 */
.illustration-section {
  flex: 1 1 50%;
  max-width: 60%;
  background-color: #E7E3E6;
  position: relative;
  overflow: hidden;
}

.illustration-section canvas {
  width: 100%;
  height: 100%;
  display: block;
}

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
  padding: 40px;
  background-color: #FFFFFF;
}

.form-wrapper {
  width: 100%;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.header-group {
  text-align: center;
  margin-bottom: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.logo-icon { width: 48px; height: auto; margin-bottom: 24px; }

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: #15161A;
  margin-bottom: 12px;
}

.subtitle {
  font-size: 14px;
  color: #666666;
  font-weight: 500;
}

.login-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-group {
  position: relative;
  width: 100%;
  height: 64px;
  border-bottom: 1px solid #000000;
  display: flex;
  align-items: flex-end;
}

.input-group input {
  width: 100%;
  height: 40px;
  padding-bottom: 8px;
  border: none;
  outline: none;
  font-size: 16px;
  font-weight: 500;
  color: #000000;
  background: transparent;
  padding-right: 40px;
  position: relative;
  z-index: 1;
}

.input-group input:-webkit-autofill,
.input-group input:-webkit-autofill:hover,
.input-group input:-webkit-autofill:focus,
.input-group input:-webkit-autofill:active {
  -webkit-box-shadow: 0 0 0 30px white inset !important;
  -webkit-text-fill-color: #000000 !important;
}

.input-group input::placeholder { color: transparent; }

.floating-label {
  position: absolute;
  left: 0; bottom: 14px;
  font-size: 16px;
  color: #000000;
  pointer-events: none;
  transition: all 0.2s ease-out;
  font-weight: 500;
  z-index: 0;
}

.input-group input:focus ~ .floating-label,
.input-group input:not(:placeholder-shown) ~ .floating-label {
  bottom: 42px;
  font-size: 12px;
  color: #666666;
}

/* 错误状态 */
.input-group.error-state { border-bottom-color: #8B0000; }
.input-group.error-state .floating-label { color: #8B0000 !important; }
.shake { animation: shake 0.4s ease-in-out; }
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-6px); }
  50% { transform: translateX(6px); }
  75% { transform: translateX(-6px); }
}

.toggle-password {
  position: absolute;
  right: 0; bottom: 4px;
  background: none; border: none;
  cursor: pointer; color: #000000;
  display: flex; align-items: center; justify-content: center;
  padding: 8px; z-index: 2;
}
.eye-icon { width: 24px; height: 24px; pointer-events: none; }

.btn-primary {
  width: 100%; height: 48px;
  background-color: #15161A; color: #FFFFFF;
  border: none; border-radius: 999px;
  font-size: 16px; font-weight: 500;
  cursor: pointer; margin-top: 24px;
  transition: background-color 0.2s;
  font-family: inherit;
}
.btn-primary:hover { background-color: #2D2E33; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

/* L4.85 申请+同意 模式: 申请登录按钮 (跟后端 L4.85 1:1 stable 永久规则化沿用) */
.btn-apply {
  width: 100%; height: 48px;
  background-color: #FFFFFF; color: #15161A;
  border: 1px solid #15161A; border-radius: 999px;
  font-size: 16px; font-weight: 500;
  cursor: pointer; margin-top: 12px;
  transition: background-color 0.2s, color 0.2s;
  font-family: inherit;
}
.btn-apply:hover { background-color: #15161A; color: #FFFFFF; }
.btn-apply:disabled { opacity: 0.6; cursor: not-allowed; }

/* L4.85 申请状态消息 */
.apply-message {
  font-size: 13px;
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  text-align: center;
}
.apply-message.info { color: #1e40af; background-color: #dbeafe; }
.apply-message.success { color: #16a34a; background-color: #dcfce7; }
.apply-message.error { color: #8b0000; background-color: #fee2e2; }

/* 错误消息 */
.error-message {
  display: none;
  font-size: 12px;
  color: #8B0000;
  margin-top: 4px;
  padding-left: 2px;
}
.error-message:not(:empty) { display: block; }

/* ====== 登录成功弹窗 ====== */
.success-overlay {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.45);
  z-index: 9999;
  align-items: center;
  justify-content: center;
}
.success-overlay.visible { display: flex; }

.success-card {
  background: #FFFFFF;
  border-radius: 20px;
  padding: 48px 40px;
  text-align: center;
  max-width: 380px;
  width: 90%;
  box-shadow: 0 24px 64px rgba(0,0,0,0.15);
  animation: popIn 500ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes popIn {
  0%   { transform: scale(0.5) translateY(40px); opacity: 0; }
  100% { transform: scale(1) translateY(0); opacity: 1; }
}

.success-card .check-icon {
  width: 64px; height: 64px;
  border-radius: 50%;
  background: #ECFDF5;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 20px;
}
.success-card .check-icon svg { width: 32px; height: 32px; color: #16A34A; }
.success-card h2 { font-size: 22px; font-weight: 700; color: #15161A; margin-bottom: 8px; }
.success-card p { font-size: 14px; color: #666666; }

/* 响应式 */
@media (max-width: 900px) {
  .illustration-section { display: none; }
  .form-section { padding: 60px 20px; }
}
</style>
