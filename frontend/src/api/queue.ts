import { isRecord, responseError } from './http'

export interface QueueHealth {
  status: 'ok' | 'warning'
  queued_task_count: number
  oldest_queued_task_age_seconds: number | null
  warning_after_seconds: number
  message: string
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

export async function getQueueHealth(signal?: AbortSignal): Promise<QueueHealth> {
  const response = await fetch('/api/health/queue', {
    credentials: 'same-origin', cache: 'no-store', signal,
  })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw responseError(response, payload, '暂时无法检查排队情况。')
  if (
    !isRecord(payload) ||
    !(payload.status === 'ok' || payload.status === 'warning') ||
    !isNonnegativeInteger(payload.queued_task_count) ||
    !(payload.oldest_queued_task_age_seconds === null ||
      isNonnegativeInteger(payload.oldest_queued_task_age_seconds)) ||
    !isNonnegativeInteger(payload.warning_after_seconds) || payload.warning_after_seconds < 1 ||
    typeof payload.message !== 'string'
  ) throw new Error('排队检查返回格式不正确。')

  const age = payload.oldest_queued_task_age_seconds
  if (
    (payload.queued_task_count === 0) !== (age === null) ||
    (payload.status === 'warning') !== (age !== null && age >= payload.warning_after_seconds)
  ) throw new Error('排队检查返回的数据不一致。')

  return {
    status: payload.status,
    queued_task_count: payload.queued_task_count,
    oldest_queued_task_age_seconds: age,
    warning_after_seconds: payload.warning_after_seconds,
    message: payload.message,
  }
}
