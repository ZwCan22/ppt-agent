import type { LoginInput, UserPublic } from '../types/auth'
import { isRecord, responseError } from './http'

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function parseUser(value: unknown): UserPublic {
  if (!isRecord(value) || typeof value.id !== 'string' || !UUID_PATTERN.test(value.id) ||
      typeof value.username !== 'string' || !/^[a-z0-9_]{3,32}$/.test(value.username) ||
      typeof value.created_at !== 'string' || !Number.isFinite(Date.parse(value.created_at))) {
    throw new Error('服务返回的用户信息不完整，请重试。')
  }
  return { id: value.id, username: value.username, created_at: value.created_at }
}

export async function getCurrentUser(signal?: AbortSignal): Promise<UserPublic> {
  const response = await fetch('/api/auth/me', {
    credentials: 'same-origin', cache: 'no-store', signal,
  })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw responseError(response, payload, '暂时无法确认登录状态。')
  return parseUser(payload)
}

export async function login(input: LoginInput, signal?: AbortSignal): Promise<UserPublic> {
  const response = await fetch('/api/auth/login', {
    method: 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input), signal,
  })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw responseError(response, payload, '登录失败，请稍后重试。')
  return parseUser(payload)
}

export async function logout(signal?: AbortSignal): Promise<void> {
  const response = await fetch('/api/auth/logout', {
    method: 'POST', credentials: 'same-origin', cache: 'no-store', signal,
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    throw responseError(response, payload, '退出登录未完成，请重试。')
  }
  if (response.status !== 204) throw new Error('服务返回的退出结果不正确，请重试。')
}
