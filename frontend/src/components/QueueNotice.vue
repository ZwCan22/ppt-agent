<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { useQueueHealth } from '../composables/useQueueHealth'

const { report, unavailable } = useQueueHealth()
const thresholdLabel = computed(() => {
  const seconds = report.value?.warning_after_seconds ?? 180
  return seconds % 60 === 0 ? `${seconds / 60} 分钟` : `${seconds} 秒`
})
</script>

<template>
  <aside v-if="report?.status === 'warning'" class="queue-notice" role="status" aria-live="polite">
    <AppIcon name="clock" :size="19" />
    <div>
      <strong>系统队列等待较久</strong>
      <p>系统中有任务提交已满 {{ thresholdLabel }}，仍在排队。</p>
      <p>当前任务仍在队列中，页面会继续更新。请保留任务编号，无需重复提交。</p>
    </div>
  </aside>
  <p v-else-if="unavailable" class="queue-check-note" role="status">
    排队情况暂时无法检查，任务状态仍会继续更新。
  </p>
</template>

<style scoped>
.queue-notice { display: flex; align-items: flex-start; gap: 11px; padding: 14px; margin: 0 0 22px; border: 1px solid #eeddb6; border-radius: 9px; background: #fff9ec; color: #806333; }
.queue-notice > svg { flex-shrink: 0; margin-top: 2px; }
.queue-notice strong { display: block; font-size: 13px; font-weight: 600; }
.queue-notice p { margin: 6px 0 0; font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
.queue-check-note { margin: 0 0 20px; font-size: 12px; line-height: 1.8; color: #8791a0; }
</style>
