import type { PptBrief } from '../types/ppt'

type SubmissionStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
export interface PendingSubmission {
  key: string
  brief: PptBrief
}

function storageKey(userId: string): string {
  return `ppt-agent:pending-submission:v1:${userId}`
}

export function normalizeBrief(brief: PptBrief): PptBrief {
  return {
    topic: brief.topic.trim(), audience: brief.audience.trim(),
    slide_count: brief.slide_count, requirements: brief.requirements.trim(),
    template_id: brief.template_id,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isPendingSubmission(value: unknown): value is PendingSubmission {
  if (!isRecord(value) || typeof value.key !== 'string' ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.key) ||
    !isRecord(value.brief)) return false
  const brief = value.brief
  return typeof brief.topic === 'string' && brief.topic.trim().length > 0 && brief.topic.length <= 200 &&
    typeof brief.audience === 'string' && brief.audience.trim().length > 0 && brief.audience.length <= 80 &&
    typeof brief.slide_count === 'number' && Number.isInteger(brief.slide_count) &&
    brief.slide_count >= 6 && brief.slide_count <= 20 &&
    typeof brief.requirements === 'string' && brief.requirements.length <= 3000 &&
    brief.template_id === 'business_blue'
}

export function readPendingSubmission(storage: SubmissionStorage, userId: string): PendingSubmission | null {
  const raw = storage.getItem(storageKey(userId))
  if (raw === null) return null
  const value: unknown = JSON.parse(raw)
  if (!isPendingSubmission(value)) throw new Error('保存的提交记录格式不正确')
  return { key: value.key, brief: normalizeBrief(value.brief) }
}

export function savePendingSubmission(storage: SubmissionStorage, userId: string, entry: PendingSubmission): void {
  if (!isPendingSubmission(entry)) throw new Error('提交编号或需求格式不正确')
  storage.setItem(storageKey(userId), JSON.stringify({ key: entry.key, brief: normalizeBrief(entry.brief) }))
}

export function clearPendingSubmission(storage: SubmissionStorage, userId: string): void {
  storage.removeItem(storageKey(userId))
}
