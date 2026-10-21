export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function responseError(response: Response, payload: unknown, fallback: string): ApiError {
  const message = isRecord(payload) && isRecord(payload.error) &&
    typeof payload.error.message === 'string' ? payload.error.message : fallback
  return new ApiError(response.status, message)
}
