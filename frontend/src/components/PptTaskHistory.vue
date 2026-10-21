<script setup lang="ts">
import type {
  PptTaskHistoryItem,
  PptTaskStatus,
} from '../types/ppt'

defineProps<{
  items: PptTaskHistoryItem[]
  loading: boolean
  error: string
  hasMore: boolean
}>()

const emit = defineEmits<{
  refresh: []
  loadMore: []
  select: [taskId: string]
}>()

const statusLabels: Record<PptTaskStatus, string> = {
  queued: '排队中',
  planning: '生成大纲',
  rendering: '制作文件',
  checking: '检查文件',
  succeeded: '制作完成',
  failed: '制作失败',
}
</script>

<template>
  <section class="surface history-panel">
    <header class="history-heading">
      <h2>任务历史</h2>
      <button
        type="button"
        class="text-button"
        :disabled="loading"
        @click="emit('refresh')"
      >
        刷新列表
      </button>
    </header>

    <p v-if="error" class="notice notice-error" role="alert">
      {{ error }}
    </p>

    <p v-if="loading" role="status">正在读取任务历史…</p>
    <p v-else-if="!error && items.length === 0">还没有任务记录。</p>

    <ul v-if="items.length > 0" class="history-list">
      <li v-for="item in items" :key="item.id" class="history-item">
        <div class="history-info">
          <strong>{{ item.topic }}</strong>
          <p>
            {{ item.slide_count }} 页 · {{ statusLabels[item.status] }}
          </p>
          <p>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</p>
        </div>

        <button
          type="button"
          class="text-button"
          :disabled="loading"
          @click="emit('select', item.id)"
        >
          查看任务
        </button>
      </li>
    </ul>

    <button
      v-if="hasMore"
      type="button"
      class="text-button"
      :disabled="loading"
      @click="emit('loadMore')"
    >
      {{ loading ? '加载中…' : '加载更多' }}
    </button>
  </section>
</template>

<style scoped>
.history-panel {
  margin-top: 24px;
  padding: 24px;
}

.history-heading,
.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.history-heading h2 {
  margin: 0;
  font-size: 20px;
}

.history-list {
  list-style: none;
  margin: 16px 0;
  padding: 0;
}

.history-item {
  padding: 16px 0;
  border-bottom: 1px solid #e8e8ec;
}

.history-info {
  min-width: 0;
  overflow-wrap: anywhere;
}

.history-info p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.history-item button {
  flex-shrink: 0;
}
</style>