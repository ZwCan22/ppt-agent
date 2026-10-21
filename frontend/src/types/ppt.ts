export interface PptBrief {
  topic: string
  audience: string
  slide_count: number
  requirements: string
  template_id: 'business_blue'
}
export interface PptTaskCreated {
  id: string
  status: PptTaskStatus
  created_at: string
}

export type PptTaskStatus =
  | 'queued'
  | 'planning'
  | 'rendering'
  | 'checking'
  | 'succeeded'
  | 'failed'

export interface PptTaskState {
  id: string
  topic: string
  audience: string
  slide_count: number
  status: PptTaskStatus
  error_message: string | null
}
export interface PptTaskHistoryItem extends PptTaskState {
  created_at: string
  updated_at: string
}

export interface PptTaskListResponse {
  items: PptTaskHistoryItem[]
  limit: number
  offset: number
  has_more: boolean
}
