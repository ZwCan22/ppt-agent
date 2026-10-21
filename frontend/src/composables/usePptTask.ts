import { onUnmounted, ref } from 'vue'
import { getPptTask } from '../api/ppt'
import { ApiError } from '../api/http'
import type { PptTaskState } from '../types/ppt'

export function usePptTask(onUnauthorized?: () => void) {
  const task = ref<PptTaskState | null>(null)
  const queryError = ref('')
  const isWatching = ref(false)

  let timer: number | undefined
  let controller: AbortController | undefined
  let generation = 0
  let disposed = false

  function stopPolling() {
    generation += 1
    window.clearTimeout(timer)
    timer = undefined
    controller?.abort()
    controller = undefined
    isWatching.value = false
  }

  function startPolling(taskId: string) {
    if (disposed) return

    stopPolling()
    task.value = null
    queryError.value = ''
    isWatching.value = true
    void poll(taskId, generation)
  }

  async function poll(taskId: string, currentGeneration: number) {
    const request = new AbortController()
    controller = request
    const timeout = window.setTimeout(() => request.abort(), 10_000)

    try {
      const result = await getPptTask(taskId, request.signal)

      if (currentGeneration !== generation) return

      task.value = result

      if (result.status === 'succeeded' || result.status === 'failed') {
        isWatching.value = false
        return
      }

      timer = window.setTimeout(() => {
        void poll(taskId, currentGeneration)
      }, 3_000)
    } catch (error: unknown) {
      if (currentGeneration !== generation) return

      isWatching.value = false
      if (error instanceof ApiError && error.status === 401) {
        onUnauthorized?.()
        return
      }
      queryError.value = request.signal.aborted
        ? '查询超时，请重新查询状态。'
        : error instanceof TypeError
          ? '暂时无法连接服务，请重新查询状态。'
          : error instanceof Error
            ? error.message
            : '暂时无法查询任务状态。'
    } finally {
      window.clearTimeout(timeout)
      if (controller === request) controller = undefined
    }
  }

  onUnmounted(() => {
    disposed = true
    stopPolling()
  })

  return { task, queryError, isWatching, startPolling, stopPolling }
}
