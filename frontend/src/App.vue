<script setup lang="ts">
import AppIcon from './components/AppIcon.vue'
import LoginPanel from './components/LoginPanel.vue'
import PptWorkspace from './components/PptWorkspace.vue'
import { useAuth } from './composables/useAuth'

const { user, state, busy, error, notice, login, logout, restoreSession, expireSession } = useAuth()
</script>

<template>
  <div class="studio-shell">
    <header class="site-header">
      <div class="header-inner">
        <a class="brand" href="/" aria-label="PPT 智能助手首页">
          <span class="brand-mark"><AppIcon name="slides" :size="24" /></span>
          <span class="brand-name">PPT<span>Studio</span></span>
        </a>
        <span class="header-divider" aria-hidden="true"></span>
        <span class="header-location">{{ state === 'authenticated' ? '创作工作台' : '账号登录' }}</span>
        <div v-if="state === 'authenticated' && user" class="account-controls">
          <span class="account-name" :title="user.username">{{ user.username }}</span>
          <button type="button" class="logout-button" :disabled="busy" @click="logout">{{ busy ? '正在退出…' : '退出登录' }}</button>
        </div>
        <span v-else class="format-badge"><AppIcon name="file" :size="15" /> 可编辑 PPTX</span>
      </div>
    </header>
    <div v-if="state === 'checking'" class="session-state" role="status" aria-live="polite">
      <AppIcon name="loader" class="spin" :size="26" />
      <h1>正在确认登录状态</h1><p>请稍候，即将进入你的工作台。</p>
    </div>
    <div v-else-if="state === 'unavailable'" class="session-state" role="alert">
      <h1>暂时无法连接工作台</h1><p>{{ error }}</p>
      <button class="primary-button retry-button" type="button" :disabled="busy" @click="restoreSession">重新连接</button>
    </div>
    <template v-else-if="state === 'authenticated' && user">
      <p v-if="error" class="notice notice-error account-error" role="alert">{{ error }}</p>
      <PptWorkspace :key="user.id" :user="user" :inert="busy || undefined" :aria-busy="busy" @session-expired="expireSession" />
    </template>
    <LoginPanel v-else :busy="busy" :error="error" :notice="notice" @submit="login" />
  </div>
</template>

<style scoped>
.account-controls { margin-left: auto; display: flex; align-items: center; gap: 16px; min-width: 0; }
.account-name { max-width: 180px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; color: #64717f; font-size: 13px; }
.logout-button { border: 1px solid var(--border); background: white; border-radius: 8px; padding: 7px 12px; color: #52627a; font-size: 12px; flex-shrink: 0; }
.logout-button:hover:not(:disabled) { background: #f4f6fb; border-color: #cbd5e5; }
.session-state { max-width: 560px; padding: 80px 24px; margin: auto; text-align: center; color: var(--muted); }
.session-state > svg { color: var(--blue); margin-bottom: 18px; }
.session-state h1 { font-size: 23px; color: #303b4d; margin-bottom: 12px; }
.session-state p { font-size: 13px; }
.retry-button { max-width: 180px; margin: 24px auto 0; }
.account-error { max-width: 1136px; margin: 20px auto 0; }
@media (max-width: 600px) { .account-controls { gap: 8px; } .account-name { max-width: 100px; font-size: 11px; } .logout-button { padding: 6px 9px; font-size: 11px; } .header-inner { gap: 10px; } .account-error { margin: 16px; } }
</style>
