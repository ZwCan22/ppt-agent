import { onMounted, onUnmounted, ref } from 'vue'
import { getCurrentUser, login as requestLogin, logout as requestLogout } from '../api/auth'
import { ApiError } from '../api/http'
import type { LoginInput, UserPublic } from '../types/auth'

type AuthState = 'checking' | 'authenticated' | 'anonymous' | 'unavailable'

export function useAuth() {
  const user = ref<UserPublic | null>(null)
  const state = ref<AuthState>('checking')
  const busy = ref(false)
  const error = ref('')
  const notice = ref('')
  let generation = 0
  let disposed = false
  let controller: AbortController | undefined
  let channel: BroadcastChannel | undefined
  let recheckPending = false

  function expireSession() {
    generation += 1
    controller?.abort()
    controller = undefined
    user.value = null
    state.value = 'anonymous'
    busy.value = false
    recheckPending = false
    error.value = ''
    notice.value = '登录已过期，请重新登录。'
  }

  async function run(mode: 'restore' | 'login' | 'logout', input?: LoginInput) {
    if (disposed || busy.value) return
    const current = ++generation
    const request = new AbortController()
    controller = request
    busy.value = true
    error.value = ''
    const hadUser = state.value === 'authenticated' && user.value !== null
    if (mode === 'restore' && !hadUser) {
      state.value = 'checking'
      user.value = null
    }
    const timeout = window.setTimeout(() => request.abort(), 10_000)
    try {
      if (mode === 'logout') {
        await requestLogout(request.signal)
        if (disposed || current !== generation) return
        user.value = null
        state.value = 'anonymous'
        notice.value = '已退出登录，后台制作任务会继续运行。'
      } else {
        const result = mode === 'restore'
          ? await getCurrentUser(request.signal)
          : await requestLogin(input!, request.signal)
        if (disposed || current !== generation) return
        user.value = result
        state.value = 'authenticated'
        notice.value = ''
      }
      if (mode !== 'restore') {
        try { channel?.postMessage('session-changed') } catch { /* Best-effort tab sync. */ }
      }
    } catch (cause: unknown) {
      if (disposed || current !== generation) return
      if (mode === 'restore' && cause instanceof ApiError && cause.status === 401) {
        user.value = null
        state.value = 'anonymous'
      } else {
        if (mode === 'restore' && !hadUser) state.value = 'unavailable'
        if (mode === 'login') state.value = 'anonymous'
        error.value = request.signal.aborted ? '请求超时，请重试。'
          : cause instanceof TypeError ? '暂时无法连接服务，请检查后端是否启动。'
            : cause instanceof Error ? cause.message : '操作失败，请重试。'
      }
    } finally {
      window.clearTimeout(timeout)
      if (!disposed && current === generation) {
        controller = undefined
        busy.value = false
        if (recheckPending) {
          recheckPending = false
          void run('restore')
        }
      }
    }
  }

  function recheckSession() {
    if (busy.value) recheckPending = true
    else void run('restore')
  }
  function onVisibilityChange() {
    if (document.visibilityState === 'visible') recheckSession()
  }

  onMounted(() => {
    try {
      if ('BroadcastChannel' in window) {
        channel = new BroadcastChannel('ppt-agent:auth')
        channel.onmessage = () => recheckSession()
      }
    } catch { /* Visibility checks remain available if messaging is blocked. */ }
    document.addEventListener('visibilitychange', onVisibilityChange)
    void run('restore')
  })
  onUnmounted(() => {
    disposed = true
    generation += 1
    controller?.abort()
    channel?.close()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return {
    user, state, busy, error, notice,
    restoreSession: () => run('restore'),
    login: (input: LoginInput) => run('login', input),
    logout: () => run('logout'),
    expireSession,
  }
}
