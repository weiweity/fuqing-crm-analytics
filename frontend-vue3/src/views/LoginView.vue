<template>
  <div class="login-container">
    <div class="form-section">
      <div class="form-wrapper">
        <div class="header-group">
          <BrandMark />
          <h2 class="welcome-title">进入增长董事会</h2>
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
              @input="usernameErr = ''; usernameShake = false"
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
              @input="passwordErr = ''; passwordShake = false"
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

          <button type="submit" class="btn-primary" :disabled="authStore.isLoading">
            {{ authStore.isLoading ? '正在验证…' : '进入' }}
          </button>
        </form>
      </div>
    </div>
  </div>

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
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BrandMark from '@/components/BrandMark.vue'
import { useAuthStore } from '@/stores/auth'
import type { ApiError } from '@/api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const usernameInputRef = ref<HTMLInputElement>()
const passwordInputRef = ref<HTMLInputElement>()
const username = ref('')
const password = ref('')
const usernameErr = ref('')
const passwordErr = ref('')
const usernameShake = ref(false)
const passwordShake = ref(false)
const showSuccess = ref(false)
const successMsg = ref('欢迎回来')
const isPasswordVisible = ref(false)

function togglePassword() {
  isPasswordVisible.value = !isPasswordVisible.value
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
    usernameInputRef.value?.focus()
    return
  }
  if (!pwd) {
    passwordErr.value = '请输入密码'
    passwordShake.value = true
    passwordInputRef.value?.focus()
    return
  }

  try {
    await authStore.login(user, pwd)
    successMsg.value = '欢迎回来，' + user + '！'
    showSuccess.value = true
    username.value = ''
    password.value = ''
    setTimeout(() => {
      showSuccess.value = false
      const redirect = route.query.redirect as string
      router.push(redirect || '/audience')
    }, 300)
  } catch (err: unknown) {
    const apiErr = err as ApiError
    const detail = apiErr.data && typeof apiErr.data === 'object' && 'detail' in apiErr.data
      ? String((apiErr.data as { detail?: unknown }).detail ?? '')
      : ''
    passwordErr.value = detail || apiErr.message || '账号或密码错误'
    passwordShake.value = true
    username.value = ''
    password.value = ''
  }
}

onMounted(() => {
  usernameInputRef.value?.focus()
})
</script>

<style scoped>
.login-container {
  display: grid;
  place-items: center;
  width: 100%;
  min-height: var(--sm-dimension-vh-100);
  color: var(--sm-ink);
  background: var(--sm-bg);
}

.form-section {
  width: min(var(--sm-dimension-px-420), calc(100% - var(--sm-dimension-px-40)));
  padding: var(--sm-dimension-px-40) var(--sm-dimension-px-28);
}

.form-wrapper {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.header-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: var(--sm-dimension-px-38);
}

.welcome-title {
  margin: var(--sm-dimension-px-16) 0 0;
  color: var(--sm-ink);
  font-family: var(--sm-font-display);
  font-size: var(--sm-dimension-px-28);
  font-weight: 580;
  letter-spacing: var(--sm-dimension-em-minus-0-04);
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
  padding-right: var(--sm-dimension-px-40);
  border: none;
  outline: none;
  font-size: var(--sm-dimension-px-16);
  font-weight: 500;
  color: var(--sm-ink);
  background: transparent;
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
  left: 0;
  bottom: var(--sm-dimension-px-14);
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
  right: 0;
  bottom: var(--sm-dimension-px-4);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--sm-lilac);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sm-dimension-px-8);
  z-index: 2;
}
.eye-icon { width: var(--sm-dimension-px-24); height: var(--sm-dimension-px-24); pointer-events: none; }

.btn-primary {
  width: 100%;
  height: var(--sm-dimension-px-48);
  background-color: var(--sm-signal);
  color: var(--sm-on-accent);
  border: var(--sm-dimension-px-1) solid var(--sm-line-accent-strong);
  border-radius: var(--sm-radius-control);
  font-size: var(--sm-dimension-px-16);
  font-weight: 500;
  cursor: pointer;
  margin-top: var(--sm-dimension-px-24);
  font-family: inherit;
}
.btn-primary:hover { background-color: var(--sm-ink); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.error-message {
  font-size: var(--sm-dimension-px-12);
  color: var(--sm-danger);
  margin-top: var(--sm-dimension-px-4);
}

.success-overlay {
  display: none;
  position: fixed;
  inset: 0;
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
}

.success-card .check-icon {
  width: var(--sm-dimension-px-64);
  height: var(--sm-dimension-px-64);
  border-radius: 50%;
  background: var(--sm-signal);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--sm-dimension-px-20);
}
.success-card .check-icon svg { width: var(--sm-dimension-px-32); height: var(--sm-dimension-px-32); color: var(--sm-on-accent); }
.success-card h2 { font-size: var(--sm-dimension-px-22); font-weight: 700; color: var(--sm-ink); margin-bottom: var(--sm-dimension-px-8); }
.success-card p { font-size: var(--sm-dimension-px-14); color: var(--sm-muted); }
</style>
