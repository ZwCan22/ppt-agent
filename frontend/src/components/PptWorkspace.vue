<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import QueueNotice from './QueueNotice.vue'
import PptBriefForm from './PptBriefForm.vue'
import { downloadPptTask } from '../api/ppt'
import { ApiError } from '../api/http'
import { usePptSubmission } from '../composables/usePptSubmission'
import { usePptTask } from '../composables/usePptTask'
import { clearLastTaskId, readLastTaskId, saveLastTaskId } from '../storage/pptTask'
import type { PptBrief, PptTaskCreated, PptTaskStatus } from '../types/ppt'
import type { UserPublic } from '../types/auth'
import PptTaskHistory from './PptTaskHistory.vue'
import { usePptTaskHistory } from '../composables/usePptTaskHistory'

const props = defineProps<{ user: UserPublic }>()
const emit = defineEmits<{ 'session-expired': [] }>()
const onUnauthorized = () => emit('session-expired')

const downloading = ref(false)
const errorMessage = ref('')
const storageMessage = ref('')
const confirmedBrief = ref<PptBrief | null>(null)
const activeTaskId = ref<string | null>(null)
const { task, queryError, isWatching, startPolling, stopPolling } = usePptTask(onUnauthorized)
let disposed = false
let downloadController: AbortController | undefined
const downloadUrls = new Set<string>()
const {
  pending, submitting, recoveryBlocked, locked: submissionLocked,
  error: submissionError, notice: submissionNotice,
  submit: submitTask, retry: retrySubmission, discard: discardSubmission,
} = usePptSubmission(props.user.id, { onCreated: handleCreated, onUnauthorized })

watch(() => submissionLocked.value && !submitting.value, async ready => {
  if (!ready) return
  await nextTick()
  if (!disposed) document.getElementById('submission-recovery-title')?.scrollIntoView({ block: 'center' })
}, { immediate: true })

const displayBrief = computed(() =>
  task.value?.id === activeTaskId.value ? task.value : confirmedBrief.value,
)

const {
  items: historyItems,
  loading: historyLoading,
  error: historyError,
  hasMore: historyHasMore,
  refresh: refreshHistory,
  loadMore: loadMoreHistory,
} = usePptTaskHistory(onUnauthorized)

onMounted(() => {
  try {
    const taskId = readLastTaskId(window.localStorage, props.user.id)
    if (!taskId) return
    activeTaskId.value = taskId
    startPolling(taskId)
  } catch {
    storageMessage.value = '浏览器无法读取上次任务记录，你仍可提交新任务。'
  }
})

onUnmounted(() => {
  disposed = true
  downloadController?.abort()
  for (const url of downloadUrls) URL.revokeObjectURL(url)
})

function clearCurrentTask() {
  if (submitting.value) return
  stopPolling()
  activeTaskId.value = null
  confirmedBrief.value = null
  errorMessage.value = ''
  storageMessage.value = ''
  try {
    clearLastTaskId(window.localStorage, props.user.id)
  } catch {
    storageMessage.value = '浏览器未能清除本机记录，刷新后可能再次显示该任务。'
  }
}

const statusLabels: Record<PptTaskStatus, string> = {
  queued: '排队中', planning: '生成大纲', rendering: '制作文件',
  checking: '检查文件', succeeded: '制作完成', failed: '制作失败',
}
const stages = [
  { code: 'queued', title: '需求已接收', hint: '等待后台开始处理' },
  { code: 'planning', title: '整理演示大纲', hint: '组织内容与叙述结构' },
  { code: 'rendering', title: '制作演示文稿', hint: '应用版式并生成文件' },
  { code: 'checking', title: '检查与交付', hint: '校验文件及演示页数' },
] as const

const activeStage = computed(() => {
  if (task.value?.status === 'succeeded') return stages.length
  return stages.findIndex(stage => stage.code === task.value?.status)
})
const displayStatus = computed(() => queryError.value ? '查询暂停'
  : task.value ? statusLabels[task.value.status]
    : isWatching.value ? '查询中' : '已提交')

function handleCreated(created: PptTaskCreated, brief: PptBrief) {
  if (disposed) return
  errorMessage.value = ''
  confirmedBrief.value = { ...brief }
  activeTaskId.value = created.id
  storageMessage.value = ''
  try {
    saveLastTaskId(window.localStorage, props.user.id, created.id)
  } catch {
    storageMessage.value = '浏览器未能保存任务记录，刷新前请保留右侧任务编号。'
  }
  startPolling(created.id)
}

