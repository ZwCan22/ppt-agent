<script setup lang="ts">
import { ref } from 'vue'
import AppIcon from './AppIcon.vue'
import type { LoginInput } from '../types/auth'

defineProps<{ busy: boolean; error: string; notice: string }>()
const emit = defineEmits<{ submit: [input: LoginInput] }>()
const username = ref('')
const password = ref('')
function submit() {
  emit('submit', { username: username.value, password: password.value })
  password.value = ''
}
</script>

<template>
  <main class="auth-main">
    <section class="auth-intro" aria-labelledby="welcome-title">
      <p class="eyebrow"><span></span> 欢迎来到 PPT Studio</p>
      <h1 id="welcome-title">让好想法，<br /><span>成为一份好演示。</span></h1>
      <p class="intro-copy">登录你的工作台，从一个主题开始，<br />把内容整理、制作与交付连接起来。</p>
      <ul class="intro-features">
        <li><AppIcon name="check" :size="17" /> 描述需求，自动生成可编辑的 PPT</li>
        <li><AppIcon name="check" :size="17" /> 随时查看制作进度与历史任务</li>
        <li><AppIcon name="check" :size="17" /> 在自己的账号中管理和下载演示文稿</li>
      </ul>
      <div class="intro-deck" aria-hidden="true">
        <AppIcon name="slides" :size="30" />
        <div><strong>YOUR NEXT BIG IDEA.</strong><span>从想法，到清晰表达。</span></div>
      </div>
    </section>
    <section class="surface auth-card" aria-labelledby="login-title">
      <p class="section-kicker">YOUR WORKSPACE</p>
      <h2 id="login-title">登录工作台</h2>
      <p class="panel-description">使用已注册的账号，继续你的演示创作。</p>
      <p v-if="notice" class="auth-notice" role="status">{{ notice }}</p>
      <form @submit.prevent="submit">
        <fieldset :disabled="busy">
          <div class="field">
            <label for="login-username">用户名</label>
            <input id="login-username" v-model="username" name="username" type="text"
              autocomplete="username" autocapitalize="none" :spellcheck="false"
              required minlength="3" maxlength="32" pattern="[a-z0-9_]{3,32}"
              placeholder="请输入用户名" aria-describedby="username-hint" />
            <p id="username-hint" class="field-hint">3～32 位小写英文字母、数字或下划线</p>
          </div>
          <div class="field">
            <label for="login-password">密码</label>
            <input id="login-password" v-model="password" name="password" type="password"
              autocomplete="current-password" required maxlength="128" placeholder="请输入密码" />
          </div>
          <button class="primary-button" type="submit">
            <AppIcon v-if="busy" name="loader" class="spin" :size="18" />
            {{ busy ? '正在登录…' : '登录工作台' }}
          </button>
        </fieldset>
      </form>
      <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
      <p class="login-help">首次使用？请先通过后端注册接口创建账号。</p>
    </section>
  </main>
</template>

<style scoped>
.auth-main { max-width: 1120px; min-height: calc(100vh - 77px); padding: 64px 32px; margin: auto; display: grid; grid-template-columns: 1.1fr 1fr; align-items: center; gap: 80px; }
.auth-intro h1 { font-size: clamp(32px, 4vw, 46px); line-height: 1.4; }
.intro-copy { margin-top: 20px; color: var(--muted); line-height: 1.9; }
.intro-features { list-style: none; padding: 0; margin: 28px 0; display: grid; gap: 12px; color: #637083; font-size: 13px; }
.intro-features li { display: flex; align-items: center; gap: 10px; }
.intro-features svg { color: #668f7a; }
.intro-deck { padding: 22px; max-width: 350px; display: flex; align-items: center; gap: 16px; color: #edf2ff; border-radius: 12px; background: #183153; box-shadow: 0 12px 30px #18315312; }
.intro-deck strong, .intro-deck span { display: block; }
.intro-deck strong { font-size: 13px; letter-spacing: 1px; }
.intro-deck span { color: #b4c3d9; font-size: 11px; margin-top: 4px; }
.auth-card { padding: 36px; }
.auth-card h2 { font-size: 25px; margin-top: 5px; }
.auth-card fieldset { gap: 22px; }
.auth-card .primary-button > svg:first-child { margin-right: 0; }
.auth-notice { padding: 12px 14px; background: #f0f4ff; color: #526ba4; border-radius: 8px; margin-bottom: 20px; font-size: 12px; }
.login-help { color: var(--muted); font-size: 11px; margin-top: 22px; line-height: 1.8; }
@media (max-width: 800px) { .auth-main { gap: 32px; padding: 36px 24px; grid-template-columns: 1fr; max-width: 540px; } .auth-intro { text-align: center; } .auth-intro .eyebrow { justify-content: center; } .intro-features, .intro-deck, .intro-copy { display: none; } .auth-intro h1 { font-size: 31px; } .auth-intro h1 br { display: none; } .auth-card { padding: 28px; } }
@media (max-width: 420px) { .auth-main { padding: 28px 16px; gap: 24px; } .auth-card { padding: 24px 20px; } .auth-intro h1 { font-size: 27px; } }
</style>
