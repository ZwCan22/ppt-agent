<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import type { PptBrief } from '../types/ppt'

const props = defineProps<{ submitting: boolean; locked?: boolean; restoredBrief?: PptBrief | null }>()
const emit = defineEmits<{ submit: [brief: PptBrief] }>()
const errorMessage = ref('')
const form = reactive<PptBrief>({
  topic: '', audience: '', slide_count: 8, requirements: '', template_id: 'business_blue',
})

watch(() => props.restoredBrief, brief => {
  if (brief) Object.assign(form, brief)
}, { immediate: true })

function fillExample() {
  if (props.submitting || props.locked) return
  Object.assign(form, {
    topic: '企业知识库如何利用 RAG 提高问答可靠性',
    audience: '企业技术负责人和产品经理',
    slide_count: 8,
    requirements: '用于 10 分钟内部分享，表达通俗，突出落地方法，不编造数据。',
  })
  errorMessage.value = ''
}

function submitBrief() {
  if (props.submitting || props.locked) return
  errorMessage.value = ''
  const brief: PptBrief = {
    ...form,
    topic: form.topic.trim(),
    audience: form.audience.trim(),
    requirements: form.requirements.trim(),
  }
  if (!brief.topic || !brief.audience) {
    errorMessage.value = '请填写 PPT 主题和目标听众。'
    return
  }
  if (!Number.isInteger(brief.slide_count) || brief.slide_count < 6 || brief.slide_count > 20) {
    errorMessage.value = '页数必须是 6 至 20 之间的整数。'
    return
  }
  emit('submit', brief)
}
</script>

<template>
  <form class="brief-form" @submit.prevent="submitBrief">
    <fieldset :disabled="props.submitting || props.locked">
      <div class="field">
        <div class="label-line">
          <label for="topic">你想讲什么？<span class="required-mark" aria-hidden="true">*</span></label>
          <span class="field-counter">{{ form.topic.length }} / 200</span>
        </div>
        <textarea id="topic" v-model="form.topic" class="topic-input" required maxlength="200" rows="2"
          placeholder="写下你的演示主题，例如：企业知识库如何利用 RAG 提高问答可靠性" />
        <div class="example-line">
          <span>还没想好怎么写？</span>
          <button type="button" class="text-button" @click="fillExample">用示例填写 <AppIcon name="arrow" :size="14" /></button>
        </div>
      </div>

      <div class="form-row">
        <div class="field">
          <label for="audience">讲给谁听？<span class="required-mark" aria-hidden="true">*</span></label>
          <input id="audience" v-model="form.audience" required maxlength="80" placeholder="例如：技术负责人和产品经理" />
        </div>
        <div class="field">
          <label for="slide-count">演示页数</label>
          <div class="number-input">
            <input id="slide-count" v-model.number="form.slide_count" type="number" required min="6" max="20" step="1"
              aria-describedby="page-hint" />
            <span aria-hidden="true">页</span>
          </div>
        </div>
      </div>
      <p id="page-hint" class="field-hint page-hint">支持 6–20 页，包含封面与结束页。</p>

      <div class="field">
        <div class="label-line">
          <label for="requirements">再补充一点要求 <span class="optional-label">选填</span></label>
          <span class="field-counter">{{ form.requirements.length }} / 3000</span>
        </div>
        <textarea id="requirements" v-model="form.requirements" rows="3" maxlength="3000"
          placeholder="用途、分享时长、表达风格，或你希望重点介绍的内容……" />
      </div>

      <div class="field template-field">
        <span class="field-label">演示风格</span>
        <div class="template-choice">
          <div class="template-thumb" aria-hidden="true"><i></i><i></i><i></i></div>
          <div class="template-copy"><strong>商务蓝</strong><span>简洁清晰 · 16:9 宽屏</span></div>
          <span class="template-selected"><AppIcon name="check" :size="15" /><span class="sr-only">已选用</span></span>
        </div>
      </div>

      <p v-if="errorMessage" class="notice notice-error" role="alert">{{ errorMessage }}</p>

      <div class="form-actions">
        <button type="submit" class="primary-button" :disabled="props.submitting || props.locked">
          <AppIcon :name="props.submitting ? 'loader' : 'sparkles'" :class="{ spin: props.submitting }" />
          {{ props.submitting ? '正在提交需求…' : props.locked ? '请先确认上次提交' : '生成演示文稿' }}
          <AppIcon v-if="!props.submitting" name="arrow" :size="18" class="button-arrow" />
        </button>
        <p class="form-footnote">生成后可下载、编辑 PPTX 文件</p>
      </div>
    </fieldset>
  </form>
</template>
