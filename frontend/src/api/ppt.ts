import type {
  PptBrief,
  PptTaskCreated,
  PptTaskState,
  PptTaskStatus,
  PptTaskHistoryItem,
  PptTaskListResponse,
} from '../types/ppt'
import { ApiError, responseError } from './http'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value)
}

export async function createPptTask(
  brief: PptBrief,
  submissionKey: string,
  signal?: AbortSignal,
): Promise<PptTaskCreated> {
  const response = await fetch('/api/ppt/tasks', {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': submissionKey,
    },
    body: JSON.stringify(brief),
  })

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    let message = '需求提交失败，请稍后重试。'

    if (
      isRecord(payload) &&
      isRecord(payload.error) &&
      typeof payload.error.message === 'string'
    ) {
      message = payload.error.message
    }

    throw new ApiError(response.status, message)
  }

  if (
    !isRecord(payload) ||
    typeof payload.id !== 'string' ||
    !payload.id ||
    !isTaskStatus(payload.status) ||
    typeof payload.created_at !== 'string'
  ) {
    throw new Error('服务返回的任务信息不完整。')
  }

  return {
    id: payload.id,
    status: payload.status,
    created_at: payload.created_at,
  }
}
function isTaskStatus(value: unknown): value is PptTaskStatus {
  return typeof value === 'string' && [
    'queued', 'planning', 'rendering',
    'checking', 'succeeded', 'failed',
  ].includes(value)
}

export async function getPptTask(
  taskId: string,
  signal?: AbortSignal,
): Promise<PptTaskState> {
  const response = await fetch(
    `/api/ppt/tasks/${encodeURIComponent(taskId)}`,
    { signal, cache: 'no-store', credentials: 'same-origin' },
  )

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    let message = '暂时无法查询任务状态。'
    if (
      isRecord(payload) &&
      isRecord(payload.error) &&
      typeof payload.error.message === 'string'
    ) {
      message = payload.error.message
    }
    throw new ApiError(response.status, message)
  }

  if (
    !isRecord(payload) ||
    payload.id !== taskId ||
    typeof payload.topic !== 'string' ||
    !payload.topic.trim() ||
    typeof payload.audience !== 'string' ||
    !payload.audience.trim() ||
    typeof payload.slide_count !== 'number' ||
    !Number.isInteger(payload.slide_count) ||
    payload.slide_count < 6 ||
    payload.slide_count > 20 ||
    !isTaskStatus(payload.status) ||
    !(payload.error_message === null ||
      typeof payload.error_message === 'string')
  ) {
    throw new Error('服务返回的任务状态不完整或不匹配。')
  }

  return {
    id: taskId,
    topic: payload.topic,
    audience: payload.audience,
    slide_count: payload.slide_count,
    status: payload.status,
    error_message: payload.error_message,
  }
}

export function getPptDownloadUrl(taskId: string): string {
  return `/api/ppt/tasks/${encodeURIComponent(taskId)}/download`
}

export async function downloadPptTask(taskId: string, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch(getPptDownloadUrl(taskId), {
    credentials: 'same-origin', cache: 'no-store', signal,
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    throw responseError(response, payload, '暂时无法下载演示文稿。')
  }
  if (!response.headers.get('content-type')?.startsWith(
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  )) throw new Error('下载响应格式不正确，请重试。')
  return response.blob()
}

export function isPptTaskHistoryItem(
  value: unknown,
): value is PptTaskHistoryItem {
  if (!isRecord(value)) return false

  return (
    typeof value.id === 'string' &&
    value.id.trim().length > 0 &&
    typeof value.topic === 'string' &&
    value.topic.trim().length > 0 &&
    typeof value.audience === 'string' &&
    value.audience.trim().length > 0 &&
    typeof value.slide_count === 'number' &&
    Number.isInteger(value.slide_count) &&
    value.slide_count >= 6 &&
    value.slide_count <= 20 &&
    isTaskStatus(value.status) &&
    (
      value.error_message === null ||
      typeof value.error_message === 'string'
    ) &&
    typeof value.created_at === 'string' &&
    Number.isFinite(Date.parse(value.created_at)) &&
    typeof value.updated_at === 'string' &&
    Number.isFinite(Date.parse(value.updated_at))
  )
}

export async function getPptTaskHistory(
  limit = 20,
  offset = 0,
  signal?: AbortSignal,
): Promise<PptTaskListResponse> {
  if (
    !Number.isInteger(limit) || limit < 1 || limit > 100 ||
    !Number.isInteger(offset) || offset < 0
  ) {
    throw new Error('分页参数不符合要求')
  }

  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  const response = await fetch(`/api/ppt/tasks?${params}`, {
    method: 'GET',
    credentials: 'same-origin',
    signal,
    cache: 'no-store',
  })

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    let message = '暂时无法获取任务历史。'

    if (
      isRecord(payload) &&
      isRecord(payload.error) &&
      typeof payload.error.message === 'string'
    ) {
      message = payload.error.message
    }

    throw new ApiError(response.status, message)
  }

  if (
    !isRecord(payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(isPptTaskHistoryItem) ||
    payload.items.length > limit ||
    payload.limit !== limit ||
    payload.offset !== offset ||
    typeof payload.has_more !== 'boolean' ||
    (payload.has_more && payload.items.length !== limit)
  ) {
    throw new Error('服务返回的任务历史格式不正确。')
  }

  return {
    items: payload.items,
    limit: payload.limit,
    offset: payload.offset,
    has_more: payload.has_more,
  }
}
