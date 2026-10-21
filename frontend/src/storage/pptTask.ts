const LEGACY_KEY = 'ppt-agent:last-task-id:v1'
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

type TaskStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function taskKey(userId: string): string {
  if (!UUID_PATTERN.test(userId)) throw new Error('无效的用户编号')
  return `ppt-agent:last-task-id:v2:${userId.toLowerCase()}`
}

export function readLastTaskId(storage: TaskStorage, userId: string): string | null {
  const key = taskKey(userId)
  storage.removeItem(LEGACY_KEY)
  const taskId = storage.getItem(key)
  if (taskId === null) return null

  if (!UUID_PATTERN.test(taskId)) {
    storage.removeItem(key)
    return null
  }

  return taskId
}

export function saveLastTaskId(storage: TaskStorage, userId: string, taskId: string): void {
  if (!UUID_PATTERN.test(taskId)) {
    throw new Error('无法保存无效的任务编号')
  }
  storage.setItem(taskKey(userId), taskId)
}

export function clearLastTaskId(storage: TaskStorage, userId: string): void {
  storage.removeItem(taskKey(userId))
}
