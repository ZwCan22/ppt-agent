import { computed, onUnmounted, ref } from 'vue'
import { createPptTask } from '../api/ppt'
import { ApiError } from '../api/http'
import {
  clearPendingSubmission, normalizeBrief, readPendingSubmission, savePendingSubmission,
  type PendingSubmission,
} from '../storage/pptSubmission'
import type { PptBrief, PptTaskCreated } from '../types/ppt'

export function usePptSubmission(userId: string, callbacks: {
  onCreated: (result: PptTaskCreated, brief: PptBrief) => void
  onUnauthorized: () => void
}) {
  const pending = ref<PendingSubmission | null>(null)
  const submitting = ref(false)
  const recoveryBlocked = ref(false)
  const error = ref('')
  const notice = ref('')
  const locked = computed(() => pending.value !== null || recoveryBlocked.value)
  let disposed = false
  let controller: AbortController | undefined

  try {
    pending.value = readPendingSubmission(window.sessionStorage, userId)
  } catch {
    recoveryBlocked.value = true
    error.value = '浏览器无法读取上次提交记录，请先检查任务历史，避免重复制作。'
  }

  async function perform(entry: PendingSubmission) {
    if (disposed || submitting.value) return
    submitting.value = true
    error.value = ''
    notice.value = ''
    // Save before POST so a reload can recover the same key and original brief.
    try {
      savePendingSubmission(window.sessionStorage, userId, entry)
    } catch {
      error.value = '浏览器无法保存提交记录，本次未发送。请允许站点存储后重试。'
      submitting.value = false
      return
    }
    const request = new AbortController()
    controller = request
    const timeout = window.setTimeout(() => request.abort(), 10_000)
    let result: PptTaskCreated | undefined
    try {
      result = await createPptTask(entry.brief, entry.key, request.signal)
    } catch (cause: unknown) {
      if (disposed) return
      if (cause instanceof ApiError && cause.status === 401) {
        callbacks.onUnauthorized()
        return
      }
      // A rejection of this retry cannot disprove an earlier successful POST.
      // Keep the key until success or an explicit decision to discard it.
      if (cause instanceof ApiError) {
        error.value = `${cause.message}。可检查任务历史，或沿用原提交再次确认。`
      } else {
        error.value = request.signal.aborted
          ? '提交超时，结果尚未确认。请点击“确认原提交”，避免重复制作。'
          : '暂时没有确认提交结果。请点击“确认原提交”，将沿用原需求重试。'
      }
    } finally {
      window.clearTimeout(timeout)
      if (controller === request) controller = undefined
      if (!disposed) submitting.value = false
    }
    if (!result || disposed) return
    try {
      clearPendingSubmission(window.sessionStorage, userId)
    } catch {
      notice.value = '任务已确认，但浏览器未能清理提交记录；刷新后可再次确认同一任务。'
    }
    pending.value = null
    callbacks.onCreated(result, normalizeBrief(entry.brief))
  }

  async function submit(brief: PptBrief) {
    if (disposed || submitting.value || locked.value) return
    error.value = ''
    try {
      const entry: PendingSubmission = { key: crypto.randomUUID(), brief: normalizeBrief(brief) }
      // Validate and persist before exposing an unresolved submission.
      savePendingSubmission(window.sessionStorage, userId, entry)
      pending.value = entry
    } catch {
      error.value = '无法准备提交记录，本次未发送。请通过 localhost 或 HTTPS 访问，并允许站点存储。'
      return
    }
    await perform(pending.value)
  }

  async function retry() {
    if (disposed || submitting.value || !pending.value) return
    await perform({ key: pending.value.key, brief: normalizeBrief(pending.value.brief) })
  }

  function discard() {
    if (disposed || submitting.value) return
    try {
      clearPendingSubmission(window.sessionStorage, userId)
      pending.value = null
      recoveryBlocked.value = false
      error.value = ''
      notice.value = '已放弃确认原提交。原任务可能仍在制作，可在任务历史查看；再次提交将创建新任务。'
    } catch {
      error.value = '浏览器无法清除提交记录，本次没有新建任务。'
    }
  }

  onUnmounted(() => {
    disposed = true
    controller?.abort()
  })
  return { pending, submitting, recoveryBlocked, locked, error, notice, submit, retry, discard }
}
