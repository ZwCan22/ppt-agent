import { onMounted, onUnmounted, ref } from 'vue'
import { getQueueHealth, type QueueHealth } from '../api/queue'

export function useQueueHealth() {
  const report = ref<QueueHealth | null>(null)
  const unavailable = ref(false)
  let disposed = false
  let timer: number | undefined
  let requestTimeout: number | undefined
  let controller: AbortController | undefined

  async function check() {
    if (disposed) return
    const request = new AbortController()
    controller = request
    const timeout = window.setTimeout(() => request.abort(), 5_000)
    requestTimeout = timeout
    try {
      const result = await getQueueHealth(request.signal)
      if (disposed) return
      if (request.signal.aborted) throw new Error('Queue check timed out')
      report.value = result
      unavailable.value = false
    } catch {
      if (disposed) return
      // Never present an old warning as a fresh observation after a failed check.
      report.value = null
      unavailable.value = true
    } finally {
      window.clearTimeout(timeout)
      if (requestTimeout === timeout) requestTimeout = undefined
      if (controller === request) controller = undefined
      if (!disposed) timer = window.setTimeout(() => void check(), 10_000)
    }
  }

  onMounted(() => void check())
  onUnmounted(() => {
    disposed = true
    window.clearTimeout(timer)
    window.clearTimeout(requestTimeout)
    controller?.abort()
  })
  return { report, unavailable }
}