function openHistoryTask(taskId: string) {
  if (disposed || submitting.value) return

  confirmedBrief.value = null
  activeTaskId.value = taskId
  errorMessage.value = ''
  storageMessage.value = ''

  try {
    saveLastTaskId(window.localStorage, props.user.id, taskId)
  } catch {
    storageMessage.value =
      '浏览器未能保存任务记录，刷新前请保留任务编号。'
  }

  startPolling(taskId)

  document.getElementById('result-title')?.scrollIntoView({
    block: 'start',
  })
}

async function downloadTask(taskId: string) {
  if (disposed || downloading.value) return
  downloading.value = true
  errorMessage.value = ''
  const request = new AbortController()
  downloadController = request
  const timeout = window.setTimeout(() => request.abort(), 60_000)
  try {
    const blob = await downloadPptTask(taskId, request.signal)
    if (disposed) return
    const url = URL.createObjectURL(blob)
    downloadUrls.add(url)
    const link = document.createElement('a')
    link.href = url
    link.download = `ppt-${taskId}.pptx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => {
      URL.revokeObjectURL(url)
      downloadUrls.delete(url)
    }, 1_000)
  } catch (cause: unknown) {
    if (disposed) return
    if (cause instanceof ApiError && cause.status === 401) {
      onUnauthorized()
      return
    }
    errorMessage.value = request.signal.aborted ? '下载超时，请重试。'
      : cause instanceof Error ? cause.message : '下载失败，请重试。'
  } finally {
    window.clearTimeout(timeout)
    if (!disposed) downloading.value = false
    if (downloadController === request) downloadController = undefined
  }
}
</script>

<template>
    <main class="studio-main">
      <section class="hero" aria-labelledby="page-title">
        <div>
          <p class="eyebrow"><span></span> 从一个主题开始</p>
          <h1 id="page-title">让好想法，<span>成为一份好演示。</span></h1>
          <p class="hero-description">描述主题与听众，帮你整理大纲、制作演示文稿。</p>
        </div>
        <div class="how-it-works" aria-label="使用流程">
          <span><b>01</b> 填写需求</span><AppIcon name="chevron" :size="14" />
          <span><b>02</b> 自动制作</span><AppIcon name="chevron" :size="14" />
          <span><b>03</b> 下载演示</span>
        </div>
      </section>

      <div class="workspace">
        <section class="surface form-panel" aria-labelledby="brief-title">
          <div class="panel-heading">
            <div><p class="section-kicker">YOUR BRIEF</p><h2 id="brief-title">创建演示文稿</h2></div>
            <span class="panel-symbol"><AppIcon name="sparkles" :size="21" /></span>
          </div>
          <p class="panel-description">先告诉我们，你想讲什么。</p>
          <div v-if="submissionLocked && !submitting" class="submission-recovery" role="status">
            <strong id="submission-recovery-title">上一次提交还没有确认结果</strong>
            <p v-if="pending">{{ pending.brief.topic }} · {{ pending.brief.slide_count }} 页</p>
            <p v-if="recoveryBlocked">浏览器中的提交记录暂时无法读取，请先检查任务历史。</p>
            <p>原任务可能已经创建。请先确认原提交；放弃后再新建可能产生两份。</p>
            <div class="submission-actions">
              <button v-if="pending" type="button" class="text-button" @click="retrySubmission">确认原提交 <AppIcon name="arrow" :size="15" /></button>
              <button type="button" class="text-button" @click="discardSubmission">放弃确认，填写新任务</button>
            </div>
          </div>
          <PptBriefForm :submitting="submitting" :locked="submissionLocked" :restored-brief="pending?.brief" @submit="submitTask" />
          <p v-if="submissionError" class="notice notice-error" role="alert">{{ submissionError }}</p>
          <p v-if="submissionNotice" class="notice submission-notice" role="status">{{ submissionNotice }}</p>
          <p v-if="errorMessage" class="notice notice-error" role="alert">{{ errorMessage }}</p>
          <p v-if="storageMessage" class="notice notice-error" role="status">{{ storageMessage }}</p>
        </section>

        <section class="surface result-panel" aria-labelledby="result-title">
          <div class="result-heading">
            <h2 id="result-title">你的演示文稿</h2>
            <span v-if="activeTaskId" class="status-badge" :class="queryError ? 'paused' : task?.status || 'unknown'" aria-live="polite">
              <i aria-hidden="true"></i>{{ displayStatus }}
            </span>
            <span v-else class="empty-badge">等待创建</span>
          </div>

          <div v-if="!activeTaskId" class="empty-state">
            <div class="deck-illustration" aria-hidden="true">
              <div class="paper-back paper-back-one"></div><div class="paper-back paper-back-two"></div>
              <div class="illustration-cover"><span class="cover-label">PRESENTATION</span><strong>YOUR NEXT<br />BIG IDEA.</strong><span class="cover-rule"></span><span class="cover-small">MAKE IT CLEAR.</span></div>
              <span class="illustration-spark"><AppIcon name="sparkles" :size="20" /></span>
            </div>
            <p class="illustration-caption">商务蓝模板 · 示意</p>
            <h3>下一份精彩演示，从这里开始</h3>
            <p>在左侧填写需求，制作进度和<br class="desktop-break" />下载入口会出现在这里。</p>
            <div class="empty-features"><span><AppIcon name="check" :size="14" /> 自动整理大纲</span><span><AppIcon name="check" :size="14" /> 文件可编辑</span></div>
          </div>

          <div v-else class="task-content">
            <div v-if="displayBrief" class="document-summary">
              <span class="document-icon"><AppIcon name="slides" :size="28" /></span>
              <div><p class="document-format">PPTX · 商务蓝</p><h3>{{ displayBrief.topic }}</h3><p class="document-meta">{{ displayBrief.slide_count }} 页 <span>·</span> 16:9 宽屏</p></div>
            </div>
            <p v-else-if="!queryError" class="watching-note" role="status">正在获取任务信息…</p>

            <div v-if="task?.status === 'succeeded'" class="completion-banner"><span><AppIcon name="check" :size="19" /></span><div><strong>演示文稿已准备好</strong><p>下载后即可打开并继续编辑。</p></div></div>

            <div v-if="queryError" class="notice notice-error" role="alert"><p>{{ queryError }}</p><button type="button" class="text-button" @click="startPolling(activeTaskId)">重新查询状态 <AppIcon name="arrow" :size="15" /></button></div>
            <QueueNotice v-if="task?.status === 'queued' && !queryError" :key="task.id" />
            <p v-if="task?.status === 'failed'" class="notice notice-error" role="alert">{{ task.error_message || '制作未完成，请稍后重新提交。' }}</p>

            <ol v-if="task && task.status !== 'failed'" class="stage-list" aria-label="制作步骤">
              <li v-for="(stage, index) in stages" :key="stage.code" :class="{ complete: index < activeStage, current: index === activeStage }" :aria-current="index === activeStage ? 'step' : undefined">
                <span class="stage-marker" aria-hidden="true"><AppIcon v-if="index < activeStage" name="check" :size="15" /><span v-else>{{ index + 1 }}</span></span>
                <div><strong>{{ stage.title }}</strong><p>{{ stage.hint }}</p></div>
                <span v-if="index === activeStage && !queryError" class="stage-pulse" aria-hidden="true"></span>
              </li>
            </ol>

            <button v-if="task?.status === 'succeeded'" type="button" class="primary-button download-button" :disabled="downloading" @click="downloadTask(task.id)"><AppIcon name="download" :size="19" /> {{ downloading ? '正在下载…' : '下载演示文稿' }} <span class="download-format">.pptx</span></button>
            <p v-else-if="isWatching" class="watching-note"><AppIcon name="clock" :size="15" /> 正在自动查询任务状态</p>

            <details class="task-details"><summary>任务详情 <AppIcon name="chevron" :size="14" /></summary><dl><dt>任务编号</dt><dd class="task-id">{{ activeTaskId }}</dd><template v-if="displayBrief"><dt>目标听众</dt><dd>{{ displayBrief.audience }}</dd></template><template v-if="confirmedBrief"><dt>其他要求</dt><dd class="requirement-text">{{ confirmedBrief.requirements || '未填写' }}</dd></template></dl></details>
            <button type="button" class="text-button" :disabled="submitting" aria-label="清除本机任务记录，后台任务继续运行" title="仅清除浏览器中的任务编号，后台任务继续运行" @click="clearCurrentTask">清除本机任务记录</button>
          </div>
        </section>
      </div>
      <PptTaskHistory
      :items="historyItems"
      :loading="historyLoading"
      :error="historyError"
      :has-more="historyHasMore"
      @refresh="refreshHistory"
      @load-more="loadMoreHistory"
      @select="openHistoryTask"
      />
      <footer class="page-footer"><span>把时间留给想法，把表达交给演示。</span><span>PPT 智能助手</span></footer>
    </main>
</template>

<style scoped>
.submission-recovery { margin: 18px 0; padding: 16px; background: #f1f6ff; border: 1px solid #d8e5fb; border-radius: 10px; color: #354866; font-size: 13px; overflow-wrap: anywhere; }
.submission-recovery p { margin: 8px 0 0; line-height: 1.7; }
.submission-actions { display: flex; flex-wrap: wrap; gap: 12px 20px; margin-top: 14px; }
.submission-notice { background: #f1f6ff; border: 1px solid #d8e5fb; color: #354866; }
</style>
