import { onMounted, onUnmounted, ref } from 'vue'
import { getPptTaskHistory } from '../api/ppt'
import { ApiError } from '../api/http'
import type { PptTaskHistoryItem } from '../types/ppt'

const PAGE_SIZE = 10

export function usePptTaskHistory(onUnauthorized?: () => void) {
  const items = ref<PptTaskHistoryItem[]>([])
  const loading = ref(false)
  const error = ref('')
  const hasMore = ref(false)

  let nextOffset = 0
  let controller: AbortController | undefined
  let disposed = false

  async function loadPage(reset: boolean) {
    if (disposed || loading.value) return
    if (!reset && !hasMore.value) return

    loading.value = true
    error.value = ''

    const offset = reset ? 0 : nextOffset
    const request = new AbortController()
    controller = request

    const timeout = window.setTimeout(() => {
      request.abort()
    }, 10_000)

    try {
      const page = await getPptTaskHistory(
        PAGE_SIZE,
        offset,
        request.signal,
      )

      if (disposed) return

      const combined = reset
        ? page.items
        : [...items.value, ...page.items]

      const uniqueItems = new Map<string, PptTaskHistoryItem>()

      for (const item of combined) {
        uniqueItems.set(item.id, item)
      }

      items.value = Array.from(uniqueItems.values())
      nextOffset = page.offset + page.items.length
      hasMore.value = page.has_more
    } catch (cause: unknown) {
      if (disposed) return
      if (cause instanceof ApiError && cause.status === 401) {
        onUnauthorized?.()
        return
      }

      error.value = request.signal.aborted
        ? '读取任务历史超时，请重试。'
        : cause instanceof TypeError
          ? '暂时无法连接服务，请重试。'
          : cause instanceof Error
            ? cause.message
            : '读取任务历史失败。'
    } finally {
      window.clearTimeout(timeout)
      controller = undefined

      if (!disposed) {
        loading.value = false
      }
    }
  }

  function refresh() {
    void loadPage(true)
  }

  function loadMore() {
    void loadPage(false)
  }

  onMounted(refresh)

  onUnmounted(() => {
    disposed = true
    controller?.abort()
  })

  return {
    items,
    loading,
    error,
    hasMore,
    refresh,
    loadMore,
  }
}
